# Hand-Gesture PC Control (webcam only)

Control your PC with hand gestures using nothing but a normal webcam, no extra
hardware. Built with Python, OpenCV, MediaPipe and PyAutoGUI.

**Features**
- Palm-anchored cursor with One Euro smoothing, so it stays steady while you click or drag
- Full-screen movement with adjustable sensitivity (every edge and corner reachable)
- Click, double click, right click and drag-and-drop by pinching
- Scroll and volume control with finger poses
- Air Canvas: draw in the air, pick colours, erase, save as PNG
- Teach your own gestures and attach actions (open an app or website, press a shortcut)

**Tech:** Python 3.9-3.12, OpenCV, MediaPipe Hands, NumPy, PyAutoGUI

<!-- Add a demo GIF or screenshots here, e.g. ![demo](docs/demo.gif) -->

## Project structure

| File | Role |
|---|---|
| `config.py` | Every tunable setting (sensitivity, smoothing, thresholds, scroll, canvas, custom gestures) |
| `tracker.py` | MediaPipe hand tracking, palm-centre anchor, finger poses, pinch/fist measurements |
| `smoothing.py` | One Euro filter + deadzone (removes jitter) |
| `mapping.py` | Camera zone -> full screen, edges and corners reachable |
| `gestures.py` | State machine: move / click / drag / right-click / scroll / volume / pause |
| `controller.py` | The only module that touches the OS mouse and keyboard (PyAutoGUI) |
| `canvas.py` | Air Canvas: draw with your index finger |
| `custom.py` | Stores, recognises and runs custom gestures |
| `teach.py` | Records a new custom gesture (`python teach.py`) |
| `main.py` | Webcam loop, preview window, keyboard shortcuts |
| `start.bat` | Windows double-click launcher (uses the `venv` folder next to it if there is one) |

Created while you use it: `drawings/` (saved pictures) and `custom_gestures.json`.

## Setup (Python 3.9 - 3.12)

**Windows (PowerShell / CMD)**
```
python -m venv venv
venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

**macOS / Linux**
```
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

Use Python 3.9-3.12 (MediaPipe doesn't support newer versions yet). No new
libraries are needed for the newer features.

- **macOS:** allow your Terminal/IDE under System Settings > Privacy & Security > Camera, Accessibility and Input Monitoring.
- **Linux:** use an X11 session (PyAutoGUI does not work on Wayland). You may also need `sudo apt install python3-tk python3-dev scrot`.
- **Volume gesture** sends the keyboard volume keys: works on Windows, may not on macOS/Linux.

## Mouse gestures

| Gesture | Action |
|---|---|
| Open hand, move palm | Move cursor |
| Thumb + index pinch, quick tap | Left click (tap twice = double click) |
| Thumb + index pinch, hold ~0.3 s | Grab (drag). Move, then release pinch to drop |
| Thumb + middle tap | Right click |
| **Index + middle up** (peace sign), hold ~0.25 s, then move hand up/down | **Scroll** (cursor stays where it was) |
| **Index + middle + ring up**, hold ~0.25 s, then move hand up/down | **Volume** up/down |
| Closed fist | Pause (cursor frozen, drag released) |

Drop the extra fingers to go back to the cursor. The cursor jumps to where your
palm is when you do, so lower your hand first if that bothers you.

## Air Canvas

Press **`c`** in the preview window to switch between Mouse and Canvas mode. In
Canvas mode the mouse is not touched.

| Gesture | Action |
|---|---|
| Index finger only | Draw |
| Index + middle (peace sign) | Pen up. Hover a toolbar button to pick it |
| Anything else | Pen up |

Toolbar: Red, Green, Blue, Yellow, Black, Eraser, Clear, Save. Hold your
fingertip over a button until its green bar fills (Clear and Save take longer
so you can't hit them by accident). `s` saves, `x` clears from the keyboard.
Pictures go to the `drawings/` folder as PNG on a white background.

## Custom gestures

1. Run `python teach.py` (close `main.py` first, the webcam can only be used once).
2. Type a name, then choose what it does: open an app/file/folder, open a website, or press a keyboard shortcut (e.g. `ctrl+shift+s`, `win+d`).
3. Show the gesture, press **SPACE**. After a 3 second countdown it records for ~2.5 s: hold the shape and move your hand around a little. Press **S** to save.
4. Run `python main.py`. Hold the gesture for about a second and the action runs once. Release it to be able to trigger it again.

Other commands: `python teach.py --list`, `python teach.py --delete NAME`.

Good shapes: thumbs up, rock sign (index + pinky), shaka (thumb + pinky), or any
fist variant. `teach.py` warns you when a shape clashes with the built-in
gestures (open hand, two or three fingers up, or thumb touching a finger).
Gestures only trigger in Mouse mode, and not during a click or drag. With a
custom gesture on screen, the preview shows `custom: NAME (0.xx)`: below 1.00
means a match, so you can see how close you are.

## Keyboard shortcuts (preview window focused)

`c` mouse/canvas - `+` / `-` sensitivity - `p` enable/disable control - `z` show/hide zone box - `s` save drawing - `x` clear drawing - `q` or `Esc` quit

## How jitter is avoided

1. The cursor follows the **palm centre** (wrist + 4 knuckles), not a fingertip, so pinching barely moves it.
2. The cursor is **frozen** while a pinch is pending, so clicks land where you aimed.
3. A **One Euro filter** smooths slow movement heavily and fast movement lightly, plus a small pixel deadzone.
4. Pinch uses **hysteresis** (`pinch_on` < `pinch_off`) so it doesn't flicker on and off.

## Tuning (`config.py`)

- Cursor shakes: lower `min_cutoff` (1.2 -> 0.8) or raise `deadzone_px`.
- Cursor feels laggy: raise `beta` (0.015 -> 0.05).
- Can't reach screen edges: raise `sensitivity` (or press `+`).
- Pinch triggers too easily / not enough: adjust `pinch_on` and `pinch_off`.
- Accidental drags: raise `drag_hold_s`.
- Scroll too fast / slow: change `scroll_gain`. Wrong direction: `scroll_invert = True`.
- Volume too sensitive: raise `volume_step_norm`.
- Fingers are misread as up/down: change `finger_ext_ratio` (higher = a finger must be straighter to count as up).
- Wobbly drawing: lower `canvas_min_cutoff`. Thicker pen: `brush_size`.
- Custom gesture never triggers: raise `custom_threshold_scale` (2.0 -> 3.0) or re-teach it with more movement. Triggers by accident: lower it, or raise `custom_hold_s`.
- Wrong camera: set `camera_index = 1`.

Tips: good front lighting, plain background, hand about 40-70 cm from the camera.

## Safety

`pyautogui.FAILSAFE` is off so corners work. Press `p` to disable control, or `q` to quit. The mouse button is always released on exit. Custom gestures can open programs and press keys, so only teach actions you are happy to trigger.

## License

MIT, see `LICENSE`.
