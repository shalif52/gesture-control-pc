"""Thin wrapper around PyAutoGUI. The only module that touches the OS mouse/keyboard."""
import sys

import pyautogui

pyautogui.FAILSAFE = False   # allow the cursor to reach screen corners
pyautogui.PAUSE = 0          # no built-in delay between calls


class MouseController:
    def __init__(self):
        self.size = pyautogui.size()
        self._down = False
        self._scroll_rem = 0.0

    def move(self, x, y):
        pyautogui.moveTo(int(x), int(y), _pause=False)

    def scroll(self, units):
        """units: + = up. 120 units = one wheel notch (the Windows convention)."""
        if sys.platform != "win32":              # macOS/Linux scroll in "lines"
            self._scroll_rem += units / 40.0
            units = int(self._scroll_rem)
            self._scroll_rem -= units
        if units:
            pyautogui.scroll(int(units))

    def handle(self, event):
        if event == "left_click":
            pyautogui.click()
        elif event == "right_click":
            pyautogui.click(button="right")
        elif event == "drag_start" and not self._down:
            pyautogui.mouseDown()
            self._down = True
        elif event == "drag_end" and self._down:
            pyautogui.mouseUp()
            self._down = False
        elif event == "volume_up":
            pyautogui.press("volumeup")          # Windows: +2% per press
        elif event == "volume_down":
            pyautogui.press("volumedown")

    def release(self):
        """Safety: never leave the button stuck down."""
        if self._down:
            pyautogui.mouseUp()
            self._down = False
