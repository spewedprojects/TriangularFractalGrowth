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
    Export only *visible* canvas items to SVG, preserving current line thickness
    for <line> elements.
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

    for item in visible:
        typ = cv.type(item)
        coords = list(map(float, cv.coords(item)))

        if typ == 'oval':
            x1, y1, x2, y2 = coords
            cx = shift((x1 + x2)/2, min_x)
            cy = shift((y1 + y2)/2, min_y)
            r = (x2 - x1)/2
            fillcol = cv.itemcget(item, 'fill')
            dwg.add(dwg.circle(center=(cx, cy), r=r, fill=fillcol, stroke='none'))

        elif typ == 'line':
            x1, y1, x2, y2 = coords
            dwg.add(dwg.line(
                start=(shift(x1, min_x), shift(y1, min_y)),
                end  =(shift(x2, min_x), shift(y2, min_y)),
                stroke='#000', stroke_width=lw
            ))

    dwg.save()


def export_png(canvas: tk.Canvas, path: str):
    """
    Export only *visible* canvas items to PNG. Temporarily disable hidden items to
    get a clean PostScript snapshot.
    """
    if Image is None:
        messagebox.showerror('Export', 'Pillow required')
        return

    scale = simpledialog.askinteger('PNG scale','Scale (1–10)',initialvalue=1,minvalue=1,maxvalue=10)
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


def export_obj(canvas_mgr, filepath):
    """
    Export the current 3D mesh (canvas_mgr.triangles_3d) to a Wavefront .obj file.

    canvas_mgr.triangles_3d is assumed to be a list of triangles, each triangle being
    a tuple of three 3D points: ((x1,y1,z1), (x2,y2,z2), (x3,y3,z3)).

    This function rebuilds the vertex list each time from scratch, so that
    undo/redo has no lingering stale vertices or faces.
    """

    # 1) Build a fresh vertex→index map and a flat list of unique vertices
    vert_map = {}     # dict: (x,y,z) → OBJ_index (1-based)
    vertices = []     # list of (x,y,z) in the order we first see them

    for tri in canvas_mgr.triangles_3d:
        for v in tri:
            if v not in vert_map:
                # First time seeing this vertex tuple, assign next OBJ index
                vert_map[v] = len(vertices) + 1   # OBJ indices are 1-based
                vertices.append(v)

    # 2) Build a flat list of faces (using the new indexing scheme)
    faces = []
    for tri in canvas_mgr.triangles_3d:
        # tri is ((x1,y1,z1), (x2,y2,z2), (x3,y3,z3))
        idx1 = vert_map[tri[0]]
        idx2 = vert_map[tri[1]]
        idx3 = vert_map[tri[2]]
        faces.append((idx1, idx2, idx3))

    # 3) Write out the .obj file
    try:
        with open(filepath, 'w') as f:
            f.write("# Triangular Growth OBJ\n")
            f.write("# vertex count: {}\n".format(len(vertices)))
            f.write("# face count: {}\n\n".format(len(faces)))

            # Write vertices
            for (x, y, z) in vertices:
                f.write("v {:.6f} {:.6f} {:.6f}\n".format(x, y, z))
            f.write("\n")

            # Write faces
            for (i1, i2, i3) in faces:
                f.write("f {} {} {}\n".format(i1, i2, i3))

        print(f"Exported OBJ successfully to: {filepath}")
    except Exception as e:
        print("Error exporting OBJ:", e)
