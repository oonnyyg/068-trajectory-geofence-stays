import math

from .errors import InputError


def _finite_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _require(cond, msg):
    if not cond:
        raise InputError(msg)


def load_config(data):
    _require(isinstance(data, dict), "root: expected a JSON object")
    max_gap = data.get("max_gap_seconds")
    _require(
        isinstance(max_gap, int) and not isinstance(max_gap, bool) and max_gap > 0,
        "max_gap_seconds: expected a positive integer",
    )
    threshold = data.get("threshold_seconds")
    _require(
        _finite_number(threshold) and threshold >= 0,
        "threshold_seconds: expected a non-negative finite number",
    )
    fences = _load_fences(data.get("fences"))
    trajectories = _load_trajectories(data.get("trajectories"))
    return fences, trajectories, max_gap, float(threshold)


def _load_fences(raw):
    _require(isinstance(raw, list) and raw, "fences: expected a non-empty array")
    fences = []
    seen_ids = set()
    for i, item in enumerate(raw):
        loc = f"fences[{i}]"
        _require(isinstance(item, dict), f"{loc}: expected an object")
        fid = item.get("id")
        _require(isinstance(fid, str) and fid, f"{loc}.id: expected a non-empty string")
        _require(fid not in seen_ids, f"{loc}.id: duplicate fence id {fid!r}")
        seen_ids.add(fid)
        poly = item.get("polygon")
        _require(isinstance(poly, list) and len(poly) >= 3, f"{loc}.polygon: need at least 3 vertices")
        pts = []
        for j, pt in enumerate(poly):
            ploc = f"{loc}.polygon[{j}]"
            _require(
                isinstance(pt, list) and len(pt) == 2 and all(_finite_number(c) for c in pt),
                f"{ploc}: expected [x, y] with finite numbers",
            )
            pts.append((float(pt[0]), float(pt[1])))
        _check_polygon(pts, f"{loc}.polygon")
        fences.append({"id": fid, "polygon": pts})
    return fences


def _check_polygon(pts, loc):
    n = len(pts)
    seen = set()
    for j, p in enumerate(pts):
        _require(p not in seen, f"{loc}[{j}]: duplicate vertex {list(p)}")
        seen.add(p)
    for a in range(n):
        for b in range(a + 1, n):
            if b == a + 1 or (a == 0 and b == n - 1):
                continue
            if _segments_intersect(pts[a], pts[(a + 1) % n], pts[b], pts[(b + 1) % n]):
                raise InputError(f"{loc}: non-adjacent edges {a} and {b} intersect")
    twice = 0.0
    for j in range(n):
        x1, y1 = pts[j]
        x2, y2 = pts[(j + 1) % n]
        twice += x1 * y2 - x2 * y1
    _require(twice != 0.0, f"{loc}: polygon area is zero")


def _cross(o, a, b):
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _segments_intersect(p1, p2, p3, p4):
    d1 = _cross(p3, p4, p1)
    d2 = _cross(p3, p4, p2)
    d3 = _cross(p1, p2, p3)
    d4 = _cross(p1, p2, p4)
    if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)):
        return True
    if d1 == 0 and _on_segment(p3, p4, p1):
        return True
    if d2 == 0 and _on_segment(p3, p4, p2):
        return True
    if d3 == 0 and _on_segment(p1, p2, p3):
        return True
    if d4 == 0 and _on_segment(p1, p2, p4):
        return True
    return False


def _on_segment(a, b, p):
    return min(a[0], b[0]) <= p[0] <= max(a[0], b[0]) and min(a[1], b[1]) <= p[1] <= max(a[1], b[1])


def _load_trajectories(raw):
    _require(isinstance(raw, list) and raw, "trajectories: expected a non-empty array")
    tracks = []
    seen_ids = set()
    for i, item in enumerate(raw):
        loc = f"trajectories[{i}]"
        _require(isinstance(item, dict), f"{loc}: expected an object")
        oid = item.get("id")
        _require(isinstance(oid, str) and oid, f"{loc}.id: expected a non-empty string")
        _require(oid not in seen_ids, f"{loc}.id: duplicate object id {oid!r}")
        seen_ids.add(oid)
        pts = item.get("points")
        _require(isinstance(pts, list) and pts, f"{loc}.points: expected a non-empty array")
        out = []
        for j, pt in enumerate(pts):
            ploc = f"{loc}.points[{j}]"
            _require(
                isinstance(pt, list) and len(pt) == 3 and all(_finite_number(c) for c in pt),
                f"{ploc}: expected [t, x, y] with finite numbers",
            )
            t = pt[0]
            _require(float(t).is_integer(), f"{ploc}: time must be an integer number of seconds")
            out.append((int(t), float(pt[1]), float(pt[2])))
        for j in range(1, len(out)):
            _require(
                out[j][0] > out[j - 1][0],
                f"{loc}.points[{j}]: times must be strictly increasing per object"
                + (" (duplicate timestamp)" if out[j][0] == out[j - 1][0] else ""),
            )
        tracks.append({"id": oid, "points": out})
    return tracks
