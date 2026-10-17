"""All tunable settings live here. Edit values, no other file needs changing."""
from dataclasses import dataclass


@dataclass
class Config:
    # --- Camera ---
    camera_index: int = 0
    frame_width: int = 640
    frame_height: int = 480
    mirror: bool = True              # mirror preview so moving right = cursor right

    # --- MediaPipe ---
    max_hands: int = 1
    detection_conf: float = 0.7
    tracking_conf: float = 0.6
    model_complexity: int = 0        # 0 = fastest, 1 = more accurate

    # --- Cursor mapping ---
    # sensitivity 1.0 = whole camera frame maps to the screen.
    # Higher = smaller hand movement needed (active zone shrinks) and
    # the screen edges/corners are reached before your hand leaves the frame.
    sensitivity: float = 1.6
    sens_min: float = 1.0
    sens_max: float = 3.5
    sens_step: float = 0.1
    zone_center_x: float = 0.5       # centre of active zone in camera frame (0..1)
    zone_center_y: float = 0.45

    # --- Smoothing (One Euro filter, applied in screen pixels) ---
    min_cutoff: float = 1.2          # lower = smoother when slow/still (less jitter)
    beta: float = 0.015              # higher = less lag when moving fast
    d_cutoff: float = 1.0
    deadzone_px: float = 2.0         # ignore moves smaller than this

    # --- Gestures (ratios are fingertip distance / hand size) ---
    pinch_on: float = 0.28           # below this = pinch started
    pinch_off: float = 0.42          # above this = pinch released (hysteresis)
    drag_hold_s: float = 0.30        # pinch held this long = drag instead of click
    right_click_max_s: float = 0.60  # thumb+middle tap shorter than this = right click
    fist_pauses: bool = True         # closed fist freezes the cursor

    # --- Finger poses (used by scroll / volume / canvas) ---
    finger_ext_ratio: float = 1.10   # finger counts as "up" if tip is this much farther
                                     # from the wrist than its middle joint
    pose_hold_s: float = 0.25        # pose must be held this long before scroll/volume starts

    # --- Scroll (index + middle up) ---
    scroll_gain: float = 4000.0      # scroll units per full camera-height of hand movement
    scroll_deadzone: float = 0.002   # ignore hand movement smaller than this per frame
    scroll_invert: bool = False      # True = moving hand up scrolls down

    # --- Volume (index + middle + ring up) ---
    volume_step_norm: float = 0.03   # hand movement (fraction of frame height) per volume step

    # --- Air Canvas ---
    canvas_min_cutoff: float = 1.5   # pen smoothing (lower = smoother lines)
    canvas_beta: float = 0.03
    pen_hold_s: float = 0.08         # pose debounce so strokes don't break on a flicker
    brush_size: int = 6
    eraser_size: int = 40
    toolbar_height: int = 60
    dwell_s: float = 0.40            # hover time to pick a colour / eraser
    dwell_long_s: float = 0.90       # hover time for Clear / Save (avoids accidents)
    canvas_margin: float = 0.08      # fingertip range trimmed at the frame edges
    drawings_dir: str = "drawings"

    # --- Custom gestures ---
    custom_file: str = "custom_gestures.json"
    custom_hold_s: float = 0.80      # hold the gesture this long to trigger it
    custom_cooldown_s: float = 1.50
    custom_threshold_scale: float = 2.0   # higher = more forgiving matching
    custom_min_threshold: float = 0.07    # RMS landmark distance (hand size = 1.0)
    custom_max_threshold: float = 0.18

    # --- Display ---
    show_window: bool = True
    show_zone: bool = True           # draw active zone box in preview
