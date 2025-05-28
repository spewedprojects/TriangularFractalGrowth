import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox
from math import cos, sin, radians
import colorsys, io
try:
    from PIL import Image
except ImportError:
    Image = None  # PNG export optional

# ------------------------------------------------------------
#  Triangular‑Growth Prototype  —  v0.9
#  • Outer Trace → single global convex‑hull silhouette
#      – checkbox renamed **Outer Hull** (keeps same position).
#      – hull recomputed after Add/Undo/Redo/Clear and when toggle flips.
#  • Row Lines, Triangles, Dots keep previous meanings.
#  • Everything else (drag seed, colours, export) unchanged.
# ------------------------------------------------------------

class TriGrowthApp:
    DOT_R = 3

    def __init__(self, m):
        self.root = m
        m.title("Triangular Growth Prototype")
        self.cv = tk.Canvas(m, width=1000, height=700, bg="white")
        self.cv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ctrl = tk.Frame(m); ctrl.pack(side=tk.RIGHT, fill=tk.Y)

        # --- command buttons
        for txt, cmd in (
            ("Add Layer",   self.add_layer),
            ("Undo Layer",  self.undo_layer),
            ("Redo Layer",  self.redo_layer),
            ("Run to End",  self.auto_run),
            ("Export",      self.export_dialog),
            ("Clear",       self.clear)):
            tk.Button(ctrl, text=txt, command=cmd).pack(padx=6, pady=2, fill=tk.X)

        # --- side selector
        self.side = tk.StringVar(value='LEFT')
        tk.Label(ctrl, text='Triangle Side', font=('Arial',10,'bold')).pack(pady=(10,0))
        for s in ('LEFT','RIGHT','BOTH'):
            tk.Radiobutton(ctrl, text=s, variable=self.side, value=s).pack(anchor='w')

        # --- visibility toggles
        tk.Label(ctrl, text='Visibility', font=('Arial',10,'bold')).pack(pady=(10,0))
        self.v_dots  = tk.IntVar(value=1)
        self.v_rows  = tk.IntVar(value=1)
        self.v_tris  = tk.IntVar(value=1)
        self.v_hull  = tk.IntVar(value=1)
        for txt, var in (("Dots",self.v_dots),("Row Lines",self.v_rows),
                         ("Triangles",self.v_tris),("Outer Hull",self.v_hull)):
            tk.Checkbutton(ctrl,text=txt,variable=var,command=self.update_visibility).pack(anchor='w')

        # --- state
        self.rows: list[list[tuple[float,float]]] = []
        self.layer_tags: list[str] = []
        self.redo = []  # stack of (row, tag)
        self.lock_seed = False
        self._left_branch = self._right_branch = None
        # drag helpers
        self._drag_i = None; self._drag_id = None

        # bindings
        self.cv.bind('<Button-1>', self.on_click)
        self.cv.bind('<B1-Motion>', self.on_drag)
        self.cv.bind('<ButtonRelease-1>', self.on_release)

    # ================================================= seed edit
    def on_click(self,e):
        if self.lock_seed: return
        if not self.rows: self.rows.append([])
        # hit‑test existing seed
        for i,(x,y) in enumerate(self.rows[0]):
            if (e.x-x)**2+(e.y-y)**2 <= (self.DOT_R*3)**2:
                self._drag_i=i; self._drag_id=self.cv.find_closest(x,y)[0]; return
        # else add
        self.rows[0].append((e.x,e.y))
        self._draw_point(e.x,e.y,'black','seed')
        if len(self.rows[0])>1:
            p,q=self.rows[0][-2],self.rows[0][-1]
            self.cv.create_line(p[0],p[1],q[0],q[1],tags=('seed','row'))
        self.update_hull()

    def on_drag(self,e):
        if self._drag_i is None: return
        self.rows[0][self._drag_i]=(e.x,e.y)
        self.cv.coords(self._drag_id,e.x-self.DOT_R,e.y-self.DOT_R,e.x+self.DOT_R,e.y+self.DOT_R)
        self.cv.delete('seed_line')
        for i in range(len(self.rows[0])-1):
            p,q=self.rows[0][i],self.rows[0][i+1]
            self.cv.create_line(p[0],p[1],q[0],q[1],tags=('seed_line','row'))
        self.update_hull()

    def on_release(self,_): self._drag_i=self._drag_id=None

    # ================================================= layer ops
    def add_layer(self):
        if not self.rows or len(self.rows[-1])<2: return
        self.lock_seed=True; self.redo.clear()
        idx=len(self.layer_tags); tag=f'ly{idx}'; col=self._col(idx)
        if self.side.get()=='BOTH':
            if self._left_branch is None:
                self._left_branch=self.rows[-1][:]; self._right_branch=self.rows[-1][:]
            nl=self._next(self._left_branch,+1,tag,col)
            nr=self._next(self._right_branch,-1,tag,col)
            self._left_branch,self._right_branch=nl,nr
            comp=nl+nr; # connect hull between branches
        else:
            sign= +1 if self.side.get()=='LEFT' else -1
            comp=self._next(self.rows[-1],sign,tag,col)
            self._left_branch=self._right_branch=None
        self.rows.append(comp); self.layer_tags.append(tag)
        self.update_hull(); self.update_visibility()

    def _next(self,row,sign,tag,col):
        ch=[]
        for i in range(len(row)-1):
            p,q=row[i],row[i+1]
            c=self._third(p,q,sign); ch.append(c)
            self._draw_tri(p,q,c,tag,col)
        # row outline
        for i in range(len(ch)-1):
            self.cv.create_line(ch[i][0],ch[i][1],ch[i+1][0],ch[i+1][1],tags=(tag,'row'))
        return ch

    def undo_layer(self):
        if len(self.rows)<=1: return
        row=self.rows.pop(); tag=self.layer_tags.pop()
        self.cv.itemconfigure(tag,state='hidden'); self.redo.append((row,tag))
        if len(self.rows)==1: self.lock_seed=False
        self.update_hull(); self.update_visibility()

    def redo_layer(self):
        if not self.redo: return
        row,tag=self.redo.pop(); self.cv.itemconfigure(tag,state='normal')
        self.rows.append(row); self.layer_tags.append(tag); self.lock_seed=True
        self.update_hull(); self.update_visibility()

    def auto_run(self):
        if self.side.get()=='BOTH': return
        while self.rows and len(self.rows[-1])>2: self.add_layer()

    def clear(self):
        self.cv.delete('all'); self.rows.clear(); self.layer_tags.clear(); self.redo.clear()
        self._left_branch=self._right_branch=None; self.lock_seed=False; self.update_hull()

    # ================================================= visibility
    def update_visibility(self):
        self.cv.itemconfigure('dot',state=('normal' if self.v_dots.get() else 'hidden'))
        self.cv.itemconfigure('row',state=('normal' if self.v_rows.get() else 'hidden'))
        self.cv.itemconfigure('tri',state=('normal' if self.v_tris.get() else 'hidden'))
        self.cv.itemconfigure('hull',state=('normal' if self.v_hull.get() else 'hidden'))

    # ================================================= hull
    def update_hull(self):
        self.cv.delete('hull')
        pts=[p for row in self.rows for p in row]
        if len(pts)<3: return
        hull=self._convex_hull(sorted(pts))
        for i in range(len(hull)):
            p,q=hull[i],hull[(i+1)%len(hull)]
            self.cv.create_line(p[0],p[1],q[0],q[1],tags=('hull',))
        self.update_visibility()

    @staticmethod
    def _cross(o,a,b): return (a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0])
    def _convex_hull(self,pts):
        if len(pts)<=1: return pts
        lower=[]
        for p in pts:
            while len(lower)>=2 and self._cross(lower[-2],lower[-1],p)<=0: lower.pop()
            lower.append(p)
        upper=[]
        for p in reversed(pts):
            while len(upper)>=2 and self._cross(upper[-2],upper[-1],p)<=0: upper.pop()
            upper.append(p)
        return lower[:-1]+upper[:-1]

    # ================================================= export (same as before, hull lines auto included)
    def export_dialog(self):
        fmt=simpledialog.askstring('Export','Format (svg/png):',initialvalue='svg');
        if not fmt: return
        fmt=fmt.lower()
        if fmt not in {'svg','png'}: messagebox.showerror('Export','Unsupported'); return
        file=filedialog.asksaveasfilename(defaultextension=f'.{fmt}')
        if not file: return
        if fmt=='svg': self._exp_svg(file)
        else: self._exp_png(file)

    def _exp_svg(self,path):
        try: import svgwrite
        except ImportError: messagebox.showerror('Export','svgwrite not installed'); return
        w,h=int(self.cv['width']),int(self.cv['height'])
        dwg=svgwrite.Drawing(path,size=(w,h))
        for item in self.cv.find_all():
            typ=self.cv.type(item); coords=self.cv.coords(item)
            if typ=='oval':
                x1,y1,x2,y2=coords; cx,cy=(x1+x2)/2,(y1+y2)/2; r=(x2-x1)/2
                dwg.add(dwg.circle(center=(cx,cy),r=r,fill=self.cv.itemcget(item,'fill')))
            elif typ=='line': dwg.add(dwg.line(start=(coords[0],coords[1]),end=(coords[2],coords[3]),stroke='#000'))
        dwg.save()

    def _exp_png(self,path):
        if Image is None: messagebox.showerror('Export','Pillow needed'); return
        scale=simpledialog.askinteger('PNG scale','Scale (1‑10)',initialvalue=1,minvalue=1,maxvalue=10)
        if not scale: return
        ps=self.cv.postscript(colormode='color')
        img=Image.open(io.BytesIO(ps.encode('utf-8')))
        w,h=img.size; img=img.resize((w*scale,h*scale),Image.ANTIALIAS); img.save(path)

    # ================================================= helper draw & geom
    def _col(self,i):
        h=(i*0.15)%1; r,g,b=colorsys.hsv_to_rgb(h,0.9,0.95); return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
    def _third(self,p,q,s):
        vx,vy=q[0]-p[0],q[1]-p[1]; a=radians(60)*s
        rx=vx*cos(a)-vy*sin(a); ry=vx*sin(a)+vy*cos(a)
        return p[0]+rx, p[1]+ry
    def _draw_point(self,x,y,col,tag):
        r=self.DOT_R; self.cv.create_oval(x-r,y-r,x+r,y+r,fill=col,outline='',tags=(tag,'dot'))
    def _draw_tri(self,p,q,r,tag,col):
        self.cv.create_line(p[0],p[1],q[0],q[1],tags=(tag,'row'))
        self.cv.create_line(q[0],q[1],r[0],r[1],tags=(tag,'tri'))
        self.cv.create_line(r[0],r[1],p[0],p[1],tags=(tag,'tri'))
        self._draw_point(*r,col,tag)

if __name__=='__main__':
    root=tk.Tk(); TriGrowthApp(root); root.mainloop()
