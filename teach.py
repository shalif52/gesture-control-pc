"""Teach the gesture mouse a new gesture and say what it should do.

  python teach.py                 record a new gesture
  python teach.py --list          show saved gestures
  python teach.py --delete NAME   remove one

Steps: type a name and an action, show the gesture to the camera, press SPACE
(3 second countdown, then it records for ~2.5 s while you hold the pose and
move your hand around a little), press S to save.
"""
import argparse
import time
from collections import Counter

import cv2
import numpy as np

from config import Config
from custom import (Gesture, describe, finger_codes_from, gestures_path, load_gestures,
                    make_threshold, save_gestures)
from main import FONT, open_camera, put_text
from tracker import HandTracker

COUNTDOWN_S, RECORD_S, SAMPLE_EVERY_S, MIN_SAMPLES = 3.0, 2.5, 0.08, 12


def ask_action():
    print("\nWhat should this gesture do?")
    print("  1) Open an app, file or folder   (notepad, calc, or a full path)")
    print("  2) Open a website                (youtube.com)")
    print("  3) Press a keyboard shortcut     (ctrl+shift+s, win+d, alt+tab)")
    choice = ""
    while choice not in ("1", "2", "3"):
        choice = input("Choose 1, 2 or 3: ").strip()

    if choice == "1":
        value = input("App, file or folder: ").strip().strip('"')
        return {"type": "app", "value": value} if value else None
    if choice == "2":
        value = input("Website: ").strip()
        if not value:
            return None
        if "://" not in value:
            value = "https://" + value
        return {"type": "url", "value": value}

    value = input("Keys joined with +  (e.g. ctrl+shift+s): ").strip().lower().replace(" ", "")
    keys = [k for k in value.split("+") if k]
    if not keys:
        return None
    try:
        import pyautogui
        bad = [k for k in keys if k not in pyautogui.KEYBOARD_KEYS]
    except Exception:
        bad = []
    if bad:
        print(f"Unknown key name(s): {', '.join(bad)}")
        return None
    return {"type": "hotkey", "value": "+".join(keys)}


def capture(cfg):
    """Show the camera and collect samples. Returns a list of (features, pose, pinch) or None."""
    cap = open_camera(cfg)
    tracker = HandTracker(cfg)
    samples, phase, t0, last = [], "ready", 0.0, 0.0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                return None
            if cfg.mirror:
                frame = cv2.flip(frame, 1)
            now = time.time()
            hand = tracker.process(frame)
            if hand is not None:
                tracker.draw(frame, hand)

            if phase == "countdown":
                left = COUNTDOWN_S - (now - t0)
                if left <= 0:
                    phase, t0, samples = "recording", now, []
                msg, color = f"Get ready... {int(max(left, 0)) + 1}", (0, 255, 255)
            elif phase == "recording":
                if hand is not None and now - last >= SAMPLE_EVERY_S:
                    samples.append((hand.features.copy(), hand.pose,
                                    min(hand.pinch_index, hand.pinch_middle), hand.fingers))
                    last = now
                if now - t0 >= RECORD_S:
                    phase = "review"
                msg, color = f"RECORDING - hold the pose ({len(samples)} samples)", (0, 0, 255)
            elif phase == "review":
                if len(samples) >= MIN_SAMPLES:
                    msg, color = f"{len(samples)} samples. S = save, R = retry, Q = cancel", (0, 255, 0)
                else:
                    msg, color = f"Only {len(samples)} samples (hand not visible?). R = retry", (0, 0, 255)
            else:
                msg, color = "Show the gesture, then press SPACE", (0, 255, 0)

            put_text(frame, msg, 28, color, 0.6)
            put_text(frame, "Q = cancel", frame.shape[0] - 12, (200, 200, 200), 0.5)
            cv2.imshow("Teach gesture", frame)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                return None
            if key == ord(" ") and phase == "ready":
                phase, t0 = "countdown", now
            elif key == ord("r") and phase == "review":
                phase = "ready"
            elif key == ord("s") and phase == "review" and len(samples) >= MIN_SAMPLES:
                return samples
    finally:
        cap.release()
        tracker.close()
        cv2.destroyAllWindows()


def check_conflicts(name, samples, feats, existing, cfg):
    warnings = []
    top = Counter(s[1] for s in samples).most_common(1)[0][0]
    if top in ("open", "two", "three"):
        warnings.append(f"This hand shape counts as '{top}', which already moves the cursor, "
                        "scrolls or changes volume. Pick another shape (thumbs up, rock sign, "
                        "shaka, a fist variant).")
    if np.mean([s[2] < cfg.pinch_on for s in samples]) > 0.3:
        warnings.append("Your thumb touches a finger, which also clicks the mouse. "
                        "Use a shape where the thumb stays away from the fingertips.")
    mean = feats.mean(axis=0)
    codes = finger_codes_from([s[3] for s in samples])
    for g in existing:
        if g.name == name:
            continue
        shares_fingers = not g.fingers or any(c in g.fingers for c in codes)
        if shares_fingers and g.distance(mean) / g.threshold < 1.0:
            warnings.append(f"It looks very similar to your gesture '{g.name}'.")
    return warnings


def list_gestures(cfg):
    gestures = load_gestures(gestures_path(cfg))
    if not gestures:
        print("No custom gestures saved yet.")
    for g in gestures:
        print(f"  {g.name:<20} {describe(g.action)}   ({len(g.samples)} samples)")


def delete_gesture(cfg, name):
    path = gestures_path(cfg)
    gestures = load_gestures(path)
    kept = [g for g in gestures if g.name != name]
    if len(kept) == len(gestures):
        print(f"No gesture named '{name}'.")
        return
    save_gestures(path, kept)
    print(f"Deleted '{name}'.")


def teach(cfg):
    path = gestures_path(cfg)
    existing = load_gestures(path)

    name = input("Name for this gesture (e.g. thumbs_up): ").strip().replace(" ", "_")
    if not name:
        print("Cancelled.")
        return
    if any(g.name == name for g in existing):
        print(f"'{name}' already exists and will be replaced.")
    action = ask_action()
    if action is None:
        print("Cancelled.")
        return

    print("\nA camera window will open. Show the gesture and press SPACE.")
    samples = capture(cfg)
    if samples is None:
        print("Cancelled, nothing saved.")
        return

    feats = np.array([s[0] for s in samples])
    for w in check_conflicts(name, samples, feats, existing, cfg):
        print("Warning:", w)
        if input("Save anyway? [y/N] ").strip().lower() != "y":
            print("Not saved.")
            return

    codes = finger_codes_from([s[3] for s in samples])
    gesture = Gesture(name, action, feats, make_threshold(feats, cfg), tuple(codes))
    save_gestures(path, [g for g in existing if g.name != name] + [gesture])
    print(f"\nSaved '{name}' -> {describe(action)}")
    print("Run  python main.py  and hold the gesture for about a second to trigger it.")


def main():
    parser = argparse.ArgumentParser(description="Teach custom hand gestures.")
    parser.add_argument("--list", action="store_true", help="show saved gestures")
    parser.add_argument("--delete", metavar="NAME", help="delete a saved gesture")
    args = parser.parse_args()
    cfg = Config()
    if args.list:
        list_gestures(cfg)
    elif args.delete:
        delete_gesture(cfg, args.delete)
    else:
        teach(cfg)


if __name__ == "__main__":
    main()
