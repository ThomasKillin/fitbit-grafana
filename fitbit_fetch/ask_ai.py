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
        label="Cardio fitness (direct VO2 max)",
        measurement="CardioFitness",
        field="vo2_max",
        metric_class="Direct",
        unit="ml/kg/min",
        aliases=("cardio fitness", "vo2", "vo2 max", "direct cardio fitness"),
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
    MetricTarget(
        label="ECG events",
        measurement="ECG",
        field="event_count",
        metric_class="Direct",
        unit="events/day",
        aliases=("ecg", "afib ecg", "ecg events"),
    ),
    MetricTarget(
        label="IRN events",
        measurement="IRN",
        field="event_count",
        metric_class="Direct",
        unit="events/day",
        aliases=("irn", "irregular rhythm", "irregular rhythm notification"),
    ),
    MetricTarget(
        label="Device sync age",
        measurement="DeviceSyncHealth",
        field="minutes_since_last_sync",
        metric_class="Direct",
        unit="minutes",
        aliases=("sync health", "device sync", "last sync", "minutes since sync"),
    ),
)


def infer_overall_summary_intent(question: str) -> bool:
    q = question.lower()
    phrases = (
        "entire dataset",
        "full dataset",
        "all data",
        "overall health",
        "overall summary",
        "health summary",
        "detailed summary",
        "summary of my health",
        "from the entire dataset",
    )
    return any(phrase in q for phrase in phrases)


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


def summarize_multi_metric(*, per_metric: list[dict], days: int) -> dict:
    available = [item for item in per_metric if item.get("points", 0) > 0]
    missing = [item["label"] for item in per_metric if item.get("points", 0) == 0]
    lines = [f"Health summary over last {days} days across {len(per_metric)} tracked metrics."]
    if available:
        lines.append("Available metrics:")
        for item in available:
            lines.append(f"- {item['summary']}")
    if missing:
        lines.append("No data found for: " + ", ".join(missing) + ".")
    return {
        "days": days,
        "metric_count": len(per_metric),
        "available_metric_count": len(available),
        "missing_metrics": missing,
        "metrics": per_metric,
        "summary": " ".join(lines),
    }


def conversational_single_metric(*, metric: str, summary: dict, days: int) -> str:
    if summary.get("points", 0) == 0:
        return (
            f"I checked your {metric.lower()} over the last {days} days, but I couldn't find data yet. "
            "Once new points land in InfluxDB, I can summarize the trend."
        )
    latest = summary.get("latest")
    avg = summary.get("average")
    delta = summary.get("delta")
    unit = summary.get("unit", "")
    trend = "up" if (delta or 0) > 0 else ("down" if (delta or 0) < 0 else "flat")
    return (
        f"Here is the short version: over the last {days} days, your {metric.lower()} is trending {trend}. "
        f"Latest is {latest:.2f} {unit}, average is {avg:.2f} {unit}, and net change is {delta:+.2f} {unit}. "
        "If you want, I can break it down week by week next."
    )


def conversational_overall_summary(*, summary: dict, days: int) -> str:
    metrics = summary.get("metrics", [])
    available = [item for item in metrics if item.get("points", 0) > 0]
    missing = summary.get("missing_metrics", [])
    lead = (
        f"I reviewed your overall health data for the last {days} days. "
        f"I found usable data for {len(available)} of {len(metrics)} tracked metrics."
    )
    highlights = []
    for item in available[:4]:
        delta = item.get("delta")
        unit = item.get("unit", "")
        trend = "up" if (delta or 0) > 0 else ("down" if (delta or 0) < 0 else "flat")
        highlights.append(f"{item['label']}: {trend} ({delta:+.2f} {unit}).")
    missing_text = ""
    if missing:
        missing_text = " Missing data: " + ", ".join(missing) + "."
    next_step = "If you want, I can now focus on one metric and explain the recent drivers in more detail."
    return " ".join([lead, " ".join(highlights), missing_text, next_step]).strip()


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
        "Write in a conversational style like ChatGPT: clear, natural, and concise. "
        "Do not add medical advice. Keep the response under 140 words.\n\n"
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
                    {
                        "role": "system",
                        "content": (
                            "Use only provided stats. Keep a conversational tone, plain English, and no medical advice."
                        ),
                    },
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
        "Write in conversational plain English. "
        "Do not add medical advice. Keep under 140 words.\n\n"
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
    overall_intent = target is None and infer_overall_summary_intent(question)

    if overall_intent:
        q = question.lower()
        days = 3650 if ("entire dataset" in q or "full dataset" in q or "all data" in q) else infer_window_days(
            question,
            default_days=default_window_days,
        )
        per_metric = []
        for metric_target in METRIC_TARGETS:
            series = influx_writer.query_metric_series(
                measurement=metric_target.measurement,
                field=metric_target.field,
                days=days,
                metric_class=metric_target.metric_class,
            )
            per_metric.append(
                summarize_series(
                    values=series,
                    label=metric_target.label,
                    unit=metric_target.unit,
                    days=days,
                )
            )

        summary = summarize_multi_metric(per_metric=per_metric, days=days)
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
            "metric": "Overall health summary",
            "measurement": None,
            "field": None,
            "metric_class": None,
            "days": days,
            "ai_provider": provider,
            "summary": summary,
            "answer": ai_text or conversational_overall_summary(summary=summary, days=days),
        }

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
        "answer": ai_text or conversational_single_metric(metric=target.label, summary=summary, days=days),
    }
