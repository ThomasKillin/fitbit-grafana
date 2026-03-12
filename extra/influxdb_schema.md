### Measurement: `Activity Minutes`

| Field Key | Field Type |
| --- | --- |
| `minutesFairlyActive` | integer |
| `minutesLightlyActive` | integer |
| `minutesSedentary` | integer |
| `minutesVeryActive` | integer |

| Tag Key | Tag Type |
| --- | --- |
| `Device` | string |

---

### Measurement: `Activity Records`

| Field Key | Field Type |
| --- | --- |
| `ActiveDuration` | integer |
| `AverageHeartRate` | integer |
| `calories` | integer |
| `distance` | float |
| `duration` | integer |
| `steps` | integer |

| Tag Key | Tag Type |
| --- | --- |
| `ActivityName` | string |

---

### Measurement: `BreathingRate`

| Field Key | Field Type |
| --- | --- |
| `value` | float |

| Tag Key | Tag Type |
| --- | --- |
| `Device` | string |

---

### Measurement: `DeviceBatteryLevel`

| Field Key | Field Type |
| --- | --- |
| `value` | float |

---

### Measurement: `Derived PipelineHealth`

| Field Key | Field Type |
| --- | --- |
| `last_success_epoch` | integer |
| `minutes_since_success` | float |
| `record_count_last_run` | integer |

| Tag Key | Tag Type |
| --- | --- |
| `Device` | string |
| `MetricClass` | string |

---

### Measurement: `Derived CardioFitness`

| Field Key | Field Type |
| --- | --- |
| `vo2_estimate` | float |
| `source` | string |
| `confidence` | float |

| Tag Key | Tag Type |
| --- | --- |
| `Device` | string |
| `MetricClass` | string |

---

### Measurement: `Derived CorrelationSignals`

| Field Key | Field Type |
| --- | --- |
| `rhr_delta` | float |
| `hrv_delta` | float |
| `sleep_minutes_delta` | float |
| `steps_delta` | float |

| Tag Key | Tag Type |
| --- | --- |
| `Device` | string |
| `MetricClass` | string |

---

### Measurement: `Derived CorrelationMatrix`

| Field Key | Field Type |
| --- | --- |
| `corr_rhr_vs_hrv_14d` | float |
| `corr_sleep_vs_recovery_14d` | float |
| `corr_steps_vs_recovery_14d` | float |
| `corr_load_vs_recovery_14d` | float |
| `corr_load_vs_recovery_lag1_14d` | float |
| `corr_load_vs_recovery_lag2_14d` | float |

| Tag Key | Tag Type |
| --- | --- |
| `Device` | string |
| `MetricClass` | string |

---

### Measurement: `Derived RecoveryScore`

| Field Key | Field Type |
| --- | --- |
| `score` | float |
| `sleep_component` | float |
| `hrv_component` | float |
| `rhr_component` | float |
| `strain_component` | float |
| `confidence` | float |
| `missing_inputs_count` | integer |

| Tag Key | Tag Type |
| --- | --- |
| `Device` | string |
| `MetricClass` | string |

---

### Measurement: `Derived ReadinessFlags`

| Field Key | Field Type |
| --- | --- |
| `readiness_score` | float |
| `readiness_confidence` | float |
| `missing_inputs_count` | integer |
| `overreaching_flag` | integer |
| `under_recovered_flag` | integer |
| `load_ratio` | float |

| Tag Key | Tag Type |
| --- | --- |
| `Device` | string |
| `MetricClass` | string |

---

### Measurement: `Derived TrendSignals`

| Field Key | Field Type |
| --- | --- |
| `slope_7d_rhr` | float |
| `slope_7d_hrv` | float |
| `slope_7d_sleep_minutes` | float |
| `slope_7d_steps` | float |
| `slope_7d_training_load` | float |
| `slope_7d_recovery_score` | float |

| Tag Key | Tag Type |
| --- | --- |
| `Device` | string |
| `MetricClass` | string |

---

### Measurement: `Derived ZScores`

| Field Key | Field Type |
| --- | --- |
| `z_rhr` | float |
| `z_hrv` | float |
| `z_sleep_minutes` | float |
| `z_steps` | float |
| `z_training_load` | float |
| `z_recovery_score` | float |

| Tag Key | Tag Type |
| --- | --- |
| `Device` | string |
| `MetricClass` | string |

---

### Measurement: `Derived TrainingLoad`

| Field Key | Field Type |
| --- | --- |
| `daily_load` | float |
| `acute_7d` | float |
| `chronic_28d` | float |
| `load_ratio` | float |

| Tag Key | Tag Type |
| --- | --- |
| `Device` | string |
| `MetricClass` | string |

---

### Measurement: `GPS`

| Field Key | Field Type |
| --- | --- |
| `altitude` | float |
| `distance` | float |
| `heart_rate` | integer |
| `lat` | float |
| `lon` | float |
| `speed_kph` | float |

| Tag Key | Tag Type |
| --- | --- |
| `ActivityID` | string |

---

### Measurement: `HR zones`

| Field Key | Field Type |
| --- | --- |
| `Cardio` | integer |
| `Fat Burn` | integer |
| `Normal` | integer |
| `Peak` | integer |

| Tag Key | Tag Type |
| --- | --- |
| `Device` | string |

---

### Measurement: `HRV`

| Field Key | Field Type |
| --- | --- |
| `dailyRmssd` | float |
| `deepRmssd` | float |

| Tag Key | Tag Type |
| --- | --- |
| `Device` | string |

---

### Measurement: `HeartRate_Intraday`

| Field Key | Field Type |
| --- | --- |
| `value` | integer |

| Tag Key | Tag Type |
| --- | --- |
| `Device` | string |

---

### Measurement: `RestingHR`

| Field Key | Field Type |
| --- | --- |
| `value` | integer |

| Tag Key | Tag Type |
| --- | --- |
| `Device` | string |

---

### Measurement: `SPO2`

| Field Key | Field Type |
| --- | --- |
| `avg` | float |
| `max` | float |
| `min` | float |

| Tag Key | Tag Type |
| --- | --- |
| `Device` | string |

---

### Measurement: `SPO2_Intraday`

| Field Key | Field Type |
| --- | --- |
| `value` | float |

| Tag Key | Tag Type |
| --- | --- |
| `Device` | string |

---

### Measurement: `Skin Temperature Variation`

| Field Key | Field Type |
| --- | --- |
| `RelativeValue` | float |

| Tag Key | Tag Type |
| --- | --- |
| `Device` | string |

---

### Measurement: `Sleep Levels`

| Field Key | Field Type |
| --- | --- |
| `duration_seconds` | integer |
| `level` | integer |

| Tag Key | Tag Type |
| --- | --- |
| `Device` | string |
| `isMainSleep` | string |

---

### Measurement: `Sleep Summary`

| Field Key | Field Type |
| --- | --- |
| `efficiency` | integer |
| `minutesAfterWakeup` | integer |
| `minutesAsleep` | integer |
| `minutesAwake` | integer |
| `minutesDeep` | integer |
| `minutesInBed` | integer |
| `minutesLight` | integer |
| `minutesREM` | integer |
| `minutesToFallAsleep` | integer |

| Tag Key | Tag Type |
| --- | --- |
| `Device` | string |
| `isMainSleep` | string |

---

### Measurement: `Steps_Intraday`

| Field Key | Field Type |
| --- | --- |
| `value` | integer |

| Tag Key | Tag Type |
| --- | --- |
| `Device` | string |

---

### Measurement: `Total Steps`

| Field Key | Field Type |
| --- | --- |
| `value` | float |

| Tag Key | Tag Type |
| --- | --- |
| `Device` | string |

---

### Measurement: `bmi`

| Field Key | Field Type |
| --- | --- |
| `value` | float |

| Tag Key | Tag Type |
| --- | --- |
| `Device` | string |

---

### Measurement: `calories`

| Field Key | Field Type |
| --- | --- |
| `value` | float |

| Tag Key | Tag Type |
| --- | --- |
| `Device` | string |

---

### Measurement: `distance`

| Field Key | Field Type |
| --- | --- |
| `value` | float |

| Tag Key | Tag Type |
| --- | --- |
| `Device` | string |

---

### Measurement: `weight`

| Field Key | Field Type |
| --- | --- |
| `value` | float |

| Tag Key | Tag Type |
| --- | --- |
| `Device` | string |

---

## Common Tag Convention

All points written by the current pipeline include:

- `MetricClass`: `Direct` for API-native measurements and `Derived` for computed measurements.

