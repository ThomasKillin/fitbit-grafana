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

## Derived Measurements (Phase 1 Target)

| Metric | Planned Influx Measurement | Planned Field(s) | Derived From | Status |
| --- | --- | --- | --- | --- |
| Cardio fitness / VO2 trend | `CardioFitness` | `vo2_estimate`, `source` | Fitbit cardio fitness source if available | Planned |
| Recovery score | `RecoveryScore` | `score`, component fields | HRV, RestingHR, Sleep Summary, prior load | Planned |
| Training load | `TrainingLoad` | `daily_load`, `acute_7d`, `chronic_28d`, `load_ratio` | HR zones + activity duration/minutes | Planned |
| Pipeline freshness | `PipelineHealth` | `last_success_epoch`, `minutes_since_success`, `record_count_last_run` | Fetch/write runtime signals | Planned |

---

## Implementation Notes

- Keep direct and derived panels physically separated in dashboard layout.
- Avoid mixing direct and derived series in the same panel unless comparison is the goal.
- If a panel mixes both, include the metric class in legend names (e.g. `Direct: RestingHR`, `Derived: RecoveryScore`).
