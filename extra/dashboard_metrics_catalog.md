# Dashboard Metrics Catalog

This file is the canonical list of metrics shown (or planned) in Grafana.
It explicitly distinguishes between:

- `Direct`: raw or near-raw measurements fetched from Fitbit APIs.
- `Derived`: computed metrics based on one or more direct measurements.

## Dashboard Section Convention

To reduce confusion in Grafana, group panels into two top-level sections:

- `Direct Measurements`
- `Derived Measurements`

Recommended naming style for panel titles:

- Direct panel title prefix: `[Direct]`
- Derived panel title prefix: `[Derived]`

---

## Direct Measurements (Current)

| Metric | Influx Measurement | Field(s) | Notes |
| --- | --- | --- | --- |
| Intraday heart rate | `HeartRate_Intraday` | `value` | High frequency HR samples |
| Intraday steps | `Steps_Intraday` | `value` | 1-minute step samples |
| Resting heart rate | `RestingHR` | `value` | Daily resting HR |
| Heart rate zones | `HR zones` | `Normal`, `Fat Burn`, `Cardio`, `Peak` | Includes active-zone minutes where available |
| HRV | `HRV` | `dailyRmssd`, `deepRmssd` | Daily recovery indicator |
| Sleep summary | `Sleep Summary` | sleep minute fields + efficiency | Main sleep rollup |
| Sleep stages | `Sleep Levels` | `level`, `duration_seconds` | Sleep timeline/stage depth |
| SpO2 daily | `SPO2` | `avg`, `max`, `min` | Daily oxygen summary |
| SpO2 intraday | `SPO2_Intraday` | `value` | Minute-level oxygen data |
| Breathing rate | `BreathingRate` | `value` | Daily breathing rate |
| Skin temperature variation | `Skin Temperature Variation` | `RelativeValue` | Nightly relative change |
| Activity minutes | `Activity Minutes` | active/sedentary minute fields | Daily activity split |
| Daily steps | `Total Steps` | `value` | Daily total |
| Daily distance | `distance` | `value` | Daily total |
| Daily calories | `calories` | `value` | Daily total |
| Weight | `weight` | `value` | Logged weight |
| BMI | `bmi` | `value` | Logged BMI |
| Device battery | `DeviceBatteryLevel` | `value` | Last synced battery |
| Activity records | `Activity Records` | duration/calorie/distance/steps fields | Recent activity list |
| GPS activity track | `GPS` | `lat`, `lon`, `speed_kph`, etc. | GPS-enabled activity tracks |

---

## Direct Measurements Explained (Plain English)

### Heart and Cardio

- `HeartRate_Intraday.value`: Your short-interval heart-rate readings during the day. Useful for spotting spikes, recovery after effort, and time patterns (for example, elevated afternoon HR).
- `RestingHR.value`: Your daily resting heart rate, usually one of the best simple markers of fitness and recovery trend over time.
- `HR zones.Normal`, `HR zones.Fat Burn`, `HR zones.Cardio`, `HR zones.Peak`: Time spent in each intensity zone. Useful for understanding training intensity distribution, not just total exercise time.
- `HRV.dailyRmssd`, `HRV.deepRmssd`: Heart-rate variability metrics (RMSSD). Higher values are often associated with better recovery/readiness, but personal baseline matters more than absolute values.

### Sleep and Recovery Inputs

- `Sleep Summary` fields (for example `minutesAsleep`, `minutesAwake`, `efficiency`): Daily rollup of main sleep session quality and quantity.
- `Sleep Levels.level`, `Sleep Levels.duration_seconds`: Sleep stage timeline (light/deep/REM/wake) and durations. Useful for stage balance and sleep fragmentation checks.

### Oxygen, Respiration, Temperature

- `SPO2.avg`, `SPO2.max`, `SPO2.min`: Daily blood oxygen summary statistics.
- `SPO2_Intraday.value`: Higher-frequency oxygen readings where available.
- `BreathingRate.value`: Daily breathing rate estimate, often useful as an illness/fatigue context signal.
- `Skin Temperature Variation.RelativeValue`: Nightly skin temperature change relative to your baseline, useful as a trend signal rather than a one-day diagnostic.

### Activity and Energy

- `Steps_Intraday.value`: Near real-time step accumulation during the day.
- `Total Steps.value`: End-of-day step total.
- `Activity Minutes` fields: Time split across sedentary/light/fairly/very active buckets.
- `distance.value`: Daily distance estimate.
- `calories.value`: Daily calories burned (resting + active, depending on Fitbit field semantics).
- `Activity Records` fields: Per-activity session details such as distance, duration, steps, and calories.
- `GPS` fields (`lat`, `lon`, `speed_kph`, etc.): Route and movement dynamics for GPS-tracked activities.

### Body and Device State

- `weight.value`: Logged body weight.
- `bmi.value`: Logged BMI (derived from height and weight by Fitbit).
- `DeviceBatteryLevel.value`: Last synced battery status for your wearable device.

---

## Derived Measurements (Current Phase 1)

| Metric | Influx Measurement | Field(s) | Derived From | Status |
| --- | --- | --- | --- | --- |
| Training load | `Derived TrainingLoad` | `daily_load`, `acute_7d`, `chronic_28d`, `load_ratio` | Latest HR zone durations | Implemented (feature-flagged) |
| Recovery score | `Derived RecoveryScore` | `score`, `sleep_component`, `hrv_component`, `rhr_component`, `strain_component` | Sleep Summary, HRV, RestingHR, HR zones | Implemented (feature-flagged) |
| Correlation signals | `Derived CorrelationSignals` | `rhr_delta`, `hrv_delta`, `sleep_minutes_delta`, `steps_delta` | Day-over-day differences from direct measurements | Implemented (feature-flagged) |
| Pipeline freshness | `Derived PipelineHealth` | `last_success_epoch`, `minutes_since_success`, `record_count_last_run` | Runtime fetch/write state | Implemented (default on) |
| Cardio fitness / VO2 trend | `Derived CardioFitness` | `vo2_estimate`, `source`, `confidence` | RestingHR-based heuristic (v1) | Implemented (feature-flagged) |

---

## Derived Measurements Explained (Plain English)

### `Derived TrainingLoad`

- What it is: A simple daily strain score representing how hard your day was from a cardiovascular intensity perspective.
- How it is derived (current v1 logic):
  - Uses `HR zones` points in the current processing batch.
  - Computes per-day weighted zone minutes:
    - `Normal * 1`
    - `Fat Burn * 2`
    - `Cardio * 3`
    - `Peak * 4`
  - Aggregates by day and computes rolling averages ending at `end_date_str`:
    - `acute_7d`: 7-day average load
    - `chronic_28d`: 28-day average load
    - `load_ratio = acute_7d / chronic_28d` (0 when chronic is 0)
  - Stores:
    - `daily_load`: load for `end_date_str` (or latest available day if missing).
    - `acute_7d`: computed 7-day rolling average.
    - `chronic_28d`: computed 28-day rolling average.
    - `load_ratio`: computed acute/chronic ratio.
- What it means: Higher value means more high-intensity time and therefore higher physiological strain for that day.
- How it is useful:
  - Track day-to-day training stress.
  - Compare load with sleep/recovery markers.
  - Eventually support overload detection once rolling windows are implemented.
- Caveats:
  - Rolling windows are based on data available in the current run; missing days count as zero.
  - It is a heuristic, not a medical or coaching-grade training impulse model.

### `Derived RecoveryScore`

- What it is: A 0-100 readiness-style composite score to summarize whether your body looks recovered.
- How it is derived (current v1 logic):
  - Inputs:
    - `Sleep Summary.minutesAsleep`
    - `HRV.dailyRmssd`
    - `RestingHR.value`
    - Daily load proxy from `HR zones` (same weighted load as above)
  - Components (each clamped to 0-100):
    - `sleep_component = (minutesAsleep / 480) * 100`
    - `hrv_component = (dailyRmssd / 60) * 100`
    - `rhr_component = ((80 - resting_hr) / 30) * 100`
      - If resting HR missing/non-positive, defaults to `50`.
    - `strain_component = 100 - (daily_load / 2)`
  - Final score:
    - `score = average(sleep_component, hrv_component, rhr_component, strain_component)`
- What it means:
  - Higher score suggests better recovery state based on sleep, autonomic signal (HRV), resting HR, and recent strain.
  - Lower score suggests accumulated strain and/or weak recovery signals.
- How it is useful:
  - Quick morning dashboard check for readiness trend.
  - Context for deciding hard vs easy training day.
  - Helpful when viewed as a rolling trend, not a single-point truth.
- Caveats:
  - v1 normalization constants (480 min sleep, HRV 60 ms, RHR 80/30 scaling) are generic heuristics.
  - Personal baselines differ widely; trend over time is more informative than absolute score.
  - Not a diagnostic or clinical metric.

### `Derived PipelineHealth`

- What it is: Operational telemetry for the data pipeline itself, not your physiology.
- How it is derived:
  - Written on each successful run.
  - `last_success_epoch`: current Unix timestamp when write completes.
  - `minutes_since_success`: currently set to `0.0` at write time.
  - `record_count_last_run`: number of direct records included in that run.
- What it means:
  - Confirms ingestion is alive and how much data was processed.
  - Supports alerting when expected updates stop.
- How it is useful:
  - Build Grafana alerts for stale pipeline.
  - Diagnose runs with unexpectedly low data volume.
- Caveats:
  - `minutes_since_success` is currently write-time only; elapsed-time behavior is better computed in Grafana query expressions.

### `Derived CardioFitness`

- What it is: A trend metric for estimated VO2/cardiorespiratory fitness (for example from Pixel Watch/Fitbit sources).
- How it is derived (current v1 logic):
  - Uses latest `RestingHR.value`.
  - Applies a simple trend heuristic:
    - `vo2_estimate = clamp(90 - (0.8 * resting_hr), 20, 70)`
  - Writes:
    - `source = heuristic_rhr`
    - `confidence = 0.4`
- What it means:
  - Higher estimated value generally indicates better aerobic capacity trend.
- How it is useful:
  - Long-term cardio trend tracking alongside training load and recovery metrics.
  - Gives a visible placeholder metric until device-native VO2 endpoints are integrated.
- Caveats:
  - v1 is intentionally heuristic and based only on resting HR.
  - Should be interpreted as trend guidance, not lab-grade VO2 max testing.
  - Future versions should prefer device/source-native VO2 estimates when available.

### `Derived CorrelationSignals`

- What it is: A compact set of day-over-day change values for key recovery and activity inputs.
- How it is derived (current v1 logic):
  - For each signal, compares the latest two available daily values in the current processing batch:
    - `RestingHR.value` -> `rhr_delta`
    - `HRV.dailyRmssd` -> `hrv_delta`
    - `Sleep Summary.minutesAsleep` -> `sleep_minutes_delta`
    - `Total Steps.value` -> `steps_delta`
  - Formula for each field:
    - `delta = latest_value - previous_value`
  - Writes only fields that have at least two daily values available.
- What it means:
  - Positive/negative deltas show direction and size of short-term change.
  - Example: negative `rhr_delta` and positive `hrv_delta` often suggest improved recovery conditions.
- How it is useful:
  - Fast signal panel for “what changed since yesterday”.
  - Correlation overlays against `Derived RecoveryScore` and `Derived TrainingLoad`.
  - Alerting on abrupt shifts (for example large negative sleep delta).
- Caveats:
  - It is a short-window feature, not a trend model.
  - If a signal has fewer than two daily values in the current batch, that field is omitted.

---

## Implementation Notes

- Keep direct and derived panels physically separated in dashboard layout.
- Avoid mixing direct and derived series in the same panel unless comparison is the goal.
- If a panel mixes both, include the metric class in legend names (e.g. `Direct: RestingHR`, `Derived: RecoveryScore`).
