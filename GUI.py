import tkinter as tk
from math import cos, sin, radians, sqrt


class TriGrowthApp:
    """Interactive prototype for the equilateral‑triangle growth idea.

    Click on the white canvas to drop the *seed* dots (first row).
    When you have at least two dots, press **Add Layer** to create the next
    generation.  Press **Run to End** to iterate automatically until only one
    or two dots remain.  **Clear** wipes the canvas so you can start a fresh
    sketch.  Use the *Triangle Side* radio buttons to choose which side of the
    seed‑segment the new vertex is built on (LEFT / RIGHT / ALTERNATE)."""

    def __init__(self, master):
        self.master = master
        self.master.title("Triangular Growth Prototype")

        # ---------- UI layout ----------
        self.canvas = tk.Canvas(master, width=800, height=600, bg="white")
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        ctrl = tk.Frame(master)
        ctrl.pack(side=tk.RIGHT, fill=tk.Y)

        self.add_layer_btn = tk.Button(ctrl, text="Add Layer", command=self.add_layer)
        self.add_layer_btn.pack(padx=5, pady=5, fill=tk.X)

        self.auto_btn = tk.Button(ctrl, text="Run to End", command=self.auto_run)
        self.auto_btn.pack(padx=5, pady=5, fill=tk.X)

        self.clear_btn = tk.Button(ctrl, text="Clear", command=self.clear)
        self.clear_btn.pack(padx=5, pady=5, fill=tk.X)

        self.side_choice = tk.StringVar(value="LEFT")
        tk.Label(ctrl, text="Triangle Side").pack()
        for side in ("LEFT", "RIGHT", "ALTERNATE"):
            tk.Radiobutton(ctrl, text=side, variable=self.side_choice, value=side).pack(anchor='w')

        # ---------- internal state ----------
        # rows[0]  = seed dots, rows[1] = first generation, ...
        self.rows: list[list[tuple[float, float]]] = []
        self.lock_seed = False  # once you make a layer, no new seed dots allowed

        # bind mouse click for adding seed points
        self.canvas.bind("<Button-1>", self.add_seed_point)

    # ---------- event handlers ----------

    def add_seed_point(self, event):
        """Add a dot to the seed row by clicking on the canvas."""
        if self.lock_seed:
            return  # seed row is fixed after first layer is built
        if not self.rows:
            self.rows.append([])
        self.rows[0].append((event.x, event.y))
        self._draw_point(event.x, event.y, color="black")

    def add_layer(self):
        """Generate the next row of dots using the equilateral rule."""
        if not self.rows or len(self.rows[-1]) < 2:
            return  # nothing to do
        self.lock_seed = True
        current = self.rows[-1]

        side_mode = self.side_choice.get()
        next_row: list[tuple[float, float]] = []

        for i in range(len(current) - 1):
            p = current[i]
            q = current[i + 1]

            if side_mode == "LEFT":
                side = 1
            elif side_mode == "RIGHT":
                side = -1
            else:  # ALTERNATE
                side = 1 if i % 2 == 0 else -1

            r = self._third_vertex(p, q, side)
            next_row.append(r)
            self._draw_triangle(p, q, r)

        self.rows.append(next_row)

    def auto_run(self):
        """Keep adding layers until only 1‑2 points remain."""
        while self.rows and len(self.rows[-1]) > 2:
            self.add_layer()

    def clear(self):
        """Reset everything to start anew."""
        self.canvas.delete("all")
        self.rows.clear()
        self.lock_seed = False

    # ---------- geometry helpers ----------

    @staticmethod
    def _third_vertex(p: tuple[float, float], q: tuple[float, float], sign: int = 1):
        """Return coordinates of the third vertex of an equilateral triangle.

        Args:
            p, q : endpoints of the base segment.
            sign : +1 ⇒ rotate 60° CCW, ‑1 ⇒ 60° CW.
        """
        vx = q[0] - p[0]
        vy = q[1] - p[1]
        angle = radians(60) * sign

        rx = vx * cos(angle) - vy * sin(angle)
        ry = vx * sin(angle) + vy * cos(angle)

        # height of equilateral triangle is |v| / sqrt(3)
        rx /= sqrt(3)
        ry /= sqrt(3)
        return (p[0] + rx, p[1] + ry)

    # ---------- drawing helpers ----------

    def _draw_point(self, x: float, y: float, color: str = "red", radius: int = 3):
        self.canvas.create_oval(x - radius, y - radius, x + radius, y + radius, fill=color, outline="")

    def _draw_triangle(self, p, q, r):
        self.canvas.create_line(p[0], p[1], q[0], q[1])
        self.canvas.create_line(q[0], q[1], r[0], r[1])
        self.canvas.create_line(r[0], r[1], p[0], p[1])
        self._draw_point(r[0], r[1], color="red")


if __name__ == "__main__":
    root = tk.Tk()
    app = TriGrowthApp(root)
    root.mainloop()
