# gui.py

import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox
import io, os

try:
    from PIL import Image
except ImportError:
    Image = None

import geometry as gm
import drawing as drw
from state import LayerState

# You can tweak this to control the “height” of each 3D layer:
HEIGHT_STEP = 1.0


class TriGrowthGUI:
    def __init__(self, root: tk.Tk):
        # ------------------------- Scrollable Canvas Setup -------------------------
        canvas_frame = tk.Frame(root)
        canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.cv = tk.Canvas(canvas_frame, width=1000, height=700, bg='white')
        sb_v = tk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=self.cv.yview)
        sb_h = tk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL, command=self.cv.xview)
        self.cv.config(yscrollcommand=sb_v.set, xscrollcommand=sb_h.set)

        self.cv.grid(row=0, column=0, sticky='nsew')
        sb_v.grid(row=0, column=1, sticky='ns')
        sb_h.grid(row=1, column=0, sticky='ew')
        canvas_frame.grid_rowconfigure(0, weight=1)
        canvas_frame.grid_columnconfigure(0, weight=1)

        # --------------------------- Control Panel ---------------------------
        ctrl = tk.Frame(root)
        ctrl.pack(side=tk.RIGHT, fill=tk.Y)

        # Buttons
        for txt, fn in (('Add Layer',   self.add_layer),
                        ('Undo Layer',  self.undo_layer),
                        ('Redo Layer',  self.redo_layer),
                        ('Run to End',  self.auto_run),
                        ('Export',      self.export_dialog),
                        ('Clear',       self.clear)):
            tk.Button(ctrl, text=txt, command=fn).pack(fill=tk.X, padx=6, pady=2)

        # Side selector (LEFT, RIGHT, BOTH)
        self.side = tk.StringVar(value='LEFT')
        tk.Label(ctrl, text='Triangle Side', font=('Arial', 10, 'bold')).pack(pady=(10, 0))
        for s in ('LEFT', 'RIGHT', 'BOTH'):
            tk.Radiobutton(ctrl, text=s, variable=self.side, value=s).pack(anchor='w')

        # Visibility toggles
        tk.Label(ctrl, text='Visibility', font=('Arial', 10, 'bold')).pack(pady=(10, 0))
        self.v_dots = tk.IntVar(value=1)
        self.v_rows = tk.IntVar(value=1)
        self.v_tris = tk.IntVar(value=1)
        self.v_hull = tk.IntVar(value=1)
        for txt, var in (('Dots', self.v_dots),
                         ('Row Lines', self.v_rows),
                         ('Triangles', self.v_tris),
                         ('Outer Hull', self.v_hull)):
            tk.Checkbutton(ctrl, text=txt, variable=var,
                           command=self.update_visibility).pack(anchor='w')

        # Line thickness control
        tk.Label(ctrl, text='Line Thickness', font=('Arial', 10, 'bold')).pack(pady=(10, 0))
        self.line_thickness = tk.IntVar(value=1)
        tk.Spinbox(ctrl, from_=1, to=10, textvariable=self.line_thickness,
                   command=self.update_thickness, width=5).pack(anchor='w', pady=(0, 10))

        # --------------------------- Internal State ---------------------------
        self.state = LayerState()
        # Each layer in 2D: state.rows. We also keep:
        self.layers_3d = []        # list of lists of (x,y,z) for each layer
        self.triangles_3d = []     # list of ( (x1,y1,z1),(x2,y2,z2),(x3,y3,z3) ) triplets

        self._drag_i = None
        self._drag_id = None

        # --------------------------- Bindings ---------------------------
        self.cv.bind('<Button-1>', self.on_click)
        self.cv.bind('<B1-Motion>', self.on_drag)
        self.cv.bind('<ButtonRelease-1>', self.on_release)

    # ------------------------------------------------ seed editing: click to add/move points
    def on_click(self, e):
        if self.state.seed_locked:
            return
        # map widget coords to canvas coords
        x = self.cv.canvasx(e.x)
        y = self.cv.canvasy(e.y)

        if not self.state.rows:
            self.state.rows.append([])

        # Check if clicking on an existing seed dot
        for i, (px, py) in enumerate(self.state.rows[0]):
            if (x - px)**2 + (y - py)**2 <= (drw.DOT_R * 3)**2:
                self._drag_i = i
                self._drag_id = self.cv.find_closest(px, py)[0]
                return

        # Otherwise add a brand-new seed dot
        self.state.rows[0].append((x, y))
        drw.draw_point(self.cv, x, y, 'black', 'seed')
        if len(self.state.rows[0]) > 1:
            p, q = self.state.rows[0][-2], self.state.rows[0][-1]
            self.cv.create_line(p[0], p[1], q[0], q[1],
                                tags=('seed', 'row'),
                                width=self.line_thickness.get())

        self.update_hull()

    def on_drag(self, e):
        if self._drag_i is None:
            return
        x = self.cv.canvasx(e.x)
        y = self.cv.canvasy(e.y)
        self.state.rows[0][self._drag_i] = (x, y)
        self.cv.coords(self._drag_id,
                       x - drw.DOT_R, y - drw.DOT_R,
                       x + drw.DOT_R, y + drw.DOT_R)

        # Redraw the “seed line” that connects seed dots
        self.cv.delete('seed_line')
        for i in range(len(self.state.rows[0]) - 1):
            p, q = self.state.rows[0][i], self.state.rows[0][i+1]
            self.cv.create_line(p[0], p[1], q[0], q[1],
                                tags=('seed_line', 'row'),
                                width=self.line_thickness.get())

        self.update_hull()

    def on_release(self, _):
        self._drag_i = self._drag_id = None

    # ------------------------------------------------ layer operations
    def add_layer(self):
        # Need at least two points in the last row to build a new layer
        if not self.state.rows or len(self.state.rows[-1]) < 2:
            return

        self.state.seed_locked = True
        idx = len(self.state.tags)           # next layer index (0=seed,1=first,2=second...)
        tag = f'ly{idx}'
        colour = drw.layer_colour(idx)
        w = self.line_thickness.get()
        z = idx * HEIGHT_STEP                # assign a Z‐height for this new layer

        # Build the new layer in 2D + record its 3D points
        if self.side.get() == 'BOTH':
            # If this is the very first BOTH layer, initialize left/right branches at layer‐0
            if self.state.left_branch is None:
                self.state.left_branch = self.state.rows[-1][:]
                self.state.right_branch = self.state.rows[-1][:]
            nl_2d = self._make_next(self.state.left_branch,  +1, tag, colour, w, z)
            nr_2d = self._make_next(self.state.right_branch, -1, tag, colour, w, z)
            self.state.left_branch, self.state.right_branch = nl_2d, nr_2d
            new_row_2d = nl_2d + nr_2d
        else:
            sign = +1 if self.side.get() == 'LEFT' else -1
            new_row_2d = self._make_next(self.state.rows[-1], sign, tag, colour, w, z)
            self.state.left_branch = self.state.right_branch = None

        # Push the new 2D row into state
        self.state.push(new_row_2d, tag)

        # Record the 3D geometry for this entire new row
        # seed‐row (layer=0) was already recorded at CLEAR; now we record layer idx
        new_row_3d = [(x, y, z) for (x, y) in new_row_2d]
        self.layers_3d.append(new_row_3d)

        self.update_hull()
        self.update_visibility()

    def _make_next(self, row_2d, side, tag, colour, width, z):
        """
        row_2d: a list of 2D points [(x,y), ...]
        side: +1 or -1 for LEFT/RIGHT
        tag: layer tag (e.g. 'ly1')
        colour: fill colour for the new dot
        width: current line thickness
        z:  the Z‐height for this layer (float)
        """
        children_2d = []
        for i in range(len(row_2d) - 1):
            p2d, q2d = row_2d[i], row_2d[i+1]
            # Compute the new 2D child (third vertex of equilateral)
            c2d = gm.third_vertex(p2d, q2d, side)
            children_2d.append(c2d)

            # DRAW in 2D on the canvas:
            drw.draw_triangle(self.cv, p2d, q2d, c2d, tag, colour, width)

            # RECORD the triangle in 3D
            # The parent edge (p2d→q2d) lives at the same z, as does c2d
            p3d = (p2d[0], p2d[1], z)
            q3d = (q2d[0], q2d[1], z)
            c3d = (c2d[0], c2d[1], z)
            self.triangles_3d.append((p3d, q3d, c3d))

        # Draw the 2D “row line” connecting consecutive children_2d
        for i in range(len(children_2d) - 1):
            a, b = children_2d[i], children_2d[i+1]
            self.cv.create_line(a[0], a[1], b[0], b[1],
                                tags=(tag, 'row'),
                                width=width)

        return children_2d

    def undo_layer(self):
        tag = self.state.pop()
        if tag:
            self.cv.itemconfigure(tag, state='hidden')
            self.state.undone.add(tag)
            # Also drop the last 3D layer & its triangles:
            if self.layers_3d:
                self.layers_3d.pop()
            # Remove all triangles whose Z = that layer's height
            z_to_remove = len(self.layers_3d) * HEIGHT_STEP
            self.triangles_3d = [
                tri for tri in self.triangles_3d if tri[0][2] != z_to_remove
            ]
            self.update_hull()
            self.update_visibility()

    def redo_layer(self):
        tag = self.state.redo_layer()
        if tag:
            self.state.undone.discard(tag)
            self.cv.itemconfigure(tag, state='normal')
            # We cannot “reconstruct” the 3D layer easily here unless we kept it in a redo‐stack as well.
            # Easiest approach: when undoing, we popped one layer from layers_3d; when redoing,
            # we need to reconstruct that layer_3d from the 2D row (state.rows[-1]) and its index.
            idx = len(self.state.tags) - 1   # index of the re-pushed layer
            z = idx * HEIGHT_STEP
            row2d = self.state.rows[-1]
            row3d = [(x, y, z) for (x, y) in row2d]
            self.layers_3d.append(row3d)

            # Triangles: we know that “redo” re-executes exactly the same equilateral
            # construction that we had ran originally, so we can just reconstruct all triangles
            # in the last layer from state.rows[-2] → state.rows[-1].
            # (Note: this works because redo only follows an immediate undo.)
            parent_row = self.state.rows[-2]
            children = row2d
            side = +1 if self.side.get() == 'LEFT' else -1
            if self.side.get() == 'BOTH':
                # BOTH‐mode: the left and right branches were stored in state,
                # but since we only popped one generation, we know how to rebuild.
                # Simplest: re-run _make_next on a copy of the previous left/right branch:
                # (But for clarity, we will just recalc from 2D: identical result.)
                # In most normal use-cases, users undo/redo only one step, so this suffices.
                side = +1  # build a left‐only version, then append right
                # left branch:
                left3d = []
                for i in range(len(parent_row) - 1):
                    p2d, q2d = parent_row[i], parent_row[i+1]
                    c2d = gm.third_vertex(p2d, q2d, +1)
                    p3d = (p2d[0], p2d[1], z)
                    q3d = (q2d[0], q2d[1], z)
                    c3d = (c2d[0], c2d[1], z)
                    left3d.append(c3d)
                    self.triangles_3d.append((p3d, q3d, c3d))
                # right branch:
                for i in range(len(parent_row) - 1):
                    p2d, q2d = parent_row[i], parent_row[i+1]
                    c2d = gm.third_vertex(p2d, q2d, -1)
                    p3d = (p2d[0], p2d[1], z)
                    q3d = (q2d[0], q2d[1], z)
                    c3d = (c2d[0], c2d[1], z)
                    self.triangles_3d.append((p3d, q3d, c3d))
                # done
            else:
                # single‐side redo:
                for i in range(len(parent_row) - 1):
                    p2d, q2d = parent_row[i], parent_row[i+1]
                    c2d = gm.third_vertex(p2d, q2d, side)
                    p3d = (p2d[0], p2d[1], z)
                    q3d = (q2d[0], q2d[1], z)
                    c3d = (c2d[0], c2d[1], z)
                    self.triangles_3d.append((p3d, q3d, c3d))

            self.update_hull()
            self.update_visibility()

    def auto_run(self):
        if self.side.get() == 'BOTH':
            return
        while self.state.rows and len(self.state.rows[-1]) > 2:
            self.add_layer()

    def clear(self):
        self.cv.delete('all')
        self.state = LayerState()
        self.layers_3d.clear()
        self.triangles_3d.clear()
        # Reset scrollregion
        self.cv.configure(scrollregion=(0, 0, 1000, 700))
        self.update_hull()

    # ------------------------------------------------ visibility & thickness
    def update_visibility(self):
        cv = self.cv
        cv.itemconfigure('dot', state='normal' if self.v_dots.get() else 'hidden')
        cv.itemconfigure('row', state='normal' if self.v_rows.get() else 'hidden')
        cv.itemconfigure('tri', state='normal' if self.v_tris.get() else 'hidden')
        cv.itemconfigure('hull', state='normal' if self.v_hull.get() else 'hidden')
        for t in self.state.undone:
            cv.itemconfigure(t, state='hidden')

    def update_thickness(self):
        w = self.line_thickness.get()
        for tag in ('row', 'tri', 'hull'):
            self.cv.itemconfigure(tag, width=w)

    # ------------------------------------------------ true outer silhouette
    def update_hull(self):
        cv = self.cv
        cv.delete('hull')

        # Step 1: count triangle edges (undirected)
        edge_cnt = {}
        for item in cv.find_withtag('tri'):
            coords = list(map(int, map(round, cv.coords(item))))
            p = (coords[0], coords[1])
            q = (coords[2], coords[3])
            key = tuple(sorted((p, q)))
            edge_cnt[key] = edge_cnt.get(key, 0) + 1

        # Step 2: keep only edges that appear once → boundary
        boundary = [e for e, count in edge_cnt.items() if count == 1]
        if len(boundary) < 3:
            # Even if no hull, we still update scrollregion
            self.cv.configure(scrollregion=self.cv.bbox('all') or (0, 0, 1000, 700))
            self.update_visibility()
            return

        # Step 3: build adjacency map
        adj = {}
        for p, q in boundary:
            adj.setdefault(p, []).append(q)
            adj.setdefault(q, []).append(p)

        # Step 4: walk all loops using a visited‐edge set
        visited = set()  # set of frozenset({p, q}) for edges we’ve drawn
        loops = []
        for start in adj:
            # if all edges at this vertex are already visited, skip
            if all(tuple(sorted((start, n))) in visited for n in adj[start]):
                continue

            loop = [start]
            prev, curr = None, start
            while True:
                nxt = None
                for n in adj[curr]:
                    key = tuple(sorted((curr, n)))
                    if key not in visited:
                        nxt = n
                        visited.add(key)
                        break
                if nxt is None or nxt == start:
                    break
                loop.append(nxt)
                prev, curr = curr, nxt

            if len(loop) > 2:
                loop.append(start)
                loops.append(loop)

        # Step 5: draw each loop in 2D
        w = self.line_thickness.get()
        for loop in loops:
            for i in range(len(loop) - 1):
                p, q = loop[i], loop[i+1]
                cv.create_line(p[0], p[1], q[0], q[1],
                               tags=('hull',), width=w)

        # Step 6: update scrollregion so you can pan/zoom to see everything
        self.cv.configure(scrollregion=self.cv.bbox('all') or (0, 0, 1000, 700))
        self.update_visibility()

    # ------------------------------------------------ Export dialog (svg/png/obj)
    def export_dialog(self):
        fmt = simpledialog.askstring('Export', 'Format (svg/png/obj):', initialvalue='svg')
        if not fmt:
            return
        fmt = fmt.lower()
        if fmt not in ('svg', 'png', 'obj'):
            messagebox.showerror('Export', 'Unsupported format')
            return

        filetypes = { 'svg': '.svg', 'png': '.png', 'obj': '.obj' }
        file = filedialog.asksaveasfilename(defaultextension=filetypes[fmt])
        if not file:
            return

        if fmt == 'svg':
            self._exp_svg(file)
        elif fmt == 'png':
            self._exp_png(file)
        else:  # fmt == 'obj'
            self._exp_obj(file)

    # ------------------------------------------------ Export to SVG (preserve line thickness)
    def _exp_svg(self, path):
        try:
            import svgwrite
        except ImportError:
            messagebox.showerror('Export', 'svgwrite not installed')
            return

        cv = self.cv
        visible = [i for i in cv.find_all() if cv.itemcget(i, 'state') != 'hidden']
        if not visible:
            messagebox.showinfo('Export', 'Nothing visible to export')
            return

        # 1. Compute bounding box
        xs, ys = [], []
        for item in visible:
            coords = list(map(float, cv.coords(item)))
            xs.extend(coords[0::2])
            ys.extend(coords[1::2])

        margin = 10
        min_x = min(xs) - margin
        min_y = min(ys) - margin
        max_x = max(xs) + margin
        max_y = max(ys) + margin

        width = max_x - min_x
        height = max_y - min_y
        shift = lambda v, off: v - off

        dwg = svgwrite.Drawing(path, size=(width, height))
        lw = self.line_thickness.get()

        # 2. Draw visible items into SVG
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

    # ------------------------------------------------ Export to PNG (visible only)
    def _exp_png(self, path):
        if Image is None:
            messagebox.showerror('Export', 'Pillow required')
            return
        scale = simpledialog.askinteger('PNG scale', 'Scale (1–10)',
                                        initialvalue=1, minvalue=1, maxvalue=10)
        if not scale:
            return

        cv = self.cv
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

    # ------------------------------------------------ Export to OBJ (3D model)
    def _exp_obj(self, path):
        # We will write each triangle’s three vertices as separate 'v' lines,
        # then each triangle as an 'f' face. This means no vertex sharing, but
        # it’s the simplest approach.

        if not self.triangles_3d:
            messagebox.showinfo('Export', 'No 3D data to export. Add at least one layer.')
            return

        # Flatten vertices and assign indices 1-based
        vertices = []
        faces = []
        for tri in self.triangles_3d:
            base_idx = len(vertices)  # 0-based
            vertices.extend(tri)
            # OBJ face indices are 1-based
            faces.append((base_idx + 1, base_idx + 2, base_idx + 3))

        try:
            with open(path, 'w') as f:
                f.write("# Triangular Growth 3D OBJ export\n")
                for v in vertices:
                    f.write(f"v {v[0]} {v[1]} {v[2]}\n")
                for face in faces:
                    f.write(f"f {face[0]} {face[1]} {face[2]}\n")
            messagebox.showinfo('Export', f'OBJ saved to:\n{os.path.abspath(path)}')
        except Exception as e:
            messagebox.showerror('Export', f'Failed to write OBJ:\n{e}')
