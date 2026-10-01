# trajectory-geofence-stays

Analyze local trajectories against planar geofences using only the Python
standard library. For each object and fence the tool reports every
positive-duration stay interval and the accumulated seconds, for inspection
record cross-checking. No network access is used.

## Usage

```
python -m geofence_report <input.json> <output.json>
```

- Exit code `0`: report written to `<output.json>` (UTF-8 JSON).
- Exit code `1`: invalid input or unreadable file; a locatable reason is
  printed to stderr and **no output file is created**.
- Exit code `2`: wrong command-line arguments.

All coordinates share one planar unit; times are integer seconds.

## Input format

```json
{
  "max_gap_seconds": 60,
  "min_stay_seconds": 10,
  "fences": [
    {"id": "yard-A", "vertices": [[0, 0], [10, 0], [10, 10], [0, 10]]}
  ],
  "trajectories": [
    {"object_id": "truck-1",
     "points": [{"t": 0, "x": 2.0, "y": 2.0}, {"t": 30, "x": 8.0, "y": 8.0}]}
  ]
}
```

- `max_gap_seconds` (required): positive integer. If two consecutive
  observations of an object are more than this many seconds apart, the
  segment between them contributes nothing and any stay interval is broken.
- `min_stay_seconds` (optional, default `0`): non-negative number. Intervals
  whose duration reaches this threshold (equality counts) are additionally
  listed under `qualifying_intervals`.
- `fences`: each fence is a simple polygon with non-zero area. Vertices are
  not repeated (the first vertex is not repeated at the end). Duplicate
  vertices, non-finite coordinates, zero-area polygons and polygons whose
  non-adjacent edges intersect are rejected. Edges and vertices belong to
  the interior; each fence is evaluated independently.
- `trajectories`: points of each object must be sorted by strictly
  increasing integer time `t`. A duplicate or out-of-order timestamp rejects
  the whole input batch.

## Computation rules

- Between consecutive observations the object moves at constant velocity
  along a straight line (linear interpolation). The exact time slices where
  this segment lies inside the closed polygon are computed by clipping the
  segment against all polygon edges — endpoint containment alone is never
  used, so a segment with both endpoints outside can still contribute.
- Boundary contact of zero duration (touching a vertex or tangent) does not
  count as a stay.
- Intervals that touch in time are merged. Nothing is extrapolated beyond
  the first/last observation; a single-point trajectory accumulates zero.

## Output format

```json
{
  "interpolation": "linear: ...",
  "max_gap_seconds": 60,
  "min_stay_seconds": 10,
  "objects": [
    {"object_id": "truck-1",
     "fences": [
       {"fence_id": "yard-A",
        "intervals": [{"start": 0.0, "end": 30.0, "duration": 30.0}],
        "total_seconds": 30.0,
        "qualifying_intervals": [{"start": 0.0, "end": 30.0, "duration": 30.0}]}
     ]}
  ]
}
```

- Entries are sorted by `object_id`, then `fence_id`, then interval `start`.
- `interpolation` documents the interpolation rule.
- Times and durations are JSON numbers emitted with full `repr` precision
  (round-trippable double precision).

## Error reporting

Validation errors carry a JSON-path-like location, e.g.
`$.trajectories[0].points[1].t: times must be strictly increasing per
object; duplicate or out-of-order time 0`.

## Tests

```
python -m unittest discover -s tests
```

Covers concave-polygon crossing, along-edge movement, gap-induced interval
breaks, threshold equality, zero-duration touches, merging, sorting and
input validation failures.
