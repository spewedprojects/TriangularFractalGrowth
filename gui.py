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
        self.cv = tk.Canvas(root, width=1000, height=700, bg='white')
        self.cv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ctrl = tk.Frame(root); ctrl.pack(side=tk.RIGHT, fill=tk.Y)

        for txt, fn in (('Add Layer', self.add_layer),
                        ('Undo Layer', self.undo_layer),
                        ('Redo Layer', self.redo_layer),
                        ('Run to End', self.auto_run),
                        ('Export', self.export_dialog),
                        ('Clear', self.clear)):
            tk.Button(ctrl, text=txt, command=fn).pack(fill=tk.X, padx=6, pady=2)

        self.side = tk.StringVar(value='LEFT')
        tk.Label(ctrl, text='Triangle Side', font=('Arial', 10, 'bold')).pack(pady=(10,0))
        for s in ('LEFT', 'RIGHT', 'BOTH'):
            tk.Radiobutton(ctrl, text=s, variable=self.side, value=s).pack(anchor='w')

        # --- visibility toggles
        tk.Label(ctrl, text='Visibility', font=('Arial', 10, 'bold')).pack(pady=(10,0))
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

        self.state = LayerState()
        self._drag_i = None
        self._drag_id = None

        self.cv.bind('<Button-1>', self.on_click)
        self.cv.bind('<B1-Motion>', self.on_drag)
        self.cv.bind('<ButtonRelease-1>', self.on_release)

    # ------------------------------------------------ seed editing
    def on_click(self, e):
        if self.state.seed_locked:
            return
        if not self.state.rows:
            self.state.rows.append([])

        for i, (x, y) in enumerate(self.state.rows[0]):
            if (e.x-x)**2 + (e.y-y)**2 <= (drw.DOT_R*3)**2:
                self._drag_i = i
                self._drag_id = self.cv.find_closest(x, y)[0]
                return

        self.state.rows[0].append((e.x, e.y))
        drw.draw_point(self.cv, e.x, e.y, 'black', 'seed')
        if len(self.state.rows[0]) > 1:
            p, q = self.state.rows[0][-2], self.state.rows[0][-1]
            self.cv.create_line(*p, *q, tags=('seed', 'row'))
        self.update_hull()

    def on_drag(self, e):
        if self._drag_i is None:
            return
        self.state.rows[0][self._drag_i] = (e.x, e.y)
        self.cv.coords(self._drag_id,
                       e.x-drw.DOT_R, e.y-drw.DOT_R,
                       e.x+drw.DOT_R, e.y+drw.DOT_R)
        self.cv.delete('seed_line')
        for i in range(len(self.state.rows[0])-1):
            p, q = self.state.rows[0][i], self.state.rows[0][i+1]
            self.cv.create_line(*p, *q, tags=('seed_line', 'row'))
        self.update_hull()

    def on_release(self, _):
        self._drag_i = self._drag_id = None

    # ------------------------------------------------ layer ops
    def add_layer(self):
        if not self.state.rows or len(self.state.rows[-1]) < 2:
            return
        self.state.seed_locked = True
        idx = len(self.state.tags)
        tag = f'ly{idx}'
        colour = drw.layer_colour(idx)

        if self.side.get() == 'BOTH':
            if self.state.left_branch is None:
                self.state.left_branch = self.state.rows[-1][:]
                self.state.right_branch = self.state.rows[-1][:]
            nl = self._make_next(self.state.left_branch, +1, tag, colour)
            nr = self._make_next(self.state.right_branch, -1, tag, colour)
            self.state.left_branch, self.state.right_branch = nl, nr
            new_row = nl + nr
        else:
            sign = +1 if self.side.get() == 'LEFT' else -1
            new_row = self._make_next(self.state.rows[-1], sign, tag, colour)
            self.state.left_branch = self.state.right_branch = None

        self.state.push(new_row, tag)
        self.update_hull()
        self.update_visibility()

    def _make_next(self, row, side, tag, col):
        children = []
        for i in range(len(row) - 1):
            p, q = row[i], row[i+1]
            c = gm.third_vertex(p, q, side)
            children.append(c)
            drw.draw_triangle(self.cv, p, q, c, tag, col)

        for i in range(len(children) - 1):
            self.cv.create_line(*children[i], *children[i+1],
                                tags=(tag, 'row'))
        return children

    def undo_layer(self):
        tag = self.state.pop()
        if tag:
            self.cv.itemconfigure(tag, state='hidden')
            self.state.undone.add(tag)  # ← NEW
            self.update_hull()
            self.update_visibility()

    def redo_layer(self):
        tag = self.state.redo_layer()
        if tag:
            self.state.undone.discard(tag)  # ← NEW
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
        self.update_hull()

    # ------------------------------------------------ visibility + hull
    def update_visibility(self):
        cv = self.cv
        cv.itemconfigure('dot', state='normal' if self.v_dots.get() else 'hidden')
        cv.itemconfigure('row', state='normal' if self.v_rows.get() else 'hidden')
        cv.itemconfigure('tri', state='normal' if self.v_tris.get() else 'hidden')
        cv.itemconfigure('hull', state='normal' if self.v_hull.get() else 'hidden')

        # ← NEW: make sure layers in "undone" stay hidden
        for tag in self.state.undone:
            cv.itemconfigure(tag, state='hidden')

    # ------------------------------------------------ true outer silhouette
    def update_hull(self):
        cv = self.cv
        cv.delete('hull')

        # 1. gather undirected edges of every triangle
        edge_cnt = {}  # {(p,q): occurrences}
        for item in cv.find_withtag('tri'):
            x1, y1, x2, y2 = map(int, map(round, cv.coords(item)))
            p = (x1, y1);
            q = (x2, y2)
            key = tuple(sorted([p, q]))
            edge_cnt[key] = edge_cnt.get(key, 0) + 1

        # 2. boundary edges: appear exactly once
        boundary = [e for e, n in edge_cnt.items() if n == 1]
        if len(boundary) < 3:
            self.update_visibility()
            return

        # 3. adjacency   vertex -> [neigh, neigh]
        adj = {}
        for p, q in boundary:
            adj.setdefault(p, []).append(q)
            adj.setdefault(q, []).append(p)

        # 4. walk every loop using a visited-edge set
        visited = set()  # edge keys we've drawn
        loops = []
        for start in list(adj):
            # skip vertices whose incident edges are done
            if all(tuple(sorted((start, n))) in visited for n in adj[start]):
                continue
            loop = [start]
            prev, curr = None, start
            while True:
                # pick the first neighbour whose edge is still unvisited
                nxt = None
                for n in adj[curr]:
                    key = tuple(sorted((curr, n)))
                    if key not in visited:
                        nxt = n
                        visited.add(key)
                        break
                if nxt is None:
                    break  # open fragment, shouldn’t happen
                loop.append(nxt)
                if nxt == start:
                    break  # closed the loop
                prev, curr = curr, nxt
            if len(loop) > 2:
                loops.append(loop)

        # 5. draw the loops
        for loop in loops:
            for i in range(len(loop) - 1):
                p, q = loop[i], loop[i + 1]
                cv.create_line(*p, *q, tags=('hull',))

        # 6. honour visibility toggle
        self.update_visibility()

    # ------------------------------------------------ export
    def export_dialog(self):
        fmt = simpledialog.askstring('Export', 'Format (svg/png):',
                                     initialvalue='svg')
        if not fmt:
            return
        fmt = fmt.lower()
        if fmt not in {'svg', 'png'}:
            messagebox.showerror('Export', 'Unsupported format')
            return
        file = filedialog.asksaveasfilename(defaultextension=f'.{fmt}')
        if not file:
            return
        if fmt == 'svg':
            self._export_svg(file)
        else:
            self._export_png(file)

    def _export_svg(self, path):
        try:
            import svgwrite
        except ImportError:
            messagebox.showerror('Export', 'svgwrite not installed')
            return
        w, h = int(self.cv['width']), int(self.cv['height'])
        dwg = svgwrite.Drawing(path, size=(w, h))
        for item in self.cv.find_all():
            typ = self.cv.type(item)
            coords = self.cv.coords(item)
            if typ == 'oval':
                x1, y1, x2, y2 = coords
                cx, cy = (x1+x2)/2, (y1+y2)/2
                r = (x2 - x1) / 2
                dwg.add(dwg.circle(center=(cx, cy), r=r,
                                   fill=self.cv.itemcget(item, 'fill')))
            elif typ == 'line':
                dwg.add(dwg.line(start=(coords[0], coords[1]),
                                 end=(coords[2], coords[3]),
                                 stroke='#000'))
        dwg.save()

    def _export_png(self, path):
        if Image is None:
            messagebox.showerror('Export', 'Pillow required')
            return
        scale = simpledialog.askinteger('PNG scale', 'Scale (1–10)',
                                        initialvalue=1, minvalue=1, maxvalue=10)
        if not scale:
            return
        ps = self.cv.postscript(colormode='color')
        img = Image.open(io.BytesIO(ps.encode('utf-8')))
        w, h = img.size
        img = img.resize((w*scale, h*scale), Image.ANTIALIAS)
        img.save(path)
