# gui.py

import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox
import io

try:
    from PIL import Image
except ImportError:
    Image = None

import geometry as gm
import drawing as drw
from state import LayerState


class TriGrowthGUI:
    def __init__(self, root: tk.Tk):
        # ------ SCROLLABLE CANVAS SETUP ------
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

        # ------ CONTROL PANEL ------
        ctrl = tk.Frame(root)
        ctrl.pack(side=tk.RIGHT, fill=tk.Y)

        # Buttons
        for txt, fn in (('Add Layer', self.add_layer),
                        ('Undo Layer', self.undo_layer),
                        ('Redo Layer', self.redo_layer),
                        ('Run to End', self.auto_run),
                        ('Export', self.export_dialog),
                        ('Clear', self.clear)):
            tk.Button(ctrl, text=txt, command=fn).pack(fill=tk.X, padx=6, pady=2)

        # Side selector
        self.side = tk.StringVar(value='LEFT')
        tk.Label(ctrl, text='Triangle Side', font=('Arial',10,'bold')).pack(pady=(10,0))
        for s in ('LEFT','RIGHT','BOTH'):
            tk.Radiobutton(ctrl, text=s, variable=self.side, value=s).pack(anchor='w')

        # Visibility toggles
        tk.Label(ctrl, text='Visibility', font=('Arial',10,'bold')).pack(pady=(10,0))
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
        tk.Label(ctrl, text='Line Thickness', font=('Arial',10,'bold')).pack(pady=(10,0))
        self.line_thickness = tk.IntVar(value=1)
        tk.Spinbox(ctrl, from_=1, to=10, textvariable=self.line_thickness,
                   command=self.update_thickness, width=5).pack(anchor='w', pady=(0,10))

        # ------ STATE ------
        self.state = LayerState()
        self._drag_i = self._drag_id = None

        # Bindings
        self.cv.bind('<Button-1>', self.on_click)
        self.cv.bind('<B1-Motion>', self.on_drag)
        self.cv.bind('<ButtonRelease-1>', self.on_release)

    # ------------------ Seed editing ------------------
    def on_click(self, e):
        if self.state.seed_locked:
            return

        # convert from widget coords to canvas coords
        x = self.cv.canvasx(e.x)
        y = self.cv.canvasy(e.y)

        if not self.state.rows:
            self.state.rows.append([])

        # hit-test existing seed dots
        for i, (px, py) in enumerate(self.state.rows[0]):
            if (x - px)**2 + (y - py)**2 <= (drw.DOT_R*3)**2:
                self._drag_i = i
                self._drag_id = self.cv.find_closest(px, py)[0]
                return

        # add a new seed dot at the correct canvas position
        self.state.rows[0].append((x, y))
        drw.draw_point(self.cv, x, y, 'black', 'seed')
        if len(self.state.rows[0]) > 1:
            p, q = self.state.rows[0][-2], self.state.rows[0][-1]
            self.cv.create_line(
                p[0], p[1], q[0], q[1],
                tags=('seed','row'),
                width=self.line_thickness.get()
            )

        self.update_hull()

    def on_drag(self, e):
        if self._drag_i is None:
            return

        # convert mouse coords
        x = self.cv.canvasx(e.x)
        y = self.cv.canvasy(e.y)

        # update the stored position
        self.state.rows[0][self._drag_i] = (x, y)
        # move the oval
        self.cv.coords(
            self._drag_id,
            x-drw.DOT_R, y-drw.DOT_R,
            x+drw.DOT_R, y+drw.DOT_R
        )
        # redraw the seed‐line
        self.cv.delete('seed_line')
        for i in range(len(self.state.rows[0]) - 1):
            p, q = self.state.rows[0][i], self.state.rows[0][i+1]
            self.cv.create_line(
                p[0], p[1], q[0], q[1],
                tags=('seed_line','row'),
                width=self.line_thickness.get()
            )

        self.update_hull()

    def on_release(self, _):
        self._drag_i = self._drag_id = None

    # ------------------ Layer operations ------------------
    def add_layer(self):
        if not self.state.rows or len(self.state.rows[-1]) < 2:
            return
        self.state.seed_locked = True
        idx = len(self.state.tags)
        tag = f'ly{idx}'
        colour = drw.layer_colour(idx)
        w = self.line_thickness.get()

        if self.side.get() == 'BOTH':
            if self.state.left_branch is None:
                self.state.left_branch = self.state.rows[-1][:]
                self.state.right_branch = self.state.rows[-1][:]
            nl = self._make_next(self.state.left_branch, +1, tag, colour, w)
            nr = self._make_next(self.state.right_branch, -1, tag, colour, w)
            self.state.left_branch, self.state.right_branch = nl, nr
            new_row = nl + nr
        else:
            sign = +1 if self.side.get() == 'LEFT' else -1
            new_row = self._make_next(self.state.rows[-1], sign, tag, colour, w)
            self.state.left_branch = self.state.right_branch = None

        self.state.push(new_row, tag)
        self.update_hull()
        self.update_visibility()

    def _make_next(self, row, side, tag, colour, width):
        children = []
        for i in range(len(row) - 1):
            p, q = row[i], row[i+1]
            c = gm.third_vertex(p, q, side)
            children.append(c)
            drw.draw_triangle(self.cv, p, q, c, tag, colour, width)

        for i in range(len(children) - 1):
            self.cv.create_line(*children[i], *children[i+1],
                                tags=(tag,'row'),
                                width=width)
        return children

    def undo_layer(self):
        tag = self.state.pop()
        if tag:
            self.cv.itemconfigure(tag, state='hidden')
            self.state.undone.add(tag)
            self.update_hull()
            self.update_visibility()

    def redo_layer(self):
        tag = self.state.redo_layer()
        if tag:
            self.state.undone.discard(tag)
            self.cv.itemconfigure(tag, state='normal')
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
        # reset scrollregion to default canvas size
        self.cv.configure(scrollregion=(0,0,1000,700))
        self.update_hull()

    # ------------------ Visibility & thickness ------------------
    def update_visibility(self):
        self.cv.itemconfigure('dot',
                              state='normal' if self.v_dots.get() else 'hidden')
        self.cv.itemconfigure('row',
                              state='normal' if self.v_rows.get() else 'hidden')
        self.cv.itemconfigure('tri',
                              state='normal' if self.v_tris.get() else 'hidden')
        self.cv.itemconfigure('hull',
                              state='normal' if self.v_hull.get() else 'hidden')
        # re-hide any undone layers
        for t in self.state.undone:
            self.cv.itemconfigure(t, state='hidden')

    def update_thickness(self):
        w = self.line_thickness.get()
        for tag in ('row','tri','hull'):
            self.cv.itemconfigure(tag, width=w)

    # ------------------ True outer silhouette (unchanged) ------------------
    def update_hull(self):
        cv = self.cv
        cv.delete('hull')

        edge_cnt = {}
        for item in cv.find_withtag('tri'):
            x1, y1, x2, y2 = map(int, map(round, cv.coords(item)))
            p, q = (x1,y1), (x2,y2)
            key = tuple(sorted((p,q)))
            edge_cnt[key] = edge_cnt.get(key,0) + 1

        boundary = [e for e,n in edge_cnt.items() if n==1]
        if len(boundary) < 3:
            # still update scrollregion
            self.cv.configure(scrollregion=self.cv.bbox('all') or (0,0,1000,700))
            self.update_visibility()
            return

        # build adjacency
        adj = {}
        for p,q in boundary:
            adj.setdefault(p,[]).append(q)
            adj.setdefault(q,[]).append(p)

        visited = set()
        loops = []
        for start in adj:
            if all(tuple(sorted((start,n))) in visited for n in adj[start]):
                continue
            loop = [start]
            prev, curr = None, start
            while True:
                nxt = None
                for n in adj[curr]:
                    key = tuple(sorted((curr,n)))
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

        w = self.line_thickness.get()
        for loop in loops:
            for i in range(len(loop)-1):
                p, q = loop[i], loop[i+1]
                cv.create_line(*p, *q,
                               tags=('hull',),
                               width=w)

        # update scrollregion to cover all items
        self.cv.configure(scrollregion=self.cv.bbox('all') or (0,0,1000,700))
        self.update_visibility()

    # ------------------ Export (only visible items) ------------------
    def export_dialog(self):
        fmt = simpledialog.askstring('Export', 'Format (svg/png):',
                                     initialvalue='svg')
        if not fmt:
            return
        fmt = fmt.lower()
        if fmt not in ('svg','png'):
            messagebox.showerror('Export','Unsupported')
            return
        file = filedialog.asksaveasfilename(defaultextension=f'.{fmt}')
        if not file:
            return
        if fmt == 'svg':
            self._export_svg(file)
        else:
            self._export_png(file)

    # ... keep your previous _exp_svg() and _exp_png() here ...


    # --------------------------------------------------------- SVG export
    def _export_svg(self, path):
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

        # 1. Compute bounding box of all visible items
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

        # 2. Create the SVG drawing with that exact size
        dwg = svgwrite.Drawing(path, size=(width, height))
        shift = lambda v, off: v - off  # to translate coords into [0..width] × [0..height]

        # 3. Read current line thickness
        lw = self.line_thickness.get()

        # 4. Add each visible item to the SVG
        for item in visible:
            typ = cv.type(item)
            coords = list(map(float, cv.coords(item)))

            if typ == 'oval':
                # draw a circle for each dot (filled)
                x1, y1, x2, y2 = coords
                cx = shift((x1 + x2) / 2, min_x)
                cy = shift((y1 + y2) / 2, min_y)
                r = (x2 - x1) / 2
                fillcol = cv.itemcget(item, 'fill')
                dwg.add(
                    dwg.circle(
                        center=(cx, cy),
                        r=r,
                        fill=fillcol,
                        stroke='none'
                    )
                )

            elif typ == 'line':
                # draw a line with stroke-width = current line thickness
                x1, y1, x2, y2 = coords
                dwg.add(
                    dwg.line(
                        start=(shift(x1, min_x), shift(y1, min_y)),
                        end=(shift(x2, min_x), shift(y2, min_y)),
                        stroke='#000',
                        stroke_width=lw
                    )
                )

        dwg.save()

    def _export_png(self, path):
        if Image is None:
            messagebox.showerror('Export', 'Pillow required')
            return
        scale = simpledialog.askinteger('PNG scale', 'Scale (1–10)',
                                        initialvalue=1, minvalue=1, maxvalue=10)
        if not scale:
            return

        cv = self.cv
        # Temporarily hide items that are currently invisible so the PostScript
        # contains **only** what’s shown.
        hidden = [i for i in cv.find_all()
                  if cv.itemcget(i, 'state') == 'hidden']
        for i in hidden:
            cv.itemconfigure(i, state='disabled')

        ps = cv.postscript(colormode='color')
        for i in hidden:
            cv.itemconfigure(i, state='hidden')      # restore

        img = Image.open(io.BytesIO(ps.encode('utf-8')))
        w, h = img.size
        img = img.resize((w*scale, h*scale), Image.ANTIALIAS)
        img.save(path)
