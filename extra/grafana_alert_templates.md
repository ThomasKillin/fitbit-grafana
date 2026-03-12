# Grafana Alert Templates (Pipeline Health)

These templates use `Derived PipelineHealth` so you can detect ingestion failures early.

Current behavior note:
- `minutes_since_success` reflects elapsed minutes since the previous successful write in the current process.
- After service restarts, the first write resets `minutes_since_success` to `0`.
- For robust alerting, still prefer query-window presence/count logic.

---

## Alert 1: No Pipeline Updates (v1 InfluxQL)

Purpose:
- Fire when no `Derived PipelineHealth` points arrive in the last 2 hours.

Query (A):

```sql
SELECT count("record_count_last_run")
FROM "Derived PipelineHealth"
WHERE $timeFilter
  AND "MetricClass"='Derived'
```

Suggested alert rule settings:
- Time range: `now-2h` to `now`
- Reduce: `last()`
- Condition: `A < 1`
- No data state: `Alerting`
- Evaluate every: `5m`
- For: `10m`

---

## Alert 2: Low Records Per Run (v1 InfluxQL)

Purpose:
- Fire when recent runs are present but have unusually low ingestion volume.

Query (A):

```sql
SELECT mean("record_count_last_run")
FROM "Derived PipelineHealth"
WHERE $timeFilter
  AND "MetricClass"='Derived'
GROUP BY time(15m) fill(null)
```

Suggested alert rule settings:
- Time range: `now-2h` to `now`
- Reduce: `last()`
- Condition: `A < 100` (tune threshold to your normal baseline)
- No data state: `NoData` or `Alerting` (depends on preference)
- Evaluate every: `5m`
- For: `15m`

---

## Alert 1: No Pipeline Updates (v2 Flux)

Query (A):

```flux
from(bucket: v.defaultBucket)
  |> range(start: -2h)
  |> filter(fn: (r) =>
      r._measurement == "Derived PipelineHealth" and
      r._field == "record_count_last_run" and
      r.MetricClass == "Derived")
  |> count()
```

Suggested alert rule settings:
- Reduce: `last()`
- Condition: `A < 1`
- No data state: `Alerting`
- Evaluate every: `5m`
- For: `10m`

---

## Alert 2: Low Records Per Run (v2 Flux)

Query (A):

```flux
from(bucket: v.defaultBucket)
  |> range(start: -2h)
  |> filter(fn: (r) =>
      r._measurement == "Derived PipelineHealth" and
      r._field == "record_count_last_run" and
      r.MetricClass == "Derived")
  |> aggregateWindow(every: 15m, fn: mean, createEmpty: false)
  |> tail(n: 1)
```

Suggested alert rule settings:
- Reduce: `last()`
- Condition: `A < 100` (tune to your baseline)
- Evaluate every: `5m`
- For: `15m`

---

## Practical Threshold Tuning

Use your own ingestion profile:
- Stable daily mode often has lower `record_count_last_run` than historical backfill mode.
- Start with warnings first (higher threshold), then tighten after observing 1-2 weeks.

Recommended severity split:
- Warning: no updates for `> 30m`
- Critical: no updates for `> 2h`

---

## Alert 3: Overreaching Risk (v1 InfluxQL)

```sql
SELECT mean("overreaching_flag")
FROM "Derived ReadinessFlags"
WHERE $timeFilter
  AND "MetricClass"='Derived'
GROUP BY time(15m) fill(null)
```

Suggested rule:
- Time range: `now-6h` to `now`
- Reduce: `last()`
- Condition: `A >= 1`
- Evaluate every: `5m`
- For: `10m`

## Alert 4: Under-Recovered Risk (v1 InfluxQL)

```sql
SELECT mean("under_recovered_flag")
FROM "Derived ReadinessFlags"
WHERE $timeFilter
  AND "MetricClass"='Derived'
GROUP BY time(15m) fill(null)
```

Suggested rule:
- Time range: `now-6h` to `now`
- Reduce: `last()`
- Condition: `A >= 1`
- Evaluate every: `5m`
- For: `10m`

## Alert 3: Overreaching Risk (v2 Flux)

```flux
from(bucket: v.defaultBucket)
  |> range(start: -6h)
  |> filter(fn: (r) =>
      r._measurement == "Derived ReadinessFlags" and
      r._field == "overreaching_flag" and
      r.MetricClass == "Derived")
  |> aggregateWindow(every: 15m, fn: mean, createEmpty: false)
  |> tail(n: 1)
```

Suggested rule:
- Reduce: `last()`
- Condition: `A >= 1`
- Evaluate every: `5m`
- For: `10m`

## Alert 4: Under-Recovered Risk (v2 Flux)

```flux
from(bucket: v.defaultBucket)
  |> range(start: -6h)
  |> filter(fn: (r) =>
      r._measurement == "Derived ReadinessFlags" and
      r._field == "under_recovered_flag" and
      r.MetricClass == "Derived")
  |> aggregateWindow(every: 15m, fn: mean, createEmpty: false)
  |> tail(n: 1)
```

Suggested rule:
- Reduce: `last()`
- Condition: `A >= 1`
- Evaluate every: `5m`
- For: `10m`

---

## Alert 5: High Z-Score Anomaly (v1 InfluxQL)

Purpose:
- Detect unusual physiology/movement spikes using 28-day z-scores.

```sql
SELECT max("z_rhr") AS "z_rhr",
       max("z_hrv") AS "z_hrv",
       max("z_recovery_score") AS "z_recovery_score"
FROM "Derived ZScores"
WHERE $timeFilter
  AND "MetricClass"='Derived'
GROUP BY time(30m) fill(null)
```

Suggested rule:
- Time range: `now-24h` to `now`
- Reduce: `last()`
- Condition: `abs(A) >= 2` (or split into per-series rules)
- Evaluate every: `10m`
- For: `15m`

## Alert 6: Negative Recovery Trend (v1 InfluxQL)

Purpose:
- Detect sustained deterioration in 7-day trend slope.

```sql
SELECT mean("slope_7d_recovery_score") AS "slope_7d_recovery_score"
FROM "Derived TrendSignals"
WHERE $timeFilter
  AND "MetricClass"='Derived'
GROUP BY time(30m) fill(null)
```

Suggested rule:
- Time range: `now-24h` to `now`
- Reduce: `last()`
- Condition: `A < -0.2` (tune to baseline)
- Evaluate every: `10m`
- For: `20m`

## Alert 7: Correlation Drift (Load vs Recovery Lagged) (v1 InfluxQL)

Purpose:
- Detect breakdown between load and delayed recovery response.

```sql
SELECT mean("corr_load_vs_recovery_lag1_14d") AS "lag1",
       mean("corr_load_vs_recovery_lag2_14d") AS "lag2"
FROM "Derived CorrelationMatrix"
WHERE $timeFilter
  AND "MetricClass"='Derived'
GROUP BY time(30m) fill(null)
```

Suggested rule:
- Time range: `now-7d` to `now`
- Reduce: `last()`
- Condition: `A < 0.1` (apply separately on `lag1`/`lag2`)
- Evaluate every: `30m`
- For: `1h`

---

## Alert 5: High Z-Score Anomaly (v2 Flux)

```flux
from(bucket: v.defaultBucket)
  |> range(start: -24h)
  |> filter(fn: (r) =>
      r._measurement == "Derived ZScores" and
      r.MetricClass == "Derived" and
      (r._field == "z_rhr" or r._field == "z_hrv" or r._field == "z_recovery_score"))
  |> aggregateWindow(every: 30m, fn: max, createEmpty: false)
  |> tail(n: 1)
```

Suggested rule:
- Reduce: `last()`
- Condition: `abs(A) >= 2`
- Evaluate every: `10m`
- For: `15m`

## Alert 6: Negative Recovery Trend (v2 Flux)

```flux
from(bucket: v.defaultBucket)
  |> range(start: -24h)
  |> filter(fn: (r) =>
      r._measurement == "Derived TrendSignals" and
      r._field == "slope_7d_recovery_score" and
      r.MetricClass == "Derived")
  |> aggregateWindow(every: 30m, fn: mean, createEmpty: false)
  |> tail(n: 1)
```

Suggested rule:
- Reduce: `last()`
- Condition: `A < -0.2`
- Evaluate every: `10m`
- For: `20m`

## Alert 7: Correlation Drift (Load vs Recovery Lagged) (v2 Flux)

```flux
from(bucket: v.defaultBucket)
  |> range(start: -7d)
  |> filter(fn: (r) =>
      r._measurement == "Derived CorrelationMatrix" and
      r.MetricClass == "Derived" and
      (r._field == "corr_load_vs_recovery_lag1_14d" or r._field == "corr_load_vs_recovery_lag2_14d"))
  |> aggregateWindow(every: 30m, fn: mean, createEmpty: false)
  |> tail(n: 1)
```

Suggested rule:
- Reduce: `last()`
- Condition: `A < 0.1`
- Evaluate every: `30m`
- For: `1h`
