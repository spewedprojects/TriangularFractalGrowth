# canvas_manager.py

import tkinter as tk
from math import radians
import geometry as gm
import drawing as drw
from state import LayerState

# If you want bigger “height jumps,” you can increase this.
# The seed row (layer 0) sits at z = 0.
# The first actual triangular layer (idx=0) will be at z = 1*HEIGHT_STEP, and so on.
HEIGHT_STEP = 100.0   # <-- you mentioned setting this to 50, for example


class CanvasManager:
    """
    Encapsulates all canvas‐drawing and 3D bookkeeping logic:
      • seed‐dot placement & dragging
      • building each new 2D layer (and recording its 3D counterpart)
      • undo / redo / auto_run / clear
      • computing the “true silhouette” (outer hull) in 2D
      • visibility toggles, line‐thickness changes, and scrollregion updates
      • preparing a slanted‐face OBJ mesh for export
    """

    def __init__(self, canvas: tk.Canvas, line_thickness_var: tk.IntVar):
        self.cv = canvas
        self.line_thickness_var = line_thickness_var

        # Each “row” in 2D is state.rows[i], for i=0,1,2,…
        self.state = LayerState()

        # For 3D export, we keep:
        #   layers_3d[i] = list of (x, y, z) points for layer i.
        #   triangles_3d   = list of ((x1,y1,z1), (x2,y2,z2), (x3,y3,z3)) triplets.
        self.layers_3d = []
        self.triangles_3d = []

        # Helpers for dragging seed points
        self._drag_i = None
        self._drag_id = None

        # Bind mouse events on the canvas
        self.cv.bind('<Button-1>', self.on_click)
        self.cv.bind('<B1-Motion>', self.on_drag)
        self.cv.bind('<ButtonRelease-1>', self.on_release)

    # ---------------------------------------- Seed‐dot placement / dragging
    def on_click(self, event):
        """
        If seed‐drawing isn’t locked, map the click to canvas coords,
        check if it hits an existing seed dot (to initiate drag), otherwise add
        a new seed dot at this position, and redraw the “seed line” and hull.
        """
        if self.state.seed_locked:
            return

        x = self.cv.canvasx(event.x)
        y = self.cv.canvasy(event.y)

        if not self.state.rows:
            self.state.rows.append([])

        # Hit‐test: is the click within 3×DOT_R of an existing seed?
        for i, (px, py) in enumerate(self.state.rows[0]):
            if (x - px)**2 + (y - py)**2 <= (drw.DOT_R * 3)**2:
                self._drag_i = i
                self._drag_id = self.cv.find_closest(px, py)[0]
                return

        # Otherwise, add a brand‐new seed dot
        self.state.rows[0].append((x, y))
        drw.draw_point(self.cv, x, y, 'black', 'seed')

        # Draw the “seed line” from the previous seed to this one
        if len(self.state.rows[0]) > 1:
            p, q = self.state.rows[0][-2], self.state.rows[0][-1]
            self.cv.create_line(
                p[0], p[1], q[0], q[1],
                tags=('seed', 'row'),
                width=self.line_thickness_var.get()
            )

        # Recompute the 2D hull whenever the seed row changes
        self.update_hull()

    def on_drag(self, event):
        """
        If we’re dragging a seed dot, update its position, redraw the seed line,
        and recompute the 2D hull.
        """
        if self._drag_i is None:
            return

        x = self.cv.canvasx(event.x)
        y = self.cv.canvasy(event.y)
        self.state.rows[0][self._drag_i] = (x, y)
        self.cv.coords(
            self._drag_id,
            x - drw.DOT_R, y - drw.DOT_R,
            x + drw.DOT_R, y + drw.DOT_R
        )

        # Re‐draw the entire seed‐line
        self.cv.delete('seed_line')
        for i in range(len(self.state.rows[0]) - 1):
            p, q = self.state.rows[0][i], self.state.rows[0][i+1]
            self.cv.create_line(
                p[0], p[1], q[0], q[1],
                tags=('seed_line', 'row'),
                width=self.line_thickness_var.get()
            )

        self.update_hull()

    def on_release(self, _):
        """Drop the dragged seed dot."""
        self._drag_i = None
        self._drag_id = None

    # ---------------------------------------- Layer generation (2D + 3D)
    def add_layer(self, side_var: tk.StringVar):
        """
        Build the next “generation” of points from the last 2D row. Then:
          1. Draw each 2D equilateral triangle on the canvas.
          2. Record each triangle as a slanted 3D face:
             • p, q at z = parent_z = (idx)*HEIGHT_STEP
             • c at z = child_z = (idx+1)*HEIGHT_STEP
          3. Store the child row in state.rows & layers_3d.
          4. Recompute the 2D hull & apply visibility toggles.
        """
        if not self.state.rows or len(self.state.rows[-1]) < 2:
            return

        self.state.seed_locked = True
        idx = len(self.state.tags)            # idx = 0 for the very first added layer
        tag = f'ly{idx}'
        colour = drw.layer_colour(idx)
        w = self.line_thickness_var.get()

        # Compute parent_z and child_z so that the first layer is at z = HEIGHT_STEP, not z = 0
        parent_z = idx * HEIGHT_STEP    # idx = 0 → parent_z = 0  (seed row sits at z=0)
        child_z  = (idx + 1) * HEIGHT_STEP

        if side_var.get() == 'BOTH':
            # For BOTH, we keep a separate left_branch/right_branch (as before)
            if self.state.left_branch is None:
                self.state.left_branch  = list(self.state.rows[-1])
                self.state.right_branch = list(self.state.rows[-1])

            # Build left‐side triangles + record 3D slanted faces
            nl_2d = self._make_next(
                self.state.left_branch, +1, tag, colour, w, parent_z, child_z
            )
            # Build right‐side triangles + record 3D slanted faces
            nr_2d = self._make_next(
                self.state.right_branch, -1, tag, colour, w, parent_z, child_z
            )
            self.state.left_branch, self.state.right_branch = nl_2d, nr_2d
            new_row_2d = nl_2d + nr_2d

        else:
            sign = +1 if side_var.get() == 'LEFT' else -1
            new_row_2d = self._make_next(
                self.state.rows[-1], sign, tag, colour, w, parent_z, child_z
            )
            self.state.left_branch = self.state.right_branch = None

        # Push the new 2D row into our LayerState
        self.state.push(new_row_2d, tag)

        # Record the new row’s 3D coordinates at child_z
        new_row_3d = [(x, y, child_z) for (x, y) in new_row_2d]
        self.layers_3d.append(new_row_3d)

        self.update_hull()
        self.update_visibility()

    def _make_next(self, row_2d, side, tag, colour, width, parent_z, child_z):
        """
        Helper that:
        • Takes a 2D row “row_2d” of length N.
        • For each consecutive pair (p, q), builds the equilateral c = third_vertex(p,q,side).
        • Draws the 2D triangle on the canvas.
        • Records exactly one 3D triangle face (p3d, q3d, c3d) with p, q at parent_z and c at child_z.
        • Returns the new 2D “children_2d” list of length N-1.
        """
        children_2d = []

        for i in range(len(row_2d) - 1):
            p2d = row_2d[i]
            q2d = row_2d[i+1]
            c2d = gm.third_vertex(p2d, q2d, side)
            children_2d.append(c2d)

            # DRAW the equilateral triangle on the 2D canvas
            drw.draw_triangle(self.cv, p2d, q2d, c2d, tag, colour, width)

            # RECORD the slanted 3D face:
            p3d = (p2d[0], p2d[1], parent_z)
            q3d = (q2d[0], q2d[1], parent_z)
            c3d = (c2d[0], c2d[1], child_z)
            self.triangles_3d.append((p3d, q3d, c3d))

        # Finally, draw the “row‐line” in 2D connecting consecutive children_2d
        for i in range(len(children_2d) - 1):
            a, b = children_2d[i], children_2d[i+1]
            self.cv.create_line(
                a[0], a[1], b[0], b[1],
                tags=(tag, 'row'),
                width=width
            )

        return children_2d

    def undo_layer(self):
        """
        Hide & pop the last 2D layer, then remove its 3D layer and any triangle
        faces at that layer’s height from triangles_3d.
        """
        tag = self.state.pop()
        if not tag:
            return

        self.cv.itemconfigure(tag, state='hidden')
        self.state.undone.add(tag)

        # Pop the last 3D layer (if it exists)
        if self.layers_3d:
            popped_layer = self.layers_3d.pop()
            # All vertices in popped_layer share the same child_z
            z_removed = popped_layer[0][2]
            # Remove any 3D triangles whose child vertex had z = z_removed
            self.triangles_3d = [
                tri for tri in self.triangles_3d if tri[2][2] != z_removed
            ]

        self.update_hull()
        self.update_visibility()

    def redo_layer(self, side_var: tk.StringVar):
        """
        Un‐hide the last hidden 2D layer, then re‐build its 3D slanted faces exactly
        as in add_layer() (using the same parent_z/child_z logic).
        """
        tag = self.state.redo_layer()
        if not tag:
            return

        self.state.undone.discard(tag)
        self.cv.itemconfigure(tag, state='normal')

        idx = len(self.state.tags) - 1  # index of the re‐added layer
        parent_z = idx * HEIGHT_STEP
        child_z  = (idx + 1) * HEIGHT_STEP
        row2d = self.state.rows[-1]
        row3d = [(x, y, child_z) for (x, y) in row2d]
        self.layers_3d.append(row3d)

        parent_row = self.state.rows[-2]

        if side_var.get() == 'BOTH':
            # BOTH‐mode: reconstruct left‐side faces and right‐side faces
            for i in range(len(parent_row) - 1):
                p2d, q2d = parent_row[i], parent_row[i+1]
                c2d = gm.third_vertex(p2d, q2d, +1)
                self.triangles_3d.append(((p2d[0], p2d[1], parent_z),
                                           (q2d[0], q2d[1], parent_z),
                                           (c2d[0], c2d[1], child_z)))
            for i in range(len(parent_row) - 1):
                p2d, q2d = parent_row[i], parent_row[i+1]
                c2d = gm.third_vertex(p2d, q2d, -1)
                self.triangles_3d.append(((p2d[0], p2d[1], parent_z),
                                           (q2d[0], q2d[1], parent_z),
                                           (c2d[0], c2d[1], child_z)))
        else:
            sign = +1 if side_var.get() == 'LEFT' else -1
            for i in range(len(parent_row) - 1):
                p2d, q2d = parent_row[i], parent_row[i+1]
                c2d = gm.third_vertex(p2d, q2d, sign)
                self.triangles_3d.append(((p2d[0], p2d[1], parent_z),
                                           (q2d[0], q2d[1], parent_z),
                                           (c2d[0], c2d[1], child_z)))

        self.update_hull()
        self.update_visibility()

    def auto_run(self, side_var: tk.StringVar):
        """Keep generating layers (2D+3D) until only two points remain (unless BOTH)."""
        if side_var.get() == 'BOTH':
            return
        while self.state.rows and len(self.state.rows[-1]) > 2:
            self.add_layer(side_var)

    def clear(self):
        """Delete all 2D items, reset state, and wipe out all 3D data."""
        self.cv.delete('all')
        self.state = LayerState()
        self.layers_3d.clear()
        self.triangles_3d.clear()
        self.cv.configure(scrollregion=(0, 0, 1000, 700))
        self.update_hull()

    # ----------------------------------------------- Visibility & Thickness
    def update_visibility(self):
        """
        Show/hide canvas items based on the IntVar toggles,
        then re‐hide any layers currently “undone.”
        """
        self.cv.itemconfigure('dot',  state=('normal' if self.v_dots.get() else 'hidden'))
        self.cv.itemconfigure('row',  state=('normal' if self.v_rows.get() else 'hidden'))
        self.cv.itemconfigure('tri',  state=('normal' if self.v_tris.get() else 'hidden'))
        self.cv.itemconfigure('hull', state=('normal' if self.v_hull.get() else 'hidden'))

        for t in self.state.undone:
            self.cv.itemconfigure(t, state='hidden')

    def update_thickness(self):
        """Update the width of every 'row', 'tri', and 'hull' line to match the spinbox."""
        w = self.line_thickness_var.get()
        for tag in ('row', 'tri', 'hull'):
            self.cv.itemconfigure(tag, width=w)

    # ---------------------------------------- True outer silhouette (“Outer Hull”)
    def update_hull(self):
        """
        Re‐draw the “true” boundary silhouette, using only triangle edges that appear once.
        Draw each loop, then update scrollregion so the entire structure can be panned.
        """
        cv = self.cv
        cv.delete('hull')

        # 1) Count each undirected triangle edge (tag='tri') once per occurrence
        edge_cnt = {}
        for item in cv.find_withtag('tri'):
            coords = list(map(int, map(round, cv.coords(item))))
            p = (coords[0], coords[1])
            q = (coords[2], coords[3])
            key = tuple(sorted((p, q)))
            edge_cnt[key] = edge_cnt.get(key, 0) + 1

        # 2) Keep only those edges that appear exactly once → the mesh’s outer boundary
        boundary = [edge for edge, count in edge_cnt.items() if count == 1]
        if len(boundary) < 3:
            # Even if no hull to draw, update scrollregion so scrolling works
            self.cv.configure(scrollregion=self.cv.bbox('all') or (0, 0, 1000, 700))
            self.update_visibility()
            return

        # 3) Build adjacency: vertex → [neighbour1, neighbour2, …]
        adj = {}
        for p, q in boundary:
            adj.setdefault(p, []).append(q)
            adj.setdefault(q, []).append(p)

        # 4) Walk each closed loop using a visited‐edge set
        visited = set()
        loops = []
        for start in adj:
            # If all edges incident to ‘start’ have been visited, skip
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

        # 5) Draw all boundary‐loops as a continuous hull
        w = self.line_thickness_var.get()
        for loop in loops:
            for i in range(len(loop) - 1):
                p, q = loop[i], loop[i+1]
                cv.create_line(
                    p[0], p[1], q[0], q[1],
                    tags=('hull',),
                    width=w
                )

        # 6) Update scrollregion so you can pan around the entire canvas
        self.cv.configure(scrollregion=self.cv.bbox('all') or (0, 0, 1000, 700))
        self.update_visibility()
