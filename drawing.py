import colorsys
import tkinter as tk

DOT_R = 3

def layer_colour(i):
    h = (i * 0.15) % 1
    r, g, b = colorsys.hsv_to_rgb(h, 0.9, 0.95)
    return f'#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}'

def draw_point(cv: tk.Canvas, x, y, colour, tag):
    r = DOT_R
    cv.create_oval(x-r, y-r, x+r, y+r,
                   fill=colour, outline='', tags=(tag, 'dot'))

def draw_triangle(cv: tk.Canvas, p, q, r, tag, colour, width):
    # now passing width into every edge
    cv.create_line(p[0], p[1], q[0], q[1],
                   tags=(tag, 'row'), width=width)
    cv.create_line(q[0], q[1], r[0], r[1],
                   tags=(tag, 'tri'), width=width)
    cv.create_line(r[0], r[1], p[0], p[1],
                   tags=(tag, 'tri'), width=width)
    draw_point(cv, *r, colour, tag)