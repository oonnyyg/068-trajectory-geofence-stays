from fractions import Fraction

from .geometry import segment_inside_intervals
from .validate import load_config

INTERPOLATION_RULE = (
    "Between consecutive observations an object moves at constant velocity along "
    "the straight segment joining them; sub-segments inside a fence (boundary "
    "included) are found by exact rational interpolation. Segments separated by "
    "more than max_gap_seconds contribute nothing and break intervals. No "
    "extrapolation before the first or after the last observation; zero-duration "
    "touches are not stays."
)


def _to_number(frac):
    if frac.denominator == 1:
        return int(frac)
    return float(frac)


def _track_fence_intervals(points, poly, max_gap):
    merged = []
    for (t0, x0, y0), (t1, x1, y1) in zip(points, points[1:]):
        if t1 - t0 > max_gap:
            continue
        p0 = (Fraction(x0), Fraction(y0))
        p1 = (Fraction(x1), Fraction(y1))
        span = t1 - t0
        for ua, ub in segment_inside_intervals(p0, p1, poly):
            start = Fraction(t0) + ua * span
            end = Fraction(t0) + ub * span
            if merged and merged[-1][1] == start:
                merged[-1][1] = end
            else:
                merged.append([start, end])
    return merged


def build_report(data):
    fences, tracks, max_gap, threshold = load_config(data)
    polys = [(f["id"], [(Fraction(x), Fraction(y)) for x, y in f["polygon"]]) for f in fences]
    objects = []
    for track in sorted(tracks, key=lambda t: t["id"]):
        fence_entries = []
        for fid, poly in sorted(polys, key=lambda fp: fp[0]):
            raw = _track_fence_intervals(track["points"], poly, max_gap)
            stays = [(s, e) for s, e in raw if e - s > 0]
            intervals = []
            for start, end in stays:
                intervals.append(
                    {
                        "start": _to_number(start),
                        "end": _to_number(end),
                        "duration_seconds": _to_number(end - start),
                    }
                )
            total = sum((end - start for start, end in stays), Fraction(0))
            threshold_f = Fraction(str(threshold))
            qualifying = [
                iv
                for iv, (start, end) in zip(intervals, stays)
                if end - start >= threshold_f
            ]
            fence_entries.append(
                {
                    "fence_id": fid,
                    "intervals": intervals,
                    "total_seconds": _to_number(total),
                    "qualifying_intervals": qualifying,
                }
            )
        objects.append({"object_id": track["id"], "fences": fence_entries})
    return {
        "interpolation_rule": INTERPOLATION_RULE,
        "max_gap_seconds": max_gap,
        "threshold_seconds": _to_number(Fraction(str(threshold))),
        "objects": objects,
    }
