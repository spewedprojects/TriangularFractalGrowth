from math import sin, cos, radians

def third_vertex(p, q, side):
    """Return the third vertex of an equilateral triangle built on pq.
       side = +1 (left) or –1 (right)."""
    vx, vy = q[0]-p[0], q[1]-p[1]
    a = radians(60) * side
    rx = vx * cos(a) - vy * sin(a)
    ry = vx * sin(a) + vy * cos(a)
    return (p[0] + rx, p[1] + ry)

def convex_hull(points):
    if len(points) < 3:
        return points[:]
    points = sorted(points)
    cross = lambda o, a, b: (a[0]-o[0])*(b[1]-o[1]) - (a[1]-o[1])*(b[0]-o[0])

    lower = []
    for p in points:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) < 0:
            lower.pop()
        lower.append(p)

    upper = []
    for p in reversed(points):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) < 0:
            upper.pop()
        upper.append(p)

    return lower[:-1] + upper[:-1]
