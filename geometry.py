from math import sin, cos, radians

def third_vertex(p, q, side):
    """Return the third vertex of an equilateral triangle built on pq.
       side = +1 (left) or –1 (right)."""
    vx, vy = q[0]-p[0], q[1]-p[1]
    a = radians(60) * side
    rx = vx * cos(a) - vy * sin(a)
    ry = vx * sin(a) + vy * cos(a)
    return (p[0] + rx, p[1] + ry)

