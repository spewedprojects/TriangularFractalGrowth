# controllers.py

import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox

from canvas_manager import CanvasManager
import exporter

class TriGrowthController:
    """
    Sets up the entire GUI (scrollable canvas + control panel) and binds
    buttons/checkboxes/spinbox to the CanvasManager methods and exporter routines.
    """
    def __init__(self, root: tk.Tk):
        # ------------------------- Scrollable Canvas -------------------------
        canvas_frame = tk.Frame(root)
        canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(canvas_frame, width=1500, height=1500, bg='white')
        sb_v = tk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        sb_h = tk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.canvas.config(yscrollcommand=sb_v.set, xscrollcommand=sb_h.set)

        self.canvas.grid(row=0, column=0, sticky='nsew')
        sb_v.grid(row=0, column=1, sticky='ns')
        sb_h.grid(row=1, column=0, sticky='ew')
        canvas_frame.grid_rowconfigure(0, weight=1)
        canvas_frame.grid_columnconfigure(0, weight=1)

        # Prepare control‐panel variables BEFORE creating buttons
        # -------------------------------------------------------
        # Side selector (LEFT / RIGHT / BOTH)
        self.side_var = tk.StringVar(value='LEFT')

        # Visibility checkboxes
        self.v_dots = tk.IntVar(value=1)
        self.v_rows = tk.IntVar(value=1)
        self.v_tris = tk.IntVar(value=1)
        self.v_hull = tk.IntVar(value=1)

        # Line thickness spinbox
        self.line_thickness_var = tk.IntVar(value=1)

        # Now initialize CanvasManager (needs canvas & line_thickness_var)
        self.canvas_mgr = CanvasManager(self.canvas, self.line_thickness_var)

        # Expose visibility vars to canvas_mgr so it can read them
        self.canvas_mgr.v_dots = self.v_dots
        self.canvas_mgr.v_rows = self.v_rows
        self.canvas_mgr.v_tris = self.v_tris
        self.canvas_mgr.v_hull = self.v_hull

        # ------------------------- Control Panel -------------------------
        ctrl = tk.Frame(root)
        ctrl.pack(side=tk.RIGHT, fill=tk.Y)

        # Buttons (now that canvas_mgr exists)
        for txt, cmd in (('Add Layer',   lambda: self.canvas_mgr.add_layer(self.side_var)),
                        ('Undo Layer',  self.canvas_mgr_undo),
                        ('Redo Layer',  self.canvas_mgr_redo),
                        ('Run to End',  lambda: self.canvas_mgr.auto_run(self.side_var)),
                        ('Export',      self.export_dialog),
                        ('Clear',       self.canvas_mgr.clear)):
            btn = tk.Button(ctrl, text=txt, command=cmd)
            btn.pack(fill=tk.X, padx=6, pady=2)

        # Side selector (LEFT / RIGHT / BOTH)
        tk.Label(ctrl, text='Triangle Side', font=('Arial', 10, 'bold')).pack(pady=(10, 0))
        for s in ('LEFT', 'RIGHT', 'BOTH'):
            tk.Radiobutton(ctrl, text=s, variable=self.side_var, value=s).pack(anchor='w')

        # Visibility checkboxes
        tk.Label(ctrl, text='Visibility', font=('Arial', 10, 'bold')).pack(pady=(10, 0))
        for txt, var in (('Dots', self.v_dots),
                         ('Row Lines', self.v_rows),
                         ('Triangles', self.v_tris),
                         ('Outer Hull', self.v_hull)):
            cb = tk.Checkbutton(ctrl, text=txt, variable=var,
                                command=self.canvas_mgr_update_visibility)
            cb.pack(anchor='w')

        # Line thickness spinbox
        tk.Label(ctrl, text='Line Thickness', font=('Arial', 10, 'bold')).pack(pady=(10, 0))
        spin = tk.Spinbox(ctrl, from_=1, to=10, textvariable=self.line_thickness_var,
                          command=self.canvas_mgr_update_thickness, width=5)
        spin.pack(anchor='w', pady=(0, 10))

    # ------------------------------------------------ helper wrappers for CanvasManager
    def canvas_mgr_undo(self):
        self.canvas_mgr.undo_layer()

    def canvas_mgr_redo(self):
        self.canvas_mgr.redo_layer(self.side_var)

    def canvas_mgr_update_visibility(self):
        self.canvas_mgr.update_visibility()

    def canvas_mgr_update_thickness(self):
        self.canvas_mgr.update_thickness()

    # ------------------------------------------------ Export dialog (SVG/PNG/OBJ)
    def export_dialog(self):
        fmt = simpledialog.askstring('Export', 'Format (svg/png/obj):', initialvalue='svg')
        if not fmt:
            return
        fmt = fmt.lower()
        if fmt not in ('svg', 'png', 'obj'):
            messagebox.showerror('Export', 'Unsupported format')
            return

        ext = { 'svg':'.svg', 'png':'.png', 'obj':'.obj' }[fmt]
        path = filedialog.asksaveasfilename(defaultextension=ext)
        if not path:
            return

        if fmt == 'svg':
            exporter.export_svg(self.canvas, self.line_thickness_var, path)
        elif fmt == 'png':
            exporter.export_png(self.canvas, path)
        else:  # 'obj'
            exporter.export_obj(self.canvas_mgr.triangles_3d, path)
