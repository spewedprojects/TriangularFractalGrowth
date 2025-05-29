from collections import deque

class LayerState:
    def __init__(self):
        self.rows = []  # list[list[(x,y)]]
        self.tags = []  # active layer tags
        self.redo = deque()  # stack of (row, tag)
        self.undone = set()  # ← NEW: tags currently hidden
        self.left_branch = None
        self.right_branch = None
        self.seed_locked = False

    # ---------- helpers ----------
    def push(self, row, tag):
        self.rows.append(row)
        self.tags.append(tag)
        self.redo.clear()       # new branch kills redo

    def pop(self):
        if len(self.rows) <= 1:
            return None
        row = self.rows.pop()
        tag = self.tags.pop()
        self.redo.append((row, tag))
        if len(self.rows) == 1:
            self.seed_locked = False
        return tag

    def redo_layer(self):
        if not self.redo:
            return None
        row, tag = self.redo.pop()
        self.rows.append(row)
        self.tags.append(tag)
        self.seed_locked = True
        return tag
