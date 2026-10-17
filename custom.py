"""Custom gestures: store, recognise and run the action you attached.

A gesture is a handful of recorded hand shapes (size-normalised landmarks).
While you use the mouse, the live hand is compared to each recorded shape; if
it matches for custom_hold_s seconds, the action runs once.

Actions (stored in custom_gestures.json):
  {"type": "app",    "value": "notepad"}            app / file / folder
  {"type": "url",    "value": "https://..."}        website
  {"type": "hotkey", "value": "ctrl+shift+s"}       keyboard shortcut
"""
import json
import os
import subprocess
import sys
import webbrowser
from dataclasses import dataclass
from pathlib import Path

import numpy as np


def gestures_path(cfg) -> Path:
    return Path(__file__).resolve().parent / cfg.custom_file


def finger_code(fingers) -> int:
    """(index, middle, ring, pinky) up/down flags -> a 4-bit number."""
    return sum(1 << i for i, up in enumerate(fingers) if up)


def finger_codes_from(samples_fingers, min_share=0.10):
    """Finger patterns that appeared in at least min_share of the recorded samples."""
    counts = {}
    for f in samples_fingers:
        c = finger_code(f)
        counts[c] = counts.get(c, 0) + 1
    n = len(samples_fingers)
    return sorted(c for c, k in counts.items() if k / n >= min_share)


def _rms(samples, features):
    """Root-mean-square landmark distance of each sample to `features` (hand size = 1.0).
    RMS (not a plain mean) so that one finger in the wrong place is not averaged away."""
    d = np.linalg.norm(samples - features, axis=2)
    return np.sqrt((d ** 2).mean(axis=1))


@dataclass
class Gesture:
    name: str
    action: dict
    samples: np.ndarray                  # (N, 21, 2)
    threshold: float                     # RMS landmark distance below which it counts as a match
    fingers: tuple = ()                  # allowed finger patterns (empty = don't check)

    def distance(self, features) -> float:
        """Distance to the closest recorded sample."""
        return float(_rms(self.samples, features).min())

    def ratio(self, hand) -> float:
        """distance / threshold; below 1.0 = match. inf if the fingers up/down differ."""
        if self.fingers and finger_code(hand.fingers) not in self.fingers:
            return float("inf")
        return self.distance(hand.features) / self.threshold


def make_threshold(samples, cfg) -> float:
    """Pick a match threshold from how much the recorded samples vary."""
    spread = _rms(samples, samples.mean(axis=0))
    thr = float(np.percentile(spread, 95)) * cfg.custom_threshold_scale
    return float(min(cfg.custom_max_threshold, max(cfg.custom_min_threshold, thr)))


def load_gestures(path: Path):
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"Could not read {path.name}: {e}")
        return []
    out = []
    for item in data.get("gestures", []):
        try:
            out.append(Gesture(
                name=str(item["name"]),
                action=dict(item["action"]),
                samples=np.array(item["samples"], dtype=float).reshape(-1, 21, 2),
                threshold=float(item["threshold"]),
                fingers=tuple(int(c) for c in item.get("fingers", [])),
            ))
        except (KeyError, TypeError, ValueError):
            print(f"Skipping a broken gesture entry in {path.name}")
    return out


def save_gestures(path: Path, gestures):
    data = {"gestures": [{
        "name": g.name,
        "action": g.action,
        "threshold": round(g.threshold, 4),
        "fingers": list(g.fingers),
        "samples": np.round(g.samples, 4).tolist(),
    } for g in gestures]}
    path.write_text(json.dumps(data), encoding="utf-8")


def describe(action: dict) -> str:
    kind = {"app": "open", "url": "website", "hotkey": "keys"}.get(action.get("type"), "?")
    return f"{kind}: {action.get('value')}"


def perform(action: dict):
    """Run a gesture's action. Never raises: problems are printed."""
    kind, value = action.get("type"), str(action.get("value", ""))
    try:
        if kind == "hotkey":
            import pyautogui
            pyautogui.hotkey(*[k.strip() for k in value.lower().split("+") if k.strip()])
        elif kind == "url":
            webbrowser.open(value)
        elif kind == "app":
            if sys.platform == "win32":
                os.startfile(value)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", value])
            else:
                subprocess.Popen(["xdg-open", value])
        else:
            print(f"Unknown action type: {kind}")
    except Exception as e:                      # keep the mouse loop alive
        print(f"Could not run action {describe(action)}: {e}")


class CustomRecognizer:
    def __init__(self, cfg, gestures):
        self.cfg = cfg
        self.gestures = gestures
        self.best = None             # (name, distance / threshold) for the HUD
        self._cand = None
        self._since = 0.0
        self._armed = True           # must stop matching before the same gesture can fire again
        self._cool = 0.0

    def update(self, hand, now, allowed):
        """Return the Gesture to run this frame, or None."""
        self.best = None
        if not self.gestures or hand is None or not allowed:
            self._cand, self._armed = None, True
            return None

        best_g, best_r = None, float("inf")
        for g in self.gestures:
            r = g.ratio(hand)
            if r < best_r:
                best_g, best_r = g, r
        if best_g is None:                       # no gesture has these fingers up/down
            self._cand, self._armed = None, True
            return None
        self.best = (best_g.name, best_r)

        if best_r >= 1.0:
            self._cand, self._armed = None, True
            return None
        if self._cand != best_g.name:
            self._cand, self._since = best_g.name, now
            return None
        if self._armed and now - self._since >= self.cfg.custom_hold_s and now >= self._cool:
            self._armed = False
            self._cool = now + self.cfg.custom_cooldown_s
            return best_g
        return None
