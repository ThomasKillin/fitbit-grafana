# Grafana Panel Templates (Direct vs Derived)

Use these templates when creating new panels so dashboard intent stays clear:

- `Direct` panels only query points tagged `MetricClass='Direct'`
- `Derived` panels only query points tagged `MetricClass='Derived'`

Import-ready derived block dashboard JSON:

- [Grafana_Dashboard/Derived Metrics Block for influxdb-v1.json](../Grafana_Dashboard/Derived%20Metrics%20Block%20for%20influxdb-v1.json)
- [Grafana_Dashboard/Derived Metrics Block for influxdb-v2.json](../Grafana_Dashboard/Derived%20Metrics%20Block%20for%20influxdb-v2.json) (`Flux` datasource required)
- Improved full dashboard with fixes: [Grafana_Dashboard/Health Stats Dashboard for influxdb-v1 - improved.json](../Grafana_Dashboard/Health%20Stats%20Dashboard%20for%20influxdb-v1%20-%20improved.json)
- Alert templates for pipeline monitoring: [extra/grafana_alert_templates.md](./grafana_alert_templates.md)

## Compatibility Matrix

- If your Grafana datasource uses InfluxQL / InfluxDB v1:
  - Use `Derived Metrics Block for influxdb-v1.json`
  - Use `Health Stats Dashboard for influxdb-v1 - improved.json`
- If your Grafana datasource uses Flux / InfluxDB v2:
  - Use `Derived Metrics Block for influxdb-v2.json`

## Common Import Error

If you see this in Query Inspector:

`InfluxDB returned error: error parsing query: found FROM, expected identifier...`

It means Flux query text (starts with `from(bucket: ...)`) was sent to an InfluxQL datasource.

Fix:

1. Import the `influxdb-v1` dashboard JSON for InfluxQL datasources.
2. Or configure a Flux (InfluxDB v2) datasource and use the `influxdb-v2` JSON.

Quick usage:

1. Grafana -> Dashboards -> New -> Import.
2. Upload the JSON matching your datasource mode (v1/InfluxQL or v2/Flux).
3. Select your InfluxDB datasource for `DS_HEALTH_STATS` (v1) or `DS_INFLUXDB` (v2).
4. For v2 dashboards, pick the `bucket` variable after import.
5. Optional: copy the `Derived Measurements` row panels into your main dashboard.

---

## InfluxDB v1 (InfluxQL)

### Direct panel template

```sql
SELECT mean("value")
FROM "RestingHR"
WHERE $timeFilter
  AND "MetricClass"='Direct'
GROUP BY time($__interval) fill(null)
```

### Derived panel template

```sql
SELECT mean("score")
FROM "Derived RecoveryScore"
WHERE $timeFilter
  AND "MetricClass"='Derived'
GROUP BY time($__interval) fill(null)
```

### Derived training load template

```sql
SELECT mean("daily_load") AS "daily_load",
       mean("acute_7d") AS "acute_7d",
       mean("chronic_28d") AS "chronic_28d",
       mean("load_ratio") AS "load_ratio"
FROM "Derived TrainingLoad"
WHERE $timeFilter
  AND "MetricClass"='Derived'
GROUP BY time($__interval) fill(null)
```

### Derived correlation signals template

```sql
SELECT mean("rhr_delta") AS "rhr_delta",
       mean("hrv_delta") AS "hrv_delta",
       mean("sleep_minutes_delta") AS "sleep_minutes_delta",
       mean("steps_delta") AS "steps_delta"
FROM "Derived CorrelationSignals"
WHERE $timeFilter
  AND "MetricClass"='Derived'
GROUP BY time($__interval) fill(null)
```

### Derived correlation matrix template

```sql
SELECT mean("corr_load_vs_recovery_14d") AS "corr_load_vs_recovery_14d",
       mean("corr_load_vs_recovery_lag1_14d") AS "corr_load_vs_recovery_lag1_14d",
       mean("corr_load_vs_recovery_lag2_14d") AS "corr_load_vs_recovery_lag2_14d"
FROM "Derived CorrelationMatrix"
WHERE $timeFilter
  AND "MetricClass"='Derived'
GROUP BY time($__interval) fill(null)
```

### Derived z-score template

```sql
SELECT mean("z_rhr") AS "z_rhr",
       mean("z_hrv") AS "z_hrv",
       mean("z_recovery_score") AS "z_recovery_score"
FROM "Derived ZScores"
WHERE $timeFilter
  AND "MetricClass"='Derived'
GROUP BY time($__interval) fill(null)
```

### Derived trend signals template

```sql
SELECT mean("slope_7d_rhr") AS "slope_7d_rhr",
       mean("slope_7d_hrv") AS "slope_7d_hrv",
       mean("slope_7d_recovery_score") AS "slope_7d_recovery_score"
FROM "Derived TrendSignals"
WHERE $timeFilter
  AND "MetricClass"='Derived'
GROUP BY time($__interval) fill(null)
```

### Derived readiness flags template

```sql
SELECT mean("readiness_score") AS "readiness_score",
       mean("readiness_confidence") AS "readiness_confidence",
       mean("overreaching_flag") AS "overreaching_flag",
       mean("under_recovered_flag") AS "under_recovered_flag"
FROM "Derived ReadinessFlags"
WHERE $timeFilter
  AND "MetricClass"='Derived'
GROUP BY time($__interval) fill(null)
```

---

## InfluxDB v2 (Flux)

### Direct panel template

```flux
from(bucket: v.defaultBucket)
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) =>
      r._measurement == "RestingHR" and
      r._field == "value" and
      r.MetricClass == "Direct")
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
  |> yield(name: "mean")
```

### Derived panel template

```flux
from(bucket: v.defaultBucket)
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) =>
      r._measurement == "Derived RecoveryScore" and
      r._field == "score" and
      r.MetricClass == "Derived")
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
  |> yield(name: "mean")
```

---

## Suggested Panel Set (Phase 1)

- `[Derived] Recovery Score (score)`
- `[Derived] Training Load (daily_load, acute_7d, chronic_28d)`
- `[Derived] Load Ratio (load_ratio)`
- `[Derived] Cardio Fitness (vo2_estimate)`
- `[Derived] Correlation Signals (rhr_delta, hrv_delta, sleep_minutes_delta, steps_delta)`
- `[Derived] Correlation Matrix (14d + lagged)`
- `[Derived] Z-Score Anomalies`
- `[Derived] Trend Signals (7d slopes)`
- `[Derived] Readiness Flags`
- `[Derived] Pipeline Health (record_count_last_run)`

---

## Variable Helper (optional)

Create a dashboard variable called `metric_class`:

- Type: `Custom`
- Values: `Direct,Derived`

Then you can parameterize queries with:

- InfluxQL: `AND "MetricClass"='$metric_class'`
- Flux: `r.MetricClass == "${metric_class}"`
