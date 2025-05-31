# exporter.py

import os
import io
import tkinter as tk
from tkinter import messagebox, simpledialog, filedialog

try:
    from PIL import Image
except ImportError:
    Image = None

def export_svg(canvas: tk.Canvas, line_thickness_var: tk.IntVar, path: str):
    """
    Export only the visible items of `canvas` to an SVG file at `path`,
    preserving the current line‐thickness for all <line> elements.
    """
    try:
        import svgwrite
    except ImportError:
        messagebox.showerror('Export', 'svgwrite not installed')
        return

    cv = canvas
    visible = [i for i in cv.find_all() if cv.itemcget(i, 'state') != 'hidden']
    if not visible:
        messagebox.showinfo('Export', 'Nothing visible to export')
        return

    # 1) Compute bounding box of visible items
    xs, ys = [], []
    for item in visible:
        coords = list(map(float, cv.coords(item)))
        xs.extend(coords[0::2]); ys.extend(coords[1::2])

    margin = 10
    min_x = min(xs) - margin
    min_y = min(ys) - margin
    max_x = max(xs) + margin
    max_y = max(ys) + margin

    width = max_x - min_x
    height = max_y - min_y
    shift = lambda v, off: v - off

    dwg = svgwrite.Drawing(path, size=(width, height))
    lw = line_thickness_var.get()

    # 2) Draw each visible item
    for item in visible:
        typ = cv.type(item)
        coords = list(map(float, cv.coords(item)))

        if typ == 'oval':
            x1, y1, x2, y2 = coords
            cx = shift((x1 + x2) / 2, min_x)
            cy = shift((y1 + y2) / 2, min_y)
            r = (x2 - x1) / 2
            fillcol = cv.itemcget(item, 'fill')
            dwg.add(dwg.circle(center=(cx, cy), r=r, fill=fillcol, stroke='none'))

        elif typ == 'line':
            x1, y1, x2, y2 = coords
            dwg.add(dwg.line(start=(shift(x1, min_x), shift(y1, min_y)),
                             end  =(shift(x2, min_x), shift(y2, min_y)),
                             stroke='#000', stroke_width=lw))

    dwg.save()


def export_png(canvas: tk.Canvas, path: str):
    """
    Export only the visible items of `canvas` to a PNG at `path`.
    Temporarily disable hidden items so the PostScript snapshot contains only
    the visible ones, then restore their “hidden” state.
    """
    if Image is None:
        messagebox.showerror('Export', 'Pillow required')
        return

    scale = simpledialog.askinteger('PNG scale', 'Scale (1–10)', initialvalue=1, minvalue=1, maxvalue=10)
    if not scale:
        return

    cv = canvas
    hidden = [i for i in cv.find_all() if cv.itemcget(i, 'state') == 'hidden']
    for i in hidden:
        cv.itemconfigure(i, state='disabled')

    ps = cv.postscript(colormode='color')
    for i in hidden:
        cv.itemconfigure(i, state='hidden')

    img = Image.open(io.BytesIO(ps.encode('utf-8')))
    w, h = img.size
    img = img.resize((w * scale, h * scale), Image.ANTIALIAS)
    img.save(path)


def export_obj(triangles_3d: list, path: str):
    """
    Export the 3D triangles (`triangles_3d`) to a Wavefront OBJ file at `path`.
    Each triangle in `triangles_3d` is a tuple of three (x, y, z) coordinates.
    We write each triangle with three unique vertices (no vertex sharing).
    """
    if not triangles_3d:
        messagebox.showinfo('Export', 'No 3D data to export. Add at least one layer.')
        return

    vertices = []
    faces = []
    for tri in triangles_3d:
        base_idx = len(vertices)  # 0‐based index for new batch of 3 verts
        vertices.extend(tri)
        faces.append((base_idx + 1, base_idx + 2, base_idx + 3))  # OBJ indices are 1-based

    try:
        with open(path, 'w') as f:
            f.write("# Triangular Growth 3D OBJ\n")
            for v in vertices:
                f.write(f"v {v[0]} {v[1]} {v[2]}\n")
            for face in faces:
                f.write(f"f {face[0]} {face[1]} {face[2]}\n")

        messagebox.showinfo('Export', f'OBJ saved to:\n{os.path.abspath(path)}')
    except Exception as e:
        messagebox.showerror('Export', f'Failed to write OBJ:\n{e}')
