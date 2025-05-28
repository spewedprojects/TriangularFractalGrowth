import tkinter as tk
from math import cos, sin, radians


# ------------------------------------------------------------
#  Triangular-Growth Prototype  —  v0.5
#  • Fixes BOTH-side mode so subsequent layers follow a coherent
#    perimeter path instead of criss-crossing.
#      – children built on the LEFT side are listed in forward order
#      – children on the RIGHT side are appended *in reverse*,
#        giving a smooth wrap-around (like tracing the hull).
#  • All single-side logic unchanged.  Undo / Redo still work.
# ------------------------------------------------------------


class TriGrowthApp:
    """Interactive prototype for the equilateral-triangle growth idea."""

    def __init__(self, master):
        self.master = master
        self.master.title("Triangular Growth Prototype")
        self.canvas = tk.Canvas(master, width=1000, height=700, bg="white")
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ctrl = tk.Frame(master)
        ctrl.pack(side=tk.RIGHT, fill=tk.Y)

        # Buttons
        tk.Button(ctrl, text="Add Layer", command=self.add_layer).pack(padx=6, pady=(6, 2), fill=tk.X)
        tk.Button(ctrl, text="Undo Layer", command=self.undo_layer).pack(padx=6, pady=2, fill=tk.X)
        tk.Button(ctrl, text="Redo Layer", command=self.redo_layer).pack(padx=6, pady=2, fill=tk.X)
        tk.Button(ctrl, text="Run to End", command=self.auto_run).pack(padx=6, pady=2, fill=tk.X)
        tk.Button(ctrl, text="Clear", command=self.clear).pack(padx=6, pady=2, fill=tk.X)

        # Triangle-side selector
        self.side_choice = tk.StringVar(value="LEFT")
        tk.Label(ctrl, text="Triangle Side", font=("Arial", 10, "bold")).pack(pady=(10, 0))
        for side in ("LEFT", "RIGHT", "BOTH"):
            tk.Radiobutton(ctrl, text=side, variable=self.side_choice, value=side).pack(anchor="w")

        # Internal state
        self.rows: list[list[tuple[float, float]]] = []
        self.layer_tags: list[str] = []
        self.redo_stack: list[tuple[list[tuple[float, float]], str]] = []
        self.lock_seed = False

        self.canvas.bind("<Button-1>", self.add_seed_point)

    # --------------------------------------------------
    #  Event handlers
    # --------------------------------------------------

    def add_seed_point(self, event):
        if self.lock_seed:
            return
        if not self.rows:
            self.rows.append([])
        self.rows[0].append((event.x, event.y))
        self._draw_point(event.x, event.y, color="black")

    def add_layer(self):
        if not self.rows or len(self.rows[-1]) < 2:
            return
        self.lock_seed = True
        self.redo_stack.clear()

        curr = self.rows[-1]
        mode = self.side_choice.get()
        tag = f"layer_{len(self.layer_tags)}"

        next_row: list[tuple[float, float]] = []

        if mode == "BOTH":
            left_children, right_children = [], []
            for i in range(len(curr) - 1):
                p, q = curr[i], curr[i + 1]
                cl = self._third_vertex(p, q, +1)
                cr = self._third_vertex(p, q, -1)
                left_children.append(cl)
                right_children.append(cr)
                self._draw_triangle(p, q, cl, tag)
                self._draw_triangle(p, q, cr, tag)
            next_row = left_children + right_children[::-1]  # wrap-around hull
        else:
            sign = +1 if mode == "LEFT" else -1
            for i in range(len(curr) - 1):
                p, q = curr[i], curr[i + 1]
                c = self._third_vertex(p, q, sign)
                next_row.append(c)
                self._draw_triangle(p, q, c, tag)

        self.rows.append(next_row)
        self.layer_tags.append(tag)

    def undo_layer(self):
        if len(self.rows) <= 1:
            return
        row = self.rows.pop()
        tag = self.layer_tags.pop()
        self.canvas.itemconfigure(tag, state="hidden")
        self.redo_stack.append((row, tag))
        if len(self.rows) == 1:
            self.lock_seed = False

    def redo_layer(self):
        if not self.redo_stack:
            return
        row, tag = self.redo_stack.pop()
        self.canvas.itemconfigure(tag, state="normal")
        self.rows.append(row)
        self.layer_tags.append(tag)
        self.lock_seed = True

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
        self.lock_seed = False

    # --------------------------------------------------
    #  Geometry helpers
    # --------------------------------------------------

    @staticmethod
    def _third_vertex(p, q, sign):
        vx, vy = q[0] - p[0], q[1] - p[1]
        angle = radians(60) * sign
        rx = vx * cos(angle) - vy * sin(angle)
        ry = vx * sin(angle) + vy * cos(angle)
        return p[0] + rx, p[1] + ry

    # --------------------------------------------------
    #  Drawing helpers
    # --------------------------------------------------

    def _draw_point(self, x, y, color="red", r=3, tag=""):
        self.canvas.create_oval(x - r, y - r, x + r, y + r,
                                fill=color, outline="", tags=tag)

    def _draw_triangle(self, p, q, r, tag):
        self.canvas.create_line(p[0], p[1], q[0], q[1], tags=tag)
        self.canvas.create_line(q[0], q[1], r[0], r[1], tags=tag)
        self.canvas.create_line(r[0], r[1], p[0], p[1], tags=tag)
        self._draw_point(*r, tag=tag)


if __name__ == "__main__":
    root = tk.Tk()
    TriGrowthApp(root)
    root.mainloop()