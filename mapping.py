"""Maps the palm position in the camera frame to full-screen coordinates.

Only a centred 'active zone' of the camera frame is used. Positions outside
the zone are clamped, so every screen edge and corner is reachable without
your hand leaving the camera view.
"""


class ScreenMapper:
    def __init__(self, screen_w, screen_h, cfg):
        self.sw, self.sh = screen_w, screen_h
        self.cfg = cfg
        self.sensitivity = cfg.sensitivity

    def adjust(self, delta):
        c = self.cfg
        self.sensitivity = min(c.sens_max, max(c.sens_min, self.sensitivity + delta))

    def zone(self):
        """Active zone as (x0, y0, x1, y1) in normalised camera coords."""
        half = 0.5 / self.sensitivity
        cx, cy = self.cfg.zone_center_x, self.cfg.zone_center_y
        return cx - half, cy - half, cx + half, cy + half

    def to_screen(self, nx, ny):
        x0, y0, x1, y1 = self.zone()
        u = min(1.0, max(0.0, (nx - x0) / (x1 - x0)))
        v = min(1.0, max(0.0, (ny - y0) / (y1 - y0)))
        return u * (self.sw - 1), v * (self.sh - 1)
