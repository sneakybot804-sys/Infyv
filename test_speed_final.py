"""Definitive speed measurement using QTimer for sampling."""
import sys, time
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path
sys.path.insert(0, str(Path('.').resolve()))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

app = QApplication(sys.argv)

from gui.screens.studio_screen import StudioScreen
from gui.theme.manager import ThemeManager
from gui_core.facade import ApplicationFacade
from gui.integration.workflow_controller import WorkflowController
from config import config

config.ensure_directories()
facade = ApplicationFacade(config)
controller = WorkflowController(facade)
controller.start()
theme = ThemeManager()
theme.apply(app)
screen = StudioScreen(theme, controller=controller)
screen.show()
app.processEvents()

engine = screen._playback_engine
video = str(Path("videos/test_30fps_60s.mp4").resolve())
engine.load_media(video, 60.0, 30.0)
app.processEvents()
time.sleep(0.5)

# State
samples = []
real_start = None

def sample():
    global real_start
    if real_start is None:
        real_start = time.monotonic()
    now = time.monotonic()
    elapsed = now - real_start
    ph = engine._playhead
    dec = engine._decoder
    qs = len(dec._queue) if dec else -1
    fs = engine._decoder_frames_shown
    state = engine._state
    samples.append((elapsed, ph, qs, fs, state))

# Sample every 100ms
sample_timer = QTimer()
sample_timer.timeout.connect(sample)
sample_timer.start(100)

# Start playback
engine.play()
app.processEvents()

# Run for 8 seconds
app.exec_() if hasattr(app, 'exec_') else None

# Actually, use a timeout to stop
stop_timer = QTimer()
stop_timer.setSingleShot(True)
def stop_now():
    engine.stop()
    sample_timer.stop()
    app.quit()
stop_timer.timeout.connect(stop_now)
stop_timer.start(8000)

app.exec()

# Analyze
print("=== DEFINITIVE SPEED TEST ===")
print("Video: 30 FPS, 60s, 1800 frames")
print("Method: QTimer sampling every 100ms (no monkey-patches)")
print()
print("Real(s) | Playhead | Queue | Shown | State | Rate")
print("-" * 60)
for elapsed, ph, qs, fs, state in samples[::5]:  # Every 500ms
    rate = ph / elapsed if elapsed > 0 else 0
    print(f"{elapsed:7.2f} | {ph:8.3f} | {qs:5d} | {fs:5d} | {state:7s} | {rate:.2f}x")

if samples:
    final_ph = samples[-1][1]
    final_t = samples[-1][0]
    actual_rate = final_ph / final_t if final_t > 0 else 0
    print()
    print(f"Final: playhead={final_ph:.3f}s after {final_t:.2f}s real")
    print(f"Playback rate: {actual_rate:.3f}x (should be 1.000x)")
    if 0.97 <= actual_rate <= 1.03:
        print("Status: CORRECT (within 3%)")
    elif actual_rate > 1.03:
        print(f"Status: WRONG - FAST ({actual_rate:.2f}x)")
    else:
        print(f"Status: WRONG - SLOW ({actual_rate:.2f}x)")

screen.close()
controller.stop()
