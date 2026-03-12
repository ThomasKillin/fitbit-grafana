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
