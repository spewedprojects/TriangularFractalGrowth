import tkinter as tk
from math import cos, sin, radians


# ------------------------------------------------------------
#  Triangular-Growth Prototype  —  v0.7  (visibility toggles)
#  • Adds three check‑boxes:  Show Dots, Show Row Lines, Show Triangles.
#      –  “Dots”        → tiny red vertices.
#      –  “Row Lines”   → edges that connect consecutive points in a row
#                         (no crossings, forms the visible hull/path).
#      –  “Triangles”   → the two new edges that close each equilateral.
#  • Each graphical item now carries *two* tags: a per‑layer tag
#    (e.g. “layer_3”) + a type tag (dot / row / tri).
#  • Toggling a check‑box simply sets itemconfigure(... state="hidden|normal")
#    on the corresponding type tag.
#  • Core geometry and BOTH‑mode logic unchanged from v0.6.
# ------------------------------------------------------------


class TriGrowthApp:
    def __init__(self, master):
        self.master = master
        self.master.title("Triangular Growth Prototype")
        self.canvas = tk.Canvas(master, width=1000, height=700, bg="white")
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ctrl = tk.Frame(master)
        ctrl.pack(side=tk.RIGHT, fill=tk.Y)

        # --- Action buttons -------------------------------------------------
        tk.Button(ctrl, text="Add Layer", command=self.add_layer).pack(padx=6, pady=(6, 2), fill=tk.X)
        tk.Button(ctrl, text="Undo Layer", command=self.undo_layer).pack(padx=6, pady=2, fill=tk.X)
        tk.Button(ctrl, text="Redo Layer", command=self.redo_layer).pack(padx=6, pady=2, fill=tk.X)
        tk.Button(ctrl, text="Run to End", command=self.auto_run).pack(padx=6, pady=2, fill=tk.X)
        tk.Button(ctrl, text="Clear", command=self.clear).pack(padx=6, pady=2, fill=tk.X)

        # --- Side selector --------------------------------------------------
        self.side_choice = tk.StringVar(value="LEFT")
        tk.Label(ctrl, text="Triangle Side", font=("Arial", 10, "bold")).pack(pady=(10, 0))
        for side in ("LEFT", "RIGHT", "BOTH"):
            tk.Radiobutton(ctrl, text=side, variable=self.side_choice, value=side).pack(anchor="w")

        # --- Visibility toggles --------------------------------------------
        tk.Label(ctrl, text="Visibility", font=("Arial", 10, "bold")).pack(pady=(10, 0))
        self.show_dots  = tk.IntVar(value=1)
        self.show_rows  = tk.IntVar(value=1)
        self.show_tris  = tk.IntVar(value=1)
        tk.Checkbutton(ctrl, text="Dots",       variable=self.show_dots, command=self.update_visibility).pack(anchor="w")
        tk.Checkbutton(ctrl, text="Row Lines",  variable=self.show_rows, command=self.update_visibility).pack(anchor="w")
        tk.Checkbutton(ctrl, text="Triangles",  variable=self.show_tris, command=self.update_visibility).pack(anchor="w")

        # --- Internal state -------------------------------------------------
        self.rows: list[list[tuple[float, float]]] = []      # composite rows
        self.layer_tags: list[str] = []
        self.redo_stack: list[tuple[list[tuple[float, float]], str]] = []
        self.lock_seed = False

        # BOTH‑mode separate branches
        self._left_branch = None
        self._right_branch = None

        self.canvas.bind("<Button-1>", self.add_seed_point)

    # ======================================================================
    #  Seed input
    # ======================================================================

    def add_seed_point(self, event):
        if self.lock_seed:
            return
        if not self.rows:
            self.rows.append([])
        self.rows[0].append((event.x, event.y))
        self._draw_point(event.x, event.y, color="black")

    # ======================================================================
    #  Layer generation
    # ======================================================================

    def add_layer(self):
        if not self.rows or len(self.rows[-1]) < 2:
            return
        self.lock_seed = True
        self.redo_stack.clear()

        mode = self.side_choice.get()
        tag = f"layer_{len(self.layer_tags)}"

        if mode == "BOTH":
            if self._left_branch is None:
                self._left_branch = self.rows[-1][:]
                self._right_branch = self.rows[-1][:]
            new_left  = self._next_row(self._left_branch,  +1, tag)
            new_right = self._next_row(self._right_branch, -1, tag)
            self._left_branch, self._right_branch = new_left, new_right
            composite = new_left + new_right
        else:
            sign = +1 if mode == "LEFT" else -1
            composite = self._next_row(self.rows[-1], sign, tag)
            self._left_branch = self._right_branch = None

        self.rows.append(composite)
        self.layer_tags.append(tag)
        self.update_visibility()  # respect current toggles for new items

    def _next_row(self, row, sign, tag):
        children = []
        for i in range(len(row) - 1):
            p, q = row[i], row[i + 1]
            c = self._third_vertex(p, q, sign)
            children.append(c)
            self._draw_triangle(p, q, c, tag)
        return children

    # ======================================================================
    #  Undo / Redo / Clear
    # ======================================================================

    def undo_layer(self):
        if len(self.rows) <= 1:
            return
        row = self.rows.pop()
        tag = self.layer_tags.pop()
        self.canvas.itemconfigure(tag, state="hidden")
        self.redo_stack.append((row, tag))
        if len(self.rows) == 1:
            self.lock_seed = False
        self.update_visibility()

    def redo_layer(self):
        if not self.redo_stack:
            return
        row, tag = self.redo_stack.pop()
        self.canvas.itemconfigure(tag, state="normal")
        self.rows.append(row)
        self.layer_tags.append(tag)
        self.lock_seed = True
        self.update_visibility()

    def auto_run(self):
        if self.side_choice.get() == "BOTH":
            return
        while self.rows and len(self.rows[-1]) > 2:
            self.add_layer()

    def clear(self):
        self.canvas.delete("all")
        self.rows.clear()
        self.layer_tags.clear()
        self.redo_stack.clear()
        self._left_branch = self._right_branch = None
        self.lock_seed = False

    # ======================================================================
    #  Visibility toggles
    # ======================================================================

    def update_visibility(self):
        self.canvas.itemconfigure('dot', state=('normal' if self.show_dots.get() else 'hidden'))
        self.canvas.itemconfigure('row', state=('normal' if self.show_rows.get() else 'hidden'))
        self.canvas.itemconfigure('tri', state=('normal' if self.show_tris.get() else 'hidden'))

    # ======================================================================
    #  Geometry helpers
    # ======================================================================

    @staticmethod
    def _third_vertex(p, q, sign):
        vx, vy = q[0] - p[0], q[1] - p[1]
        a = radians(60) * sign
        rx = vx * cos(a) - vy * sin(a)
        ry = vx * sin(a) + vy * cos(a)
        return p[0] + rx, p[1] + ry

    # ======================================================================
    #  Drawing helpers (tagged by type + layer)
    # ======================================================================

    def _draw_point(self, x, y, color="red", r=3, tag=""):
        self.canvas.create_oval(x - r, y - r, x + r, y + r,
                                fill=color, outline="", tags=(tag, 'dot'))

    def _draw_triangle(self, p, q, r, tag):
        # row edge (no crossings)
        self.canvas.create_line(p[0], p[1], q[0], q[1], tags=(tag, 'row'))
        # closing edges of equilateral triangle
        self.canvas.create_line(q[0], q[1], r[0], r[1], tags=(tag, 'tri'))
        self.canvas.create_line(r[0], r[1], p[0], p[1], tags=(tag, 'tri'))
        self._draw_point(*r, tag=tag)


if __name__ == "__main__":
    root = tk.Tk()
    TriGrowthApp(root)
    root.mainloop()
