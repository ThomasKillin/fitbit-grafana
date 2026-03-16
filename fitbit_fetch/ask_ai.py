"""Text-to-metric querying helpers for Fitbit + Influx data."""

from dataclasses import dataclass
import re

import requests


@dataclass(frozen=True)
class MetricTarget:
    label: str
    measurement: str
    field: str
    metric_class: str | None
    unit: str
    aliases: tuple[str, ...]


METRIC_TARGETS = (
    MetricTarget(
        label="Resting heart rate",
        measurement="RestingHR",
        field="value",
        metric_class="Direct",
        unit="bpm",
        aliases=("resting heart rate", "rhr", "resting hr"),
    ),
    MetricTarget(
        label="HRV (daily RMSSD)",
        measurement="HRV",
        field="dailyRmssd",
        metric_class="Direct",
        unit="ms",
        aliases=("hrv", "rmssd"),
    ),
    MetricTarget(
        label="Daily steps",
        measurement="Total Steps",
        field="value",
        metric_class="Direct",
        unit="steps",
        aliases=("steps", "daily steps", "step count"),
    ),
    MetricTarget(
        label="Sleep duration",
        measurement="Sleep Summary",
        field="minutesAsleep",
        metric_class="Direct",
        unit="minutes",
        aliases=("sleep", "sleep minutes", "minutes asleep"),
    ),
    MetricTarget(
        label="Recovery score",
        measurement="Derived RecoveryScore",
        field="score",
        metric_class="Derived",
        unit="score",
        aliases=("recovery score", "recovery"),
    ),
    MetricTarget(
        label="Training load ratio",
        measurement="Derived TrainingLoad",
        field="load_ratio",
        metric_class="Derived",
        unit="ratio",
        aliases=("load ratio", "training load ratio", "acute chronic ratio"),
    ),
)


def infer_target(question: str) -> MetricTarget | None:
    q = question.lower()
    for target in METRIC_TARGETS:
        if any(alias in q for alias in target.aliases):
            return target
    return None


def infer_window_days(question: str, default_days: int = 14) -> int:
    q = question.lower()
    days_match = re.search(r"(\d+)\s*day", q)
    weeks_match = re.search(r"(\d+)\s*week", q)
    months_match = re.search(r"(\d+)\s*month", q)
    if days_match:
        return max(1, min(365, int(days_match.group(1))))
    if weeks_match:
        return max(1, min(365, int(weeks_match.group(1)) * 7))
    if months_match:
        return max(1, min(365, int(months_match.group(1)) * 30))
    if "today" in q:
        return 1
    if "yesterday" in q:
        return 2
    return default_days


def summarize_series(*, values: list[dict], label: str, unit: str, days: int) -> dict:
    if not values:
        return {
            "label": label,
            "days": days,
            "points": 0,
            "summary": f"No data points found for {label.lower()} over the last {days} days.",
        }
    first = values[0]["value"]
    latest = values[-1]["value"]
    avg = sum(item["value"] for item in values) / len(values)
    delta = latest - first
    direction = "increased" if delta > 0 else ("decreased" if delta < 0 else "stayed flat")
    summary = (
        f"{label} over last {days} days: latest {latest:.2f} {unit}, "
        f"average {avg:.2f} {unit}, {direction} by {abs(delta):.2f} {unit}."
    )
    return {
        "label": label,
        "days": days,
        "points": len(values),
        "latest": round(latest, 4),
        "average": round(avg, 4),
        "delta": round(delta, 4),
        "unit": unit,
        "summary": summary,
    }


def maybe_openai_rewrite(
    *,
    question: str,
    summary_payload: dict,
    api_key: str | None,
    model: str = "gpt-4.1-mini",
    base_url: str = "https://api.openai.com/v1",
    timeout_seconds: int = 20,
) -> str | None:
    if not api_key:
        return None
    prompt = (
        "You are a health dashboard analyst. Answer the user's question using only the provided stats. "
        "Do not add medical advice. Keep the response under 120 words.\n\n"
        f"Question: {question}\n"
        f"Stats: {summary_payload}\n"
    )
    try:
        response = requests.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "Use only provided stats. Be concise."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.2,
            },
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        choices = payload.get("choices") or []
        if not choices:
            return None
        message = choices[0].get("message", {})
        content = message.get("content")
        return content.strip() if isinstance(content, str) else None
    except requests.RequestException:
        return None


def maybe_ollama_rewrite(
    *,
    question: str,
    summary_payload: dict,
    model: str = "llama3.1:8b",
    base_url: str = "http://localhost:11434",
    timeout_seconds: int = 30,
) -> str | None:
    prompt = (
        "You are a health dashboard analyst. Answer using only provided stats. "
        "Do not add medical advice. Keep under 120 words.\n\n"
        f"Question: {question}\n"
        f"Stats: {summary_payload}\n"
    )
    try:
        response = requests.post(
            f"{base_url.rstrip('/')}/api/generate",
            headers={"Content-Type": "application/json"},
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
            },
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        content = payload.get("response")
        return content.strip() if isinstance(content, str) else None
    except requests.RequestException:
        return None


def answer_question(
    *,
    question: str,
    influx_writer,
    default_window_days: int = 14,
    ai_provider: str = "auto",
    openai_api_key: str | None = None,
    openai_model: str = "gpt-4.1-mini",
    openai_base_url: str = "https://api.openai.com/v1",
    ollama_model: str = "llama3.1:8b",
    ollama_base_url: str = "http://localhost:11434",
) -> dict:
    target = infer_target(question)
    if target is None:
        supported = ", ".join(t.label for t in METRIC_TARGETS)
        return {
            "ok": False,
            "error": (
                "Could not infer a metric from your question. "
                f"Try one of: {supported}."
            ),
        }

    days = infer_window_days(question, default_days=default_window_days)
    series = influx_writer.query_metric_series(
        measurement=target.measurement,
        field=target.field,
        days=days,
        metric_class=target.metric_class,
    )
    summary = summarize_series(values=series, label=target.label, unit=target.unit, days=days)
    provider = (ai_provider or "auto").strip().lower()
    ai_text = None
    if provider == "openai":
        ai_text = maybe_openai_rewrite(
            question=question,
            summary_payload=summary,
            api_key=openai_api_key,
            model=openai_model,
            base_url=openai_base_url,
        )
    elif provider == "ollama":
        ai_text = maybe_ollama_rewrite(
            question=question,
            summary_payload=summary,
            model=ollama_model,
            base_url=ollama_base_url,
        )
    else:
        # auto mode: prefer OpenAI when key exists, fallback to local Ollama.
        if openai_api_key:
            ai_text = maybe_openai_rewrite(
                question=question,
                summary_payload=summary,
                api_key=openai_api_key,
                model=openai_model,
                base_url=openai_base_url,
            )
        if ai_text is None:
            ai_text = maybe_ollama_rewrite(
                question=question,
                summary_payload=summary,
                model=ollama_model,
                base_url=ollama_base_url,
            )
    return {
        "ok": True,
        "question": question,
        "metric": target.label,
        "measurement": target.measurement,
        "field": target.field,
        "metric_class": target.metric_class,
        "days": days,
        "ai_provider": provider,
        "summary": summary,
        "answer": ai_text or summary["summary"],
    }
