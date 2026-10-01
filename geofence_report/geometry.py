"""Planar geometry helpers: closed polygons, boundary counts as inside."""

EPS = 1e-12


def cross(a, b, c):
    """Cross product of vectors AB and AC."""
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(p, a, b):
    """True if p lies on closed segment ab (assumes collinearity check inside)."""
    if abs(cross(a, b, p)) > EPS * max(1.0, abs(b[0] - a[0]) + abs(b[1] - a[1])):
        return False
    return (min(a[0], b[0]) - EPS <= p[0] <= max(a[0], b[0]) + EPS and
            min(a[1], b[1]) - EPS <= p[1] <= max(a[1], b[1]) + EPS)


def point_in_polygon(p, poly):
    """Closed point-in-polygon test: boundary counts as inside."""
    n = len(poly)
    for i in range(n):
        if _on_segment(p, poly[i], poly[(i + 1) % n]):
            return True
    x, y = p
    inside = False
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xint = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if xint > x:
                inside = not inside
    return inside


def segments_properly_intersect(a, b, c, d):
    """True if closed segments ab and cd share any point."""
    d1 = cross(c, d, a)
    d2 = cross(c, d, b)
    d3 = cross(a, b, c)
    d4 = cross(a, b, d)
    if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)):
        return True
    if d1 == 0 and _on_segment(a, c, d):
        return True
    if d2 == 0 and _on_segment(b, c, d):
        return True
    if d3 == 0 and _on_segment(c, a, b):
        return True
    if d4 == 0 and _on_segment(d, a, b):
        return True
    return False


def clip_segment_inside(p0, p1, poly):
    """Return sorted list of (s0, s1) parameter sub-intervals of the segment
    p(s) = p0 + s*(p1-p0), s in [0,1], where p(s) is inside the closed polygon.
    Zero-length intervals are omitted."""
    dx = p1[0] - p0[0]
    dy = p1[1] - p0[1]
    len2 = dx * dx + dy * dy
    if len2 == 0.0:
        return []
    cuts = {0.0, 1.0}
    n = len(poly)
    for i in range(n):
        a = poly[i]
        b = poly[(i + 1) % n]
        ex = b[0] - a[0]
        ey = b[1] - a[1]
        denom = dx * ey - dy * ex
        if denom != 0.0:
            s = ((a[0] - p0[0]) * ey - (a[1] - p0[1]) * ex) / denom
            u = ((a[0] - p0[0]) * dy - (a[1] - p0[1]) * dx) / denom
            if 0.0 <= s <= 1.0 and 0.0 <= u <= 1.0:
                cuts.add(min(1.0, max(0.0, s)))
        else:
            # Parallel: if collinear, the edge endpoints split the segment.
            if dx * (a[1] - p0[1]) - dy * (a[0] - p0[0]) == 0.0:
                for q in (a, b):
                    s = ((q[0] - p0[0]) * dx + (q[1] - p0[1]) * dy) / len2
                    if 0.0 < s < 1.0:
                        cuts.add(s)
    ordered = sorted(cuts)
    out = []
    for lo, hi in zip(ordered, ordered[1:]):
        if hi - lo <= EPS:
            continue
        mid = ((p0[0] + (lo + hi) * 0.5 * dx), (p0[1] + (lo + hi) * 0.5 * dy))
        if point_in_polygon(mid, poly):
            out.append((lo, hi))
    return out
