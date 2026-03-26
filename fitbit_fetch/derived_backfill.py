"""Startup auto-backfill helpers for derived metrics."""

from datetime import datetime, timedelta

from fitbit_fetch.derived_metrics import build_derived_points


DERIVED_BACKFILL_DIRECT_MEASUREMENTS = [
    "HR zones",
    "Sleep Summary",
    "HRV",
    "RestingHR",
    "Total Steps",
    "CardioFitness",
]
DERIVED_BACKFILL_CONTEXT_DAYS = 35


def compute_backfill_dates(*, end_date_str: str, requested_days: int, max_days_per_run: int) -> list[str]:
    if requested_days <= 0 or max_days_per_run <= 0:
        return []
    days = min(requested_days, max_days_per_run)
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
    start_date = end_date - timedelta(days=days - 1)
    return [
        (start_date + timedelta(days=offset)).isoformat()
        for offset in range((end_date - start_date).days + 1)
    ]


def run_derived_startup_auto_backfill(
    *,
    enabled: bool,
    influx_writer,
    logger,
    devicename: str,
    end_date_str: str,
    requested_days: int,
    max_days_per_run: int,
    enable_recovery_score: bool,
    enable_training_load: bool,
    enable_cardio_fitness: bool,
    enable_correlation_signals: bool,
    enable_correlation_matrix: bool,
    enable_zscores: bool,
    enable_trend_signals: bool,
    enable_readiness_flags: bool,
    sleep_fn,
    inter_day_sleep_seconds: float = 0.2,
) -> None:
    if not enabled:
        logger.info("Derived auto-backfill disabled")
        return

    derived_toggles_enabled = any(
        [
            enable_recovery_score,
            enable_training_load,
            enable_cardio_fitness,
            enable_correlation_signals,
            enable_correlation_matrix,
            enable_zscores,
            enable_trend_signals,
            enable_readiness_flags,
        ]
    )
    if not derived_toggles_enabled:
        logger.info("Derived auto-backfill skipped because all derived metric toggles are disabled")
        return

    date_list = compute_backfill_dates(
        end_date_str=end_date_str,
        requested_days=requested_days,
        max_days_per_run=max_days_per_run,
    )
    if not date_list:
        logger.info("Derived auto-backfill skipped because date window is empty")
        return

    logger.info(
        "Starting derived auto-backfill for %s days ending %s",
        len(date_list),
        end_date_str,
    )
    processed = 0
    skipped = 0
    written = 0

    for day_str in date_list:
        day_date = datetime.strptime(day_str, "%Y-%m-%d").date()
        context_start = (day_date - timedelta(days=DERIVED_BACKFILL_CONTEXT_DAYS - 1)).isoformat()
        direct_points = influx_writer.fetch_direct_points_for_range(
            start_day_str=context_start,
            end_day_str=day_str,
            measurements=DERIVED_BACKFILL_DIRECT_MEASUREMENTS,
        )
        if not direct_points:
            skipped += 1
            logger.debug("Derived auto-backfill skipped %s (no direct points)", day_str)
            continue

        derived_points = build_derived_points(
            points=direct_points,
            devicename=devicename,
            end_date_str=day_str,
            enable_pipeline_health=False,
            enable_recovery_score=enable_recovery_score,
            enable_training_load=enable_training_load,
            enable_cardio_fitness=enable_cardio_fitness,
            enable_correlation_signals=enable_correlation_signals,
            enable_correlation_matrix=enable_correlation_matrix,
            enable_zscores=enable_zscores,
            enable_trend_signals=enable_trend_signals,
            enable_readiness_flags=enable_readiness_flags,
            pipeline_previous_success_epoch=None,
        )
        if not derived_points:
            skipped += 1
            logger.debug("Derived auto-backfill skipped %s (insufficient derived inputs)", day_str)
            continue

        influx_writer.write_points(derived_points)
        processed += 1
        written += len(derived_points)
        sleep_fn(inter_day_sleep_seconds)

    logger.info(
        "Derived auto-backfill complete: processed_days=%s skipped_days=%s derived_points_written=%s",
        processed,
        skipped,
        written,
    )
