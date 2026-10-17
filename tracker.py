"""Palm-based hand tracking with MediaPipe.

The cursor anchor is the centre of the palm (wrist + 4 knuckles), NOT a
fingertip. Those points barely move when you pinch, so the cursor stays
steady during clicks and drag-and-drop.

Also reports which fingers are up (-> a named pose) and a size-normalised
landmark vector that custom gestures are matched against.
"""
from dataclasses import dataclass

import cv2
import mediapipe as mp
import numpy as np

PALM_IDS = (0, 5, 9, 13, 17)                 # wrist + index/middle/ring/pinky knuckles
FINGER_TIPS = (8, 12, 16, 20)                # index, middle, ring, pinky
FINGER_PIPS = (6, 10, 14, 18)

_POSES = {
    (False, False, False, False): "fist",
    (True, False, False, False): "one",      # index only
    (True, True, False, False): "two",       # index + middle
    (True, True, True, False): "three",      # index + middle + ring
    (True, True, True, True): "open",
}


def classify_pose(fingers) -> str:
    """fingers = (index, middle, ring, pinky) booleans -> pose name."""
    return _POSES.get(tuple(bool(f) for f in fingers), "other")


@dataclass
class HandData:
    landmarks: object          # raw MediaPipe landmarks (for drawing)
    palm_norm: tuple           # (x, y) palm centre, 0..1 in camera frame
    index_tip_norm: tuple      # (x, y) index fingertip, 0..1 in camera frame
    pinch_index: float         # thumb-index distance / hand size
    pinch_middle: float        # thumb-middle distance / hand size
    fingers: tuple             # (index, middle, ring, pinky) extended flags
    pose: str                  # fist / one / two / three / open / other
    is_fist: bool
    features: np.ndarray       # (21, 2) landmarks relative to wrist, / hand size


def _d(a, b) -> float:
    return float(np.linalg.norm(a - b))


def analyse(pts, ext_ratio):
    """Turn 21 landmark points (pixels, shape (21, 2)) into the numbers we need."""
    palm = pts[list(PALM_IDS)].mean(axis=0)
    size = max(_d(pts[0], pts[9]), 1e-6)     # wrist -> middle knuckle
    fingers = tuple(_d(pts[0], pts[t]) > _d(pts[0], pts[p]) * ext_ratio
                    for t, p in zip(FINGER_TIPS, FINGER_PIPS))
    pose = classify_pose(fingers)
    return {
        "palm": palm,
        "pinch_index": _d(pts[4], pts[8]) / size,
        "pinch_middle": _d(pts[4], pts[12]) / size,
        "fingers": fingers,
        "pose": pose,
        "features": (pts - pts[0]) / size,
    }


class HandTracker:
    def __init__(self, cfg):
        self.cfg = cfg
        self._hands = mp.solutions.hands.Hands(
            static_image_mode=False,
            max_num_hands=cfg.max_hands,
            model_complexity=cfg.model_complexity,
            min_detection_confidence=cfg.detection_conf,
            min_tracking_confidence=cfg.tracking_conf,
        )
        self._draw = mp.solutions.drawing_utils
        self._conn = mp.solutions.hands.HAND_CONNECTIONS

    def process(self, frame_bgr):
        """Return HandData for the first detected hand, or None."""
        h, w = frame_bgr.shape[:2]
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        result = self._hands.process(rgb)
        if not result.multi_hand_landmarks:
            return None

        lm = result.multi_hand_landmarks[0]
        pts = np.array([[p.x * w, p.y * h] for p in lm.landmark])
        a = analyse(pts, self.cfg.finger_ext_ratio)

        return HandData(
            landmarks=lm,
            palm_norm=(a["palm"][0] / w, a["palm"][1] / h),
            index_tip_norm=(pts[8][0] / w, pts[8][1] / h),
            pinch_index=a["pinch_index"],
            pinch_middle=a["pinch_middle"],
            fingers=a["fingers"],
            pose=a["pose"],
            is_fist=a["pose"] == "fist",
            features=a["features"],
        )

    def draw(self, frame, hand):
        self._draw.draw_landmarks(frame, hand.landmarks, self._conn)

    def close(self):
        self._hands.close()
