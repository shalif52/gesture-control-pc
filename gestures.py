"""Gesture state machine. Turns hand data into cursor/click/drag/scroll/volume events.

Gestures
  Open hand ............ move cursor (palm-anchored)
  Thumb + index pinch .. quick tap = left click (double tap = double click)
                         hold > drag_hold_s = press & hold (drag and drop),
                         release the pinch to drop
  Thumb + middle tap ... right click
  Index + middle up .... SCROLL  (move hand up / down)
  Index+middle+ring up . VOLUME  (move hand up = louder, down = quieter)
  Closed fist .......... pause (cursor frozen, any drag is released)

While a pinch is pending the cursor is FROZEN, so clicks land exactly where
you aimed even if your fingers wobble. During scroll / volume the cursor is
frozen too, so the scroll lands on the window you were pointing at.
"""
from dataclasses import dataclass, field

IDLE, MOVE, PINCH, DRAG, RIGHT, PAUSED, SCROLL, VOLUME = (
    "NO HAND", "MOVE", "PINCH", "DRAG", "RIGHT-CLICK", "PAUSED", "SCROLL", "VOLUME")


@dataclass
class Output:
    state: str
    move: bool = False                          # should the cursor follow the hand?
    events: list = field(default_factory=list)  # left_click, right_click, drag_start,
                                                # drag_end, volume_up, volume_down
    scroll: int = 0                             # scroll units this frame (+ = up, 120 = 1 notch)


class PoseStabilizer:
    """Reports a pose only after it has been held for hold_s (removes flicker)."""

    def __init__(self, hold_s):
        self.hold_s = hold_s
        self.reset()

    def reset(self):
        self.stable = "none"
        self._cand = "none"
        self._since = 0.0

    def update(self, pose, now):
        if pose != self._cand:
            self._cand, self._since = pose, now
        if pose != self.stable and now - self._since >= self.hold_s:
            self.stable = pose
        return self.stable


class GestureEngine:
    EXIT_FRAMES = 3          # frames of a different pose before scroll / volume ends

    def __init__(self, cfg):
        self.cfg = cfg
        self._pose = PoseStabilizer(cfg.pose_hold_s)
        self.reset()

    def reset(self):
        """Forget everything (used when switching modes). Does not emit events."""
        self.state = IDLE
        self._pinch_i = False
        self._pinch_m = False
        self._t0 = 0.0
        self._pose.reset()
        self._start_motion(None)

    def _start_motion(self, hand):
        self._prev_y = hand.palm_norm[1] if hand is not None else 0.0
        self._off = 0
        self._dy = 0.0
        self._scroll_acc = 0.0
        self._vol_acc = 0.0

    def _hyst(self, was_on, value):
        c = self.cfg
        if was_on:
            return value < c.pinch_off
        return value < c.pinch_on

    def _release_all(self, events):
        if self.state == DRAG:
            events.append("drag_end")
        self._pinch_i = self._pinch_m = False

    def _motion(self, hand, events):
        """Hand height change this frame -> scroll units / volume steps."""
        c = self.cfg
        y = hand.palm_norm[1]
        raw = y - self._prev_y                      # + = hand moved down
        self._prev_y = y
        self._dy = 0.5 * self._dy + 0.5 * raw       # light smoothing
        up = -self._dy if not c.scroll_invert else self._dy   # + = hand moved up
        if abs(self._dy) < c.scroll_deadzone:
            return 0

        if self.state == SCROLL:
            self._scroll_acc += up * c.scroll_gain
            n = int(self._scroll_acc)
            self._scroll_acc -= n
            return n

        # VOLUME: one key press per volume_step_norm of vertical hand movement
        self._vol_acc += -self._dy
        step = c.volume_step_norm
        while self._vol_acc >= step:
            events.append("volume_up")
            self._vol_acc -= step
        while self._vol_acc <= -step:
            events.append("volume_down")
            self._vol_acc += step
        return 0

    def update(self, hand, now) -> Output:
        c, ev = self.cfg, []

        if hand is None:
            self._release_all(ev)
            self.state = IDLE
            self._pose.reset()
            return Output(IDLE, False, ev)

        stable = self._pose.update(hand.pose, now)

        if c.fist_pauses and hand.is_fist:
            self._release_all(ev)
            self.state = PAUSED
            return Output(PAUSED, False, ev)

        if self.state in (IDLE, PAUSED):
            self.state = MOVE

        pi = self._hyst(self._pinch_i, hand.pinch_index)
        pm = self._hyst(self._pinch_m, hand.pinch_middle) and not pi
        scroll = 0

        if self.state == MOVE:
            if not pi and not pm and stable in ("two", "three") and hand.pose == stable:
                self.state = SCROLL if stable == "two" else VOLUME
                self._start_motion(hand)
                pi = pm = False
            elif pi:
                self.state, self._t0 = PINCH, now
            elif pm:
                self.state, self._t0 = RIGHT, now

        elif self.state == PINCH:
            if not pi:                                   # quick tap -> click
                ev.append("left_click")
                self.state = MOVE
            elif now - self._t0 >= c.drag_hold_s:        # held -> drag
                ev.append("drag_start")
                self.state = DRAG

        elif self.state == DRAG:
            if not pi:
                ev.append("drag_end")
                self.state = MOVE

        elif self.state == RIGHT:
            if not pm:
                if now - self._t0 <= c.right_click_max_s:
                    ev.append("right_click")
                self.state = MOVE

        elif self.state in (SCROLL, VOLUME):
            # Entering needed a steady pose (stable); leaving reacts to the raw pose within
            # EXIT_FRAMES, and nothing scrolls while the pose is wrong, so lowering the hand
            # while changing fingers can't cause a stray scroll / volume change.
            now_mode = {"two": SCROLL, "three": VOLUME}.get(hand.pose)
            if now_mode == self.state:
                self._off = 0
                scroll = self._motion(hand, ev)
            else:
                self._off += 1
                if self._off >= self.EXIT_FRAMES:
                    if now_mode is None:                 # pose released -> back to cursor
                        self.state = MOVE
                    else:                                # two <-> three
                        self.state = now_mode
                        self._start_motion(hand)
            pi = pm = False                              # thumb position is irrelevant here

        self._pinch_i, self._pinch_m = pi, pm
        return Output(self.state, self.state in (MOVE, DRAG), ev, scroll)
