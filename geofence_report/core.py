"""Input validation and stay-interval computation."""

import json
import math

from .geometry import clip_segment_inside, segments_properly_intersect

MERGE_EPS = 1e-9


class InputError(ValueError):
    """Raised for invalid input; message carries a locatable path."""


def load_input(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        raise InputError(f"$: invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise InputError("$: top-level value must be a JSON object")
    return data


def _is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _finite_number(v, path):
    if not _is_number(v) or not math.isfinite(v):
        raise InputError(f"{path}: expected a finite number, got {v!r}")
    return float(v)


def _validate_polygon(vertices, path):
    if not isinstance(vertices, list) or len(vertices) < 3:
        raise InputError(f"{path}: polygon needs at least 3 vertices")
    pts = []
    for i, v in enumerate(vertices):
        if not isinstance(v, list) or len(v) != 2:
            raise InputError(f"{path}[{i}]: vertex must be [x, y]")
        pts.append((_finite_number(v[0], f"{path}[{i}][0]"),
                    _finite_number(v[1], f"{path}[{i}][1]")))
    seen = set()
    for i, p in enumerate(pts):
        if p in seen:
            raise InputError(f"{path}[{i}]: duplicate vertex {list(p)!r}")
        seen.add(p)
    n = len(pts)
    edges = [(pts[i], pts[(i + 1) % n]) for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            if j == i + 1 or (i == 0 and j == n - 1):
                continue  # adjacent edges share exactly one vertex
            if segments_properly_intersect(edges[i][0], edges[i][1],
                                           edges[j][0], edges[j][1]):
                raise InputError(
                    f"{path}: non-adjacent edges {i} and {j} intersect")
    area2 = 0.0
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        area2 += x1 * y2 - x2 * y1
    if area2 == 0.0:
        raise InputError(f"{path}: polygon area is zero")
    return pts


def _validate_points(points, path):
    if not isinstance(points, list):
        raise InputError(f"{path}: points must be a list")
    out = []
    prev_t = None
    for i, rec in enumerate(points):
        p = f"{path}[{i}]"
        if not isinstance(rec, dict):
            raise InputError(f"{p}: point must be an object with t, x, y")
        t = rec.get("t")
        if not isinstance(t, int) or isinstance(t, bool):
            raise InputError(f"{p}.t: time must be an integer number of seconds")
        x = _finite_number(rec.get("x"), f"{p}.x")
        y = _finite_number(rec.get("y"), f"{p}.y")
        if prev_t is not None and t <= prev_t:
            raise InputError(
                f"{p}.t: times must be strictly increasing per object; "
                f"duplicate or out-of-order time {t}")
        prev_t = t
        out.append((t, (x, y)))
    return out


def validate_config(data):
    gap = data.get("max_gap_seconds")
    if not isinstance(gap, int) or isinstance(gap, bool) or gap <= 0:
        raise InputError("$.max_gap_seconds: must be a positive integer")
    threshold = data.get("min_stay_seconds", 0)
    if not _is_number(threshold) or not math.isfinite(threshold) or threshold < 0:
        raise InputError("$.min_stay_seconds: must be a non-negative number")
    fences_raw = data.get("fences")
    if not isinstance(fences_raw, list):
        raise InputError("$.fences: must be a list")
    fences = []
    for i, f in enumerate(fences_raw):
        path = f"$.fences[{i}]"
        if not isinstance(f, dict) or not isinstance(f.get("id"), str):
            raise InputError(f"{path}: fence must be an object with string 'id'")
        fences.append((f["id"], _validate_polygon(f.get("vertices"),
                                                  f"{path}.vertices")))
    trajs_raw = data.get("trajectories")
    if not isinstance(trajs_raw, list):
        raise InputError("$.trajectories: must be a list")
    trajectories = []
    for i, tr in enumerate(trajs_raw):
        path = f"$.trajectories[{i}]"
        if not isinstance(tr, dict) or not isinstance(tr.get("object_id"), str):
            raise InputError(
                f"{path}: trajectory must be an object with string 'object_id'")
        pts = _validate_points(tr.get("points"), f"{path}.points")
        trajectories.append((tr["object_id"], pts))
    return gap, float(threshold), fences, trajectories


def _segment_intervals(t0, p0, t1, p1, poly):
    """Inside time intervals for one constant-velocity segment."""
    span = t1 - t0
    out = []
    for s0, s1 in clip_segment_inside(p0, p1, poly):
        a = t0 if s0 == 0.0 else t0 + s0 * span
        b = t1 if s1 == 1.0 else t0 + s1 * span
        if b - a > MERGE_EPS:
            out.append((a, b))
    return out


def _object_fence_intervals(points, poly, max_gap):
    raw = []
    for (t0, p0), (t1, p1) in zip(points, points[1:]):
        if t1 - t0 > max_gap:
            continue  # gap too large: no interpolation, breaks the interval
        raw.extend(_segment_intervals(t0, p0, t1, p1, poly))
    raw.sort()
    merged = []
    for a, b in raw:
        if merged and a <= merged[-1][1] + MERGE_EPS:
            last = merged[-1]
            merged[-1] = (last[0], max(last[1], b))
        else:
            merged.append((a, b))
    return merged


def build_report(data):
    """Validate input and produce the report dict."""
    max_gap, threshold, fences, trajectories = validate_config(data)
    objects = []
    for object_id, points in sorted(trajectories, key=lambda kv: kv[0]):
        fence_entries = []
        for fence_id, poly in sorted(fences, key=lambda kv: kv[0]):
            intervals = _object_fence_intervals(points, poly, max_gap)
            iv_list = [
                {"start": a, "end": b, "duration": b - a} for a, b in intervals
            ]
            qualifying = [iv for iv in iv_list
                          if iv["duration"] >= threshold]
            fence_entries.append({
                "fence_id": fence_id,
                "intervals": iv_list,
                "total_seconds": sum(iv["duration"] for iv in iv_list),
                "qualifying_intervals": qualifying,
            })
        objects.append({"object_id": object_id, "fences": fence_entries})
    return {
        "interpolation": (
            "linear: consecutive observations are joined by constant-velocity "
            "straight-line motion; intervals where the moving point lies "
            "inside the closed polygon (boundary included) are computed "
            "exactly, not inferred from endpoint containment alone"
        ),
        "max_gap_seconds": max_gap,
        "min_stay_seconds": threshold,
        "objects": objects,
    }
