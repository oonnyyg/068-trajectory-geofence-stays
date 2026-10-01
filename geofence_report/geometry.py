from fractions import Fraction


def _to_frac(v):
    return Fraction(v) if not isinstance(v, Fraction) else v


def point_in_polygon(px, py, poly):
    """Inclusive test: boundary counts as inside. Works with ints/floats/Fractions."""
    px, py = _to_frac(px), _to_frac(py)
    n = len(poly)
    inside = False
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        dx, dy = x2 - x1, y2 - y1
        cross = (px - x1) * dy - (py - y1) * dx
        if cross == 0 and min(x1, x2) <= px <= max(x1, x2) and min(y1, y2) <= py <= max(y1, y2):
            return True
        if (y1 > py) != (y2 > py):
            x_int = x1 + (py - y1) * dx / dy
            if x_int > px:
                inside = not inside
    return inside


def segment_inside_intervals(p0, p1, poly):
    """Return sorted list of (u_start, u_end) Fraction parameter ranges in [0,1]
    where the point p0 + u*(p1-p0) lies inside or on the polygon."""
    x0, y0 = p0
    x1, y1 = p1
    dx, dy = x1 - x0, y1 - y0
    cuts = {Fraction(0), Fraction(1)}
    n = len(poly)
    for i in range(n):
        ax, ay = poly[i]
        bx, by = poly[(i + 1) % n]
        ex, ey = bx - ax, by - ay
        denom = dx * ey - dy * ex
        rx, ry = ax - x0, ay - y0
        if denom != 0:
            u = (rx * ey - ry * ex) / denom
            v = (rx * dy - ry * dx) / denom
            if 0 <= u <= 1 and 0 <= v <= 1:
                cuts.add(u)
        elif rx * dy - ry * dx == 0 and (dx != 0 or dy != 0):
            # Collinear with an edge: add overlap endpoints.
            if dx != 0:
                ua, ub = (ax - x0) / dx, (bx - x0) / dx
            else:
                ua, ub = (ay - y0) / dy, (by - y0) / dy
            lo, hi = max(min(ua, ub), Fraction(0)), min(max(ua, ub), Fraction(1))
            if lo <= hi:
                cuts.add(lo)
                cuts.add(hi)
    ordered = sorted(cuts)
    intervals = []
    for a, b in zip(ordered, ordered[1:]):
        if a == b:
            continue
        mid = (a + b) / 2
        if point_in_polygon(x0 + mid * dx, y0 + mid * dy, poly):
            intervals.append((a, b))
    return intervals
