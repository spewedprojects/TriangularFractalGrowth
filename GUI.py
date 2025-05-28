import tkinter as tk
from math import cos, sin, radians


# ------------------------------------------------------------
#  Triangular‑Growth Prototype  —  v0.2
#  • Fixes the geometry so the triangles are *truly* equilateral.
#  • Adds a **BOTH** option so you can grow on the left *and* right
#    sides in the same generation (rows get wider instead of shorter).
# ------------------------------------------------------------


class TriGrowthApp:
    """Interactive prototype for the equilateral‑triangle growth idea.

    ◼  Click on the white canvas to drop *seed* dots (first row).
    ◼  **Add Layer**   → generate the next generation of vertices.
    ◼  **Run to End**  → iterate automatically until row ≤ 2 vertices
                        (disabled when BOTH‑sided, because rows can expand).
    ◼  **Clear**       → start over.

    *Triangle Side* radio options:
        LEFT   – build on the left side of every segment
        RIGHT  – build on the right side only
        BOTH   – build on *both* sides (creates two vertices per segment)

    The geometry is purely standard‑library (Tkinter ships with Python).
    Tested on Python 3.11.
    """

    def __init__(self, master):
        self.master = master
        self.master.title("Triangular Growth Prototype")

        # ---------- UI layout ----------
        self.canvas = tk.Canvas(master, width=1000, height=700, bg="white")
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        ctrl = tk.Frame(master)
        ctrl.pack(side=tk.RIGHT, fill=tk.Y)

        self.add_layer_btn = tk.Button(ctrl, text="Add Layer", command=self.add_layer)
        self.add_layer_btn.pack(padx=6, pady=4, fill=tk.X)

        self.auto_btn = tk.Button(ctrl, text="Run to End", command=self.auto_run)
        self.auto_btn.pack(padx=6, pady=4, fill=tk.X)

        self.clear_btn = tk.Button(ctrl, text="Clear", command=self.clear)
        self.clear_btn.pack(padx=6, pady=4, fill=tk.X)

        self.side_choice = tk.StringVar(value="LEFT")
        tk.Label(ctrl, text="Triangle Side", font=("Arial", 10, "bold")).pack(pady=(10, 0))
        for side in ("LEFT", "RIGHT", "BOTH"):
            tk.Radiobutton(ctrl, text=side, variable=self.side_choice, value=side).pack(anchor="w")

        # ---------- internal state ----------
        self.rows: list[list[tuple[float, float]]] = []  # rows[0] = seed dots
        self.lock_seed = False  # after first layer, seed row is fixed

        # Bind mouse click for adding seed points
        self.canvas.bind("<Button-1>", self.add_seed_point)

    # ==========================================================
    #  Event Handlers
    # ==========================================================

    def add_seed_point(self, event):
        """Left‑click → add a dot to the seed row."""
        if self.lock_seed:
            return  # seed row is immutable after first layer
        if not self.rows:
            self.rows.append([])
        self.rows[0].append((event.x, event.y))
        self._draw_point(event.x, event.y, color="black")

    def add_layer(self):
        """Generate one new layer using the equilateral construction."""
        if not self.rows or len(self.rows[-1]) < 2:
            return  # need at least a segment
        self.lock_seed = True
        current = self.rows[-1]
        mode = self.side_choice.get()

        next_row: list[tuple[float, float]] = []
        for i in range(len(current) - 1):
            p, q = current[i], current[i + 1]

            # Build left, right, or both
            if mode in ("LEFT", "BOTH"):
                r_left = self._third_vertex(p, q, +1)
                next_row.append(r_left)
                self._draw_triangle(p, q, r_left)
            if mode in ("RIGHT", "BOTH"):
                r_right = self._third_vertex(p, q, -1)
                next_row.append(r_right)
                self._draw_triangle(p, q, r_right)

        self.rows.append(next_row)

    def auto_run(self):
        """Iterate until rows are exhausted (only for LEFT or RIGHT modes)."""
        if self.side_choice.get() == "BOTH":
            return  # in BOTH mode rows can grow outward; no natural end.
        while self.rows and len(self.rows[-1]) > 2:
            self.add_layer()

    def clear(self):
        self.canvas.delete("all")
        self.rows.clear()
        self.lock_seed = False

    # ==========================================================
    #  Geometry Helpers
    # ==========================================================

    @staticmethod
    def _third_vertex(p: tuple[float, float], q: tuple[float, float], sign: int):
        """Return coordinates of the third vertex of an equilateral triangle.

        - p, q   endpoints of the base segment.
        - sign   +1 → rotate 60° CCW,  -1 → 60° CW, *without* scaling.
        """
        vx, vy = q[0] - p[0], q[1] - p[1]
        angle = radians(60) * sign
        rx = vx * cos(angle) - vy * sin(angle)
        ry = vx * sin(angle) + vy * cos(angle)
        # No scaling — keep |v| unchanged for true equilateral.
        return p[0] + rx, p[1] + ry

    # ==========================================================
    #  Drawing Helpers
    # ==========================================================

    def _draw_point(self, x, y, color="red", r=3):
        self.canvas.create_oval(x - r, y - r, x + r, y + r, fill=color, outline="")

    def _draw_triangle(self, p, q, r):
        self.canvas.create_line(p[0], p[1], q[0], q[1])
        self.canvas.create_line(q[0], q[1], r[0], r[1])
        self.canvas.create_line(r[0], r[1], p[0], p[1])
        self._draw_point(*r, color="red")


if __name__ == "__main__":
    root = tk.Tk()
    TriGrowthApp(root)
    root.mainloop()
