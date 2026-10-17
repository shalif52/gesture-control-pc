"""One Euro filter: strong smoothing when the hand is slow/still (kills jitter),
light smoothing when it moves fast (keeps the cursor responsive)."""
import math


class _LowPass:
    def __init__(self):
        self.y = None

    def __call__(self, x, alpha):
        self.y = x if self.y is None else alpha * x + (1 - alpha) * self.y
        return self.y


class OneEuroFilter:
    def __init__(self, min_cutoff, beta, d_cutoff):
        self.min_cutoff, self.beta, self.d_cutoff = min_cutoff, beta, d_cutoff
        self._x, self._dx = _LowPass(), _LowPass()
        self._prev = None
        self._t = None

    @staticmethod
    def _alpha(cutoff, dt):
        tau = 1.0 / (2 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def __call__(self, x, t):
        if self._t is None:
            self._t, self._prev = t, x
            return self._x(x, 1.0)
        dt = max(t - self._t, 1e-4)
        dx = (x - self._prev) / dt
        edx = self._dx(dx, self._alpha(self.d_cutoff, dt))
        cutoff = self.min_cutoff + self.beta * abs(edx)
        out = self._x(x, self._alpha(cutoff, dt))
        self._t, self._prev = t, x
        return out


class PointFilter:
    """Smooths an (x, y) point and ignores tiny movements (deadzone).

    min_cutoff / beta / deadzone default to the cursor values in Config;
    the Air Canvas passes its own so pen strokes can be tuned separately.
    """

    def __init__(self, cfg, min_cutoff=None, beta=None, deadzone=None):
        mc = cfg.min_cutoff if min_cutoff is None else min_cutoff
        b = cfg.beta if beta is None else beta
        self._fx = OneEuroFilter(mc, b, cfg.d_cutoff)
        self._fy = OneEuroFilter(mc, b, cfg.d_cutoff)
        self._dead = cfg.deadzone_px if deadzone is None else deadzone
        self._last = None

    def __call__(self, x, y, t):
        sx, sy = self._fx(x, t), self._fy(y, t)
        if self._last is not None and self._dead > 0:
            if math.hypot(sx - self._last[0], sy - self._last[1]) < self._dead:
                return self._last
        self._last = (sx, sy)
        return self._last

    def reset(self):
        self._last = None
