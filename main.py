"""Hand-gesture PC control. Run:  python main.py

Keys (click the preview window first):
  c        switch Mouse <-> Air Canvas      p   control on/off
  + / -    cursor sensitivity               z   show/hide zone box
  s        save drawing (canvas mode)       x   clear drawing (canvas mode)
  q / Esc  quit
"""
import sys
import time

import cv2

from canvas import AirCanvas
from config import Config
from controller import MouseController
from custom import CustomRecognizer, describe, gestures_path, load_gestures, perform
from gestures import MOVE, PAUSED, GestureEngine
from mapping import ScreenMapper
from smoothing import PointFilter
from tracker import HandTracker

FONT = cv2.FONT_HERSHEY_SIMPLEX


def _enable_dpi_awareness():
    """On Windows with display scaling, make screen size match real pixels."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass


def open_camera(cfg):
    backend = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY
    cap = cv2.VideoCapture(cfg.camera_index, backend)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, cfg.frame_width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg.frame_height)
    if not cap.isOpened():
        sys.exit("Could not open webcam. Try camera_index = 1 in config.py.")
    return cap


def put_text(img, text, y, color=(0, 255, 0), scale=0.55):
    """Text on a dark box so it stays readable on any camera background."""
    (tw, th), base = cv2.getTextSize(text, FONT, scale, 1)
    cv2.rectangle(img, (5, y - th - 5), (15 + tw, y + base + 3), (0, 0, 0), -1)
    cv2.putText(img, text, (10, y), FONT, scale, color, 1, cv2.LINE_AA)


def main():
    _enable_dpi_awareness()
    cfg = Config()
    mouse = MouseController()
    mapper = ScreenMapper(*mouse.size, cfg)
    tracker = HandTracker(cfg)
    engine = GestureEngine(cfg)
    smooth = PointFilter(cfg)
    canvas = AirCanvas(cfg)
    gestures = load_gestures(gestures_path(cfg))
    recognizer = CustomRecognizer(cfg, gestures)
    cap = open_camera(cfg)

    if gestures:
        print("Custom gestures loaded:")
        for g in gestures:
            print(f"  {g.name}  ->  {describe(g.action)}")
    else:
        print("No custom gestures yet. Teach one with:  python teach.py")

    mode, enabled, show_zone = "mouse", True, cfg.show_zone
    toast_text, toast_until = "", 0.0
    prev = time.time()
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if cfg.mirror:
                frame = cv2.flip(frame, 1)

            now = time.time()
            hand = tracker.process(frame)
            if hand is not None:
                tracker.draw(frame, hand)

            if mode == "mouse":
                out = engine.update(hand, now)
                status = out.state if enabled else "DISABLED"

                if hand is not None:
                    sx, sy = mapper.to_screen(*hand.palm_norm)
                    fx, fy = smooth(sx, sy, now)         # always update filter
                    if enabled:
                        if out.move:
                            mouse.move(fx, fy)
                        for e in out.events:
                            mouse.handle(e)
                        if out.scroll:
                            mouse.scroll(out.scroll)
                elif enabled:
                    for e in out.events:
                        mouse.handle(e)

                g = recognizer.update(hand, now, enabled and out.state in (MOVE, PAUSED))
                if g is not None:
                    perform(g.action)
                    toast_text, toast_until = f"Gesture: {g.name}", now + 2.0
            else:
                canvas.update(hand, now, frame.shape)
                canvas.render(frame, now)
                status = canvas.status()

            if cfg.show_window:
                h, w = frame.shape[:2]
                if mode == "mouse":
                    if show_zone:
                        x0, y0, x1, y1 = mapper.zone()
                        cv2.rectangle(frame, (int(x0 * w), int(y0 * h)),
                                      (int(x1 * w), int(y1 * h)), (0, 255, 255), 1)
                    fps = 1.0 / max(now - prev, 1e-6)
                    put_text(frame, f"MOUSE | {status} | sens {mapper.sensitivity:.1f} | {fps:.0f} fps", 25)
                    put_text(frame, "2 fingers=scroll  3 fingers=volume  c=canvas", h - 12,
                             (200, 200, 200), 0.5)
                    if recognizer.best and recognizer.best[1] < 2.0:
                        put_text(frame, f"custom: {recognizer.best[0]} ({recognizer.best[1]:.2f})",
                                 50, (255, 200, 0), 0.5)
                else:
                    put_text(frame, f"CANVAS | {status}", h - 36)
                    put_text(frame, "1 finger=draw  2 fingers=pen up/pick tool  s=save  x=clear  c=mouse",
                             h - 12, (200, 200, 200), 0.45)
                if now < toast_until:
                    put_text(frame, toast_text, 75, (0, 255, 255), 0.7)
                cv2.imshow("Gesture Control", frame)

                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    break
                elif key == ord("c"):
                    mouse.release()
                    engine.reset()
                    canvas.reset()
                    smooth.reset()
                    mode = "canvas" if mode == "mouse" else "mouse"
                elif key in (ord("+"), ord("=")):
                    mapper.adjust(+cfg.sens_step)
                elif key in (ord("-"), ord("_")):
                    mapper.adjust(-cfg.sens_step)
                elif key == ord("p"):
                    enabled = not enabled
                    mouse.release()
                elif key == ord("z"):
                    show_zone = not show_zone
                elif key == ord("s") and mode == "canvas":
                    canvas.save(now)
                elif key == ord("x") and mode == "canvas":
                    canvas.clear()
            prev = now
    finally:
        mouse.release()
        cap.release()
        tracker.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
