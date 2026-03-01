# Grafana Panel Templates (Direct vs Derived)

Use these templates when creating new panels so dashboard intent stays clear:

- `Direct` panels only query points tagged `MetricClass='Direct'`
- `Derived` panels only query points tagged `MetricClass='Derived'`

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
- `[Derived] Pipeline Health (record_count_last_run)`

---

## Variable Helper (optional)

Create a dashboard variable called `metric_class`:

- Type: `Custom`
- Values: `Direct,Derived`

Then you can parameterize queries with:

- InfluxQL: `AND "MetricClass"='$metric_class'`
- Flux: `r.MetricClass == "${metric_class}"`
