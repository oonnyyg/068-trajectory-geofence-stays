# trajectory-geofence-stays

Analyze local trajectories against planar geofences and report stay intervals and
accumulated durations per object, for inspection-record reconciliation.
Standard library only, no network access.

## Usage

```
python -m geofence_report <input.json> <output.json>
```

On invalid input the tool prints a located reason to stderr, exits with a
non-zero status, and does not create the output file.

## Input format

```json
{
  "fences": [{"id": "yard-a", "polygon": [[0, 0], [10, 0], [10, 10], [0, 10]]}],
  "trajectories": [{"id": "worker-1", "points": [[0, 2, 2], [4, 8, 8]]}],
  "max_gap_seconds": 30,
  "threshold_seconds": 60
}
```

- `fences`: non-empty array. Each fence has a unique string `id` and a
  `polygon` of at least 3 `[x, y]` vertices in one shared planar unit. The
  polygon must be simple with non-zero area: duplicate vertices (including a
  repeated first/last vertex) and intersecting non-adjacent edges are rejected.
- `trajectories`: non-empty array. Each object has a unique string `id` and
  `points` of `[t, x, y]` with integer second timestamps, strictly increasing
  per object; a duplicate timestamp rejects the whole batch.
- `max_gap_seconds`: positive integer. Segments between observations farther
  apart than this contribute nothing and break intervals.
- `threshold_seconds`: non-negative number. Intervals whose duration reaches
  this value are also listed under `qualifying_intervals`.

All coordinates must be finite numbers.

## Interpolation rule

Between consecutive observations an object moves at constant velocity along
the straight segment joining them. Sub-segments inside a fence (edges and
vertices count as inside) are computed by exact rational interpolation, not by
endpoint inside/outside tests. Each fence is evaluated independently.
Zero-duration touches are not stays. Time-adjacent inside pieces merge into one
interval. Nothing is extrapolated before the first or after the last
observation; a single-point trajectory accumulates zero.

## Output format

```json
{
  "interpolation_rule": "...",
  "max_gap_seconds": 30,
  "threshold_seconds": 60,
  "objects": [
    {
      "object_id": "worker-1",
      "fences": [
        {
          "fence_id": "yard-a",
          "intervals": [{"start": 0, "end": 4, "duration_seconds": 4}],
          "total_seconds": 4,
          "qualifying_intervals": []
        }
      ]
    }
  ]
}
```

Objects, fences, and intervals are sorted by object id, fence id, and start
time. Times and durations are integers when integral, otherwise full-precision
floats. `intervals` lists every positive-duration stay; `total_seconds` sums
them; `qualifying_intervals` repeats the intervals meeting the threshold.

## Tests

```
python -m unittest discover -s tests
```
