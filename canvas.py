"""Air Canvas: draw in the air with your index finger.

  1 finger up (index) ...... draw
  2 fingers up ............. pen up; hover a toolbar button to pick it
  anything else ............ pen up

Toolbar (top of the preview): colours, Eraser, Clear, Save.
Hover time is needed to press a button; Clear and Save need a longer hover
so you can't hit them by accident.
"""
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from gestures import PoseStabilizer
from smoothing import PointFilter

FONT = cv2.FONT_HERSHEY_SIMPLEX

# (label, kind, BGR colour)
BUTTONS = [
    ("Red", "color", (0, 0, 255)),
    ("Green", "color", (0, 200, 0)),
    ("Blue", "color", (255, 80, 0)),
    ("Yellow", "color", (0, 220, 255)),
    ("Black", "color", (0, 0, 0)),
    ("Eraser", "eraser", (90, 90, 90)),
    ("Clear", "clear", (60, 60, 140)),
    ("Save", "save", (60, 120, 60)),
]


class AirCanvas:
    def __init__(self, cfg):
        self.cfg = cfg
        self._pose = PoseStabilizer(cfg.pen_hold_s)
        self._pen = PointFilter(cfg, min_cutoff=cfg.canvas_min_cutoff,
                                beta=cfg.canvas_beta, deadzone=0.0)
        self.save_dir = Path(__file__).resolve().parent / cfg.drawings_dir
        self.layer = None            # BGR colours of the strokes
        self.mask = None             # 255 where a stroke exists
        self.color_idx = 0
        self.eraser = False
        self.tip = None              # current (smoothed) fingertip, pixels
        self.pose = "none"
        self.drawing = False
        self._last = None
        self._hover = None
        self._since = 0.0
        self._fired = False
        self._toast = ""
        self._toast_until = 0.0

    # ----- state -----
    def reset(self):
        """Called when the mode is entered or the hand is lost. Keeps the drawing."""
        self._pose.reset()
        self._last = None
        self._hover = None
        self.tip = None
        self.drawing = False
        self.pose = "none"

    def _ensure(self, h, w):
        if self.layer is None or self.layer.shape[:2] != (h, w):
            self.layer = np.zeros((h, w, 3), np.uint8)
            self.mask = np.zeros((h, w), np.uint8)

    def clear(self):
        if self.layer is not None:
            self.layer[:] = 0
            self.mask[:] = 0

    def save(self, now=0.0):
        """Write the drawing (on a white background) to drawings/*.png. Returns the path."""
        if self.layer is None or not self.mask.any():
            self._say("Nothing to save yet", now)
            return None
        img = np.full_like(self.layer, 255)
        img[self.mask > 0] = self.layer[self.mask > 0]
        self.save_dir.mkdir(parents=True, exist_ok=True)
        path = self.save_dir / datetime.now().strftime("air_canvas_%Y%m%d_%H%M%S.png")
        ok, buf = cv2.imencode(".png", img)
        if not ok:
            self._say("Save failed", now)
            return None
        path.write_bytes(buf.tobytes())
        self._say(f"Saved: {path.name}", now)
        print(f"Saved drawing: {path}")
        return path

    def _say(self, text, now, secs=2.5):
        self._toast, self._toast_until = text, now + secs

    # ----- per frame -----
    def update(self, hand, now, shape):
        h, w = shape[:2]
        self._ensure(h, w)
        if hand is None:
            self.reset()
            return

        self.pose = self._pose.update(hand.pose, now)
        m = self.cfg.canvas_margin
        span = 1.0 - 2 * m
        nx = min(1.0, max(0.0, (hand.index_tip_norm[0] - m) / span))
        ny = min(1.0, max(0.0, (hand.index_tip_norm[1] - m) / span))
        x, y = self._pen(nx * (w - 1), ny * (h - 1), now)
        self.tip = (int(x), int(y))

        on_toolbar = self.tip[1] < self.cfg.toolbar_height
        if self.pose == "one" and not on_toolbar:
            self._hover = None
            self._stroke(self.tip)
            self.drawing = True
        else:
            self._last = None
            self.drawing = False
            if self.pose == "two":
                self._hover_button(self.tip, w, now)
            else:
                self._hover = None

    def _stroke(self, pt):
        c = self.cfg
        p0 = self._last or pt
        if self.eraser:
            cv2.line(self.mask, p0, pt, 0, c.eraser_size)
        else:
            color = BUTTONS[self.color_idx][2]
            cv2.line(self.layer, p0, pt, color, c.brush_size)
            cv2.line(self.mask, p0, pt, 255, c.brush_size)
        self._last = pt

    def _button_at(self, pt, w):
        if pt[1] >= self.cfg.toolbar_height:
            return None
        return min(int(pt[0] / (w / len(BUTTONS))), len(BUTTONS) - 1)

    def _dwell(self, idx):
        kind = BUTTONS[idx][1]
        return self.cfg.dwell_long_s if kind in ("clear", "save") else self.cfg.dwell_s

    def _hover_button(self, pt, w, now):
        idx = self._button_at(pt, w)
        if idx != self._hover:
            self._hover, self._since, self._fired = idx, now, False
            return
        if idx is None or self._fired or now - self._since < self._dwell(idx):
            return
        self._fired = True
        kind = BUTTONS[idx][1]
        if kind == "color":
            self.color_idx, self.eraser = idx, False
        elif kind == "eraser":
            self.eraser = True
        elif kind == "clear":
            self.clear()
            self._say("Cleared", now)
        elif kind == "save":
            self.save(now)

    # ----- drawing the overlay -----
    def render(self, frame, now):
        """Draw strokes, toolbar and pen cursor onto the camera frame (in place)."""
        h, w = frame.shape[:2]
        self._ensure(h, w)
        sel = self.layer[self.mask > 0]
        frame[self.mask > 0] = sel

        bw = w / len(BUTTONS)
        th = self.cfg.toolbar_height
        for i, (label, kind, color) in enumerate(BUTTONS):
            x0, x1 = int(i * bw), int((i + 1) * bw)
            cv2.rectangle(frame, (x0, 0), (x1, th), color, -1)
            selected = (kind == "eraser" and self.eraser) or \
                       (kind == "color" and not self.eraser and i == self.color_idx)
            border = (255, 255, 255) if selected else (30, 30, 30)
            cv2.rectangle(frame, (x0, 0), (x1, th), border, 3 if selected else 1)
            dark_text = sum(color) > 350
            cv2.putText(frame, label, (x0 + 6, 28), FONT, 0.5,
                        (0, 0, 0) if dark_text else (255, 255, 255), 1, cv2.LINE_AA)
            if i == self._hover and not self._fired:
                frac = min(1.0, (now - self._since) / self._dwell(i))
                cv2.rectangle(frame, (x0, th - 8), (x0 + int((x1 - x0) * frac), th),
                              (0, 255, 0), -1)

        if self.tip is not None:
            if self.pose == "one" and self.tip[1] >= th:
                if self.eraser:
                    cv2.circle(frame, self.tip, self.cfg.eraser_size // 2, (255, 255, 255), 2)
                else:
                    color = BUTTONS[self.color_idx][2]
                    cv2.circle(frame, self.tip, max(self.cfg.brush_size, 4), color, -1)
                    cv2.circle(frame, self.tip, max(self.cfg.brush_size, 4), (255, 255, 255), 1)
            else:
                cv2.circle(frame, self.tip, 12, (255, 255, 255), 2)

        if now < self._toast_until:
            cv2.putText(frame, self._toast, (10, h - 12), FONT, 0.7, (0, 255, 255), 2, cv2.LINE_AA)

    def status(self):
        if self.tip is None:
            return "NO HAND"
        if self.drawing:
            return "ERASING" if self.eraser else "DRAWING"
        if self.pose == "two":
            return "PEN UP (pick a tool)"
        return "PEN UP"
