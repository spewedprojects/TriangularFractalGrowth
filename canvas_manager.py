# canvas_manager.py

import tkinter as tk
import math
import geometry as gm
import drawing as drw
from state import LayerState

# --------------------------------------------------------
# Each triangle slants at exactly 60°.
# LEFT  branch children go into negative Z;
# RIGHT branch children go into positive Z.
# --------------------------------------------------------

# Precompute tan(60°) = √3
TAN45 = 1

class CanvasManager:
    """
    Encapsulates:
      • 2D drawing (seed points, equilateral triangles, silhouette, row‐lines)
      • 3D bookkeeping so each triangle is slanted at 60°:
            LEFT  ⇒ child_z = parent_z – (L * √3)
            RIGHT ⇒ child_z = parent_z + (L * √3)
      • Undo / Redo / AutoRun / Clear
      • Visibility toggles & line thickness
      • Scrollregion updates
      • triangles_3d: list of ((x1,y1,z1), (x2,y2,z2), (x3,y3,z3)) triplets
    """

    def __init__(self, canvas: tk.Canvas, line_thickness_var: tk.IntVar):
        self.cv = canvas
        self.line_thickness_var = line_thickness_var

        # 2D state (rows of 2D points & hidden/visible tags)
        self.state = LayerState()

        # 3D bookkeeping for OBJ export
        #   layers_3d[i] = list of (x,y,z) for the i-th row
        #   triangles_3d = list of ((p3d),(q3d),(c3d)) triplets
        self.layers_3d = []
        self.triangles_3d = []

        # Helpers for dragging seed points
        self._drag_i = None
        self._drag_id = None

        # Bind mouse events
        self.cv.bind('<Button-1>', self.on_click)
        self.cv.bind('<B1-Motion>', self.on_drag)
        self.cv.bind('<ButtonRelease-1>', self.on_release)


    # ---------------------- Seed‐Dot Editing ----------------------
    def on_click(self, event):
        """
        Convert (event.x, event.y) to canvas coords (x, y). If seed drawing is unlocked:
          1) If we hit an existing seed dot ⇒ begin drag.
          2) Else add a new seed dot, draw a “seed line” to the previous,
             then recalc the silhouette.
        """
        if self.state.seed_locked:
            return

        x = self.cv.canvasx(event.x)
        y = self.cv.canvasy(event.y)

        if not self.state.rows:
            # First time: create the seed row
            self.state.rows.append([])

        # Hit‐test any existing seed dot (within 3×DOT_R)
        for i, (px, py) in enumerate(self.state.rows[0]):
            if (x - px)**2 + (y - py)**2 <= (drw.DOT_R * 3)**2:
                self._drag_i = i
                self._drag_id = self.cv.find_closest(px, py)[0]
                return

        # Otherwise, add a brand‐new seed dot
        self.state.rows[0].append((x, y))
        drw.draw_point(self.cv, x, y, 'black', 'seed')

        # If more than one seed, draw the seed‐line to the previous seed
        if len(self.state.rows[0]) > 1:
            p, q = self.state.rows[0][-2], self.state.rows[0][-1]
            self.cv.create_line(
                p[0], p[1], q[0], q[1],
                tags=('seed','row'),
                width=self.line_thickness_var.get()
            )

        # Recompute the silhouette (outer hull) whenever the seed row changes
        self.update_hull()


    def on_drag(self, event):
        """
        If dragging a seed dot, update its position, redraw the entire seed‐line,
        then recalc the silhouette.
        """
        if self._drag_i is None:
            return

        x = self.cv.canvasx(event.x)
        y = self.cv.canvasy(event.y)
        self.state.rows[0][self._drag_i] = (x, y)

        # Move the oval under the cursor
        self.cv.coords(
            self._drag_id,
            x - drw.DOT_R, y - drw.DOT_R,
            x + drw.DOT_R, y + drw.DOT_R
        )

        # Redraw the “seed line” by connecting all seed dots in row 0
        self.cv.delete('seed_line')
        for i in range(len(self.state.rows[0]) - 1):
            p, q = self.state.rows[0][i], self.state.rows[0][i+1]
            self.cv.create_line(
                p[0], p[1], q[0], q[1],
                tags=('seed_line','row'),
                width=self.line_thickness_var.get()
            )

        self.update_hull()


    def on_release(self, _):
        """Stop dragging the seed dot."""
        self._drag_i = None
        self._drag_id = None


    # ---------------------- Layer Generation (2D + 3D) ----------------------
    def add_layer(self, side_var: tk.StringVar):
        """
        Build a new layer of equilateral triangles from the last 2D row. Each new
        triangle is recorded as a 60°‐slanted face in 3D:
           child_z = parent_z ± (L * √3),
        where L = distance(p2d, c2d). LEFT → negative Z, RIGHT → positive Z.
        """

        if not self.state.rows or len(self.state.rows[-1]) < 2:
            return

        self.state.seed_locked = True
        idx = len(self.state.tags)
        tag = f'ly{idx}'
        colour = drw.layer_colour(idx)
        w = self.line_thickness_var.get()

        # If this is the very first add_layer(), create a 3D version of the seed row at z=0
        if not self.layers_3d:
            seed2d = self.state.rows[0]
            seed3d = [(x, y, 0.0) for (x, y) in seed2d]
            self.layers_3d.append(seed3d)

        parent2d = self.state.rows[-1]
        parent3d = self.layers_3d[-1]

        if side_var.get() == 'BOTH':
            # In BOTH mode, we clone the entire parent row into two branches.
            if self.state.left_branch is None:
                self.state.left_branch  = list(parent2d)
                self.state.right_branch = list(parent2d)
                self.state.left3d  = list(parent3d)
                self.state.right3d = list(parent3d)

            # Build left-branch children (2D + 3D)
            l2d, l3d = self._make_next(
                self.state.left_branch, self.state.left3d,
                +1, tag, colour, w
            )
            # Build right-branch children (2D + 3D)
            r2d, r3d = self._make_next(
                self.state.right_branch, self.state.right3d,
                -1, tag, colour, w
            )

            # Update branches to be the newly created children for next time
            self.state.left_branch  = l2d
            self.state.right_branch = r2d
            self.state.left3d       = l3d
            self.state.right3d      = r3d

            new2d = l2d + r2d
            new3d = l3d + r3d

        else:
            sign = +1 if side_var.get() == 'LEFT' else -1
            new2d, new3d = self._make_next(parent2d, parent3d, sign, tag, colour, w)
            self.state.left_branch = self.state.right_branch = None
            self.state.left3d = self.state.right3d = None

        # Push new2d into 2D state and new3d into layers_3d
        self.state.push(new2d, tag)
        self.layers_3d.append(new3d)

        self.update_hull()
        self.update_visibility()


    def _make_next(self, parent2d, parent3d, side, tag, colour, width):
        """
        Given:
          parent2d =     [(x₁,y₁), (x₂,y₂), …, (xₙ,yₙ)]        length = n
          parent3d =     [(x₁,y₁,z₁), (x₂,y₂,z₂), …, (xₙ,yₙ,zₙ)]  length = n
        Build n−1 children as follows:
          1) Compute c2d = third_vertex(p2d, q2d, side).
          2) Draw the 2D triangle on the canvas.
          3) Compute L = distance(p2d, c2d).
          4) If side=+1 (LEFT):  c_z = p3d.z − (L * √3)
             If side=−1 (RIGHT): c_z = p3d.z + (L * √3)
          5) Let p3d, q3d come directly from parent3d[i], parent3d[i+1].
             Let c3d = (c2d.x, c2d.y, c_z).
          6) Append (p3d, q3d, c3d) to self.triangles_3d.
        Finally draw the 2D “row line” connecting consecutive children2d.

        Returns:
          children2d = [c2d₁, c2d₂, …]   length = (n−1)
          children3d = [c3d₁, c3d₂, …]   length = (n−1)
        """
        children2d = []
        children3d = []

        for i in range(len(parent2d) - 1):
            p2d = parent2d[i]
            q2d = parent2d[i+1]
            p3d = parent3d[i]
            q3d = parent3d[i+1]

            c2d = gm.third_vertex(p2d, q2d, side)
            children2d.append(c2d)

            # Draw the 2D equilateral triangle
            drw.draw_triangle(self.cv, p2d, q2d, c2d, tag, colour, width)

            # Compute horizontal distance L = dist(p2d, c2d)
            dx = c2d[0] - p2d[0]
            dy = c2d[1] - p2d[1]
            L = math.hypot(dx, dy)

            # Compute c_z at exactly 60°: Δz = L * √3
            if side == +1:
                # LEFT ⇒ negative Z
                c_z = p3d[2] - (L * TAN45)
            else:
                # RIGHT ⇒ positive Z
                c_z = p3d[2] + (L * TAN45)

            c3d = (c2d[0], c2d[1], c_z)

            # Record the 3D slanted face
            self.triangles_3d.append((p3d, q3d, c3d))
            children3d.append(c3d)

        # Draw the 2D “row‐line” connecting consecutive c2d’s
        for i in range(len(children2d) - 1):
            a, b = children2d[i], children2d[i+1]
            self.cv.create_line(
                a[0], a[1], b[0], b[1],
                tags=(tag, 'row'),
                width=width
            )

        return children2d, children3d


    def undo_layer(self):
        """
        Hide & pop the last 2D layer via state.pop(), then pop the last 3D row.
        Remove any triangles whose apex z is in that popped 3D row.
        """
        tag = self.state.pop()
        if not tag:
            return

        self.cv.itemconfigure(tag, state='hidden')
        self.state.undone.add(tag)

        if self.layers_3d:
            popped3d = self.layers_3d.pop()
            zvals = {z for (_, _, z) in popped3d}
            self.triangles_3d = [
                tri for tri in self.triangles_3d
                if tri[2][2] not in zvals
            ]

        self.update_hull()
        self.update_visibility()


    def redo_layer(self, side_var: tk.StringVar):
        """
        Un-hide the most recently undone 2D layer, then rebuild its 3D triangles
        exactly as in add_layer(), preserving shared vertices so the mesh remains
        fully interconnected.
        """
        tag = self.state.redo_layer()
        if not tag:
            return

        self.state.undone.discard(tag)
        self.cv.itemconfigure(tag, state='normal')

        idx = len(self.state.tags) - 1
        colour = drw.layer_colour(idx)
        w = self.line_thickness_var.get()

        # The “parent row” (2D & 3D) is one level back
        parent2d = self.state.rows[-2]
        parent3d = self.layers_3d[-1]

        if side_var.get() == 'BOTH':
            # Restore BOTH logic by cloning the entire parent row into two branches
            if self.state.left_branch is None:
                self.state.left_branch  = list(parent2d)
                self.state.right_branch = list(parent2d)
                self.state.left3d       = list(parent3d)
                self.state.right3d      = list(parent3d)

            l2d, l3d = self._make_next(
                self.state.left_branch, self.state.left3d,
                +1, tag, colour, w
            )
            r2d, r3d = self._make_next(
                self.state.right_branch, self.state.right3d,
                -1, tag, colour, w
            )
            self.state.left_branch  = l2d
            self.state.right_branch = r2d
            self.state.left3d       = l3d
            self.state.right3d      = r3d

            new2d = l2d + r2d
            new3d = l3d + r3d

        else:
            sign = +1 if side_var.get() == 'LEFT' else -1
            new2d, new3d = self._make_next(parent2d, parent3d, sign, tag, colour, w)
            self.state.left_branch = self.state.right_branch = None
            self.state.left3d = self.state.right3d = None

        self.layers_3d.append(new3d)
        self.update_hull()
        self.update_visibility()


    def auto_run(self, side_var: tk.StringVar):
        """
        Keep adding layers until the last row has ≤ 2 points.
        Skip if side_var='BOTH'.
        """
        if side_var.get() == 'BOTH':
            return
        while self.state.rows and len(self.state.rows[-1]) > 2:
            self.add_layer(side_var)


    def clear(self):
        """
        Delete all canvas items, reset 2D state & 3D lists,
        and reset scrollregion to (0,0,1000,700).
        """
        self.cv.delete('all')
        self.state = LayerState()
        self.layers_3d.clear()
        self.triangles_3d.clear()
        self.cv.configure(scrollregion=(0, 0, 1000, 700))
        self.update_hull()


    # ---------------------- Visibility & Line Thickness ----------------------
    def update_visibility(self):
        """
        Show/hide canvas items based on:
          • self.v_dots, self.v_rows, self.v_tris, self.v_hull
          • any layer tags in self.state.undone
        """
        self.cv.itemconfigure('dot',  state=('normal' if self.v_dots.get() else 'hidden'))
        self.cv.itemconfigure('row',  state=('normal' if self.v_rows.get() else 'hidden'))
        self.cv.itemconfigure('tri',  state=('normal' if self.v_tris.get() else 'hidden'))
        self.cv.itemconfigure('hull', state=('normal' if self.v_hull.get() else 'hidden'))

        for t in self.state.undone:
            self.cv.itemconfigure(t, state='hidden')


    def update_thickness(self):
        """
        Set every line tagged 'row', 'tri', or 'hull' to have width = spinbox value.
        """
        w = self.line_thickness_var.get()
        for tag in ('row', 'tri', 'hull'):
            self.cv.itemconfigure(tag, width=w)


    # ---------------------- True Outer‐Hull Silhouette ----------------------
    def update_hull(self):
        """
        Recompute the 2D boundary by:
          1) Counting each undirected edge among 'tri' lines,
          2) Keeping edges that appear exactly once,
          3) Building adjacency: vertex → [neighbors],
          4) Walking each closed loop,
          5) Drawing the loops as 'hull' lines,
          6) Updating scrollregion so the canvas can pan to show all content.
        """
        cv = self.cv
        cv.delete('hull')

        # 1) Count undirected occurrences of each 'tri' edge
        edge_cnt = {}
        for item in cv.find_withtag('tri'):
            coords = list(map(int, map(round, cv.coords(item))))
            p = (coords[0], coords[1])
            q = (coords[2], coords[3])
            key = tuple(sorted((p, q)))
            edge_cnt[key] = edge_cnt.get(key, 0) + 1

        # 2) Keep only edges that appear exactly once ⇒ boundary edges
        boundary = [e for e, cnt in edge_cnt.items() if cnt == 1]
        if len(boundary) < 3:
            # Even if no hull loops, update scrollregion so panning works
            self.cv.configure(scrollregion=self.cv.bbox('all') or (0, 0, 1000, 700))
            self.update_visibility()
            return

        # 3) Build adjacency: vertex → [neighbors]
        adj = {}
        for p, q in boundary:
            adj.setdefault(p, []).append(q)
            adj.setdefault(q, []).append(p)

        # 4) Walk each closed loop using a visited-edge set
        visited = set()
        loops = []
        for start in adj:
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

        # 5) Draw each boundary loop as a continuous hull line
        w = self.line_thickness_var.get()
        for loop in loops:
            for i in range(len(loop) - 1):
                p, q = loop[i], loop[i+1]
                cv.create_line(
                    p[0], p[1], q[0], q[1],
                    tags=('hull',), width=w
                )

        # 6) Update scrollregion so user can pan/zoom to see all content
        self.cv.configure(scrollregion=self.cv.bbox('all') or (0, 0, 1500, 1500))
        self.update_visibility()
