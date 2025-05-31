# --- DPI awareness (Windows only) ------------------------------------------
import sys
if sys.platform.startswith('win'):
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)   # PER_MONITOR_AWARE
    except Exception:
        pass  # not fatal – just means Windows will do its own coarse scaling
# ----------------------------------------------------------------------------

import tkinter as tk
from controllers import TriGrowthController

root = tk.Tk()
# --- Tk scaling -------------------------------------------------------------
# How many screen pixels in a typographic point?
# Tk reports it via winfo_fpixels('1i') – 1 inch in pixels.
dpi  = root.winfo_fpixels('1i')
scale = dpi / 64          # 72 points per inch
root.tk.call('tk', 'scaling', scale)
# ----------------------------------------------------------------------------
root.title('Triangular Growth Prototype (modular)')
TriGrowthController(root)
root.mainloop()
