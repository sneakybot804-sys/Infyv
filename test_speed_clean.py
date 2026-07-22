"""Clean speed measurement without monkey-patches."""
import sys, time
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path
sys.path.insert(0, str(Path('.').resolve()))

from PySide6.QtWidgets import QApplication
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
video = str(Path('videos/test_30fps_60s.mp4').resolve())
engine.load_media(video, 60.0, 30.0)
app.processEvents()
time.sleep(0.5)

print("=== CLEAN SPEED TEST (no patches) ===")
print("Video: 30 FPS, 60s, 1800 frames")
print()

engine.play()
start = time.monotonic()
samples = []

for i in range(500):
    app.processEvents()
    time.sleep(0.01)
    now = time.monotonic()
    elapsed = now - start
    if elapsed >= 5:
        break
    idx = int(elapsed * 2)
    if idx > len(samples):
        ph = engine._playhead
        dec = engine._decoder
        qs = len(dec._queue) if dec else -1
        fs = engine._decoder_frames_shown
        samples.append((elapsed, ph, qs, fs))

engine.stop()

print("Real(s) | Playhead | Queue | Shown | Rate")
print("-" * 50)
for elapsed, ph, qs, fs in samples:
    rate = ph / elapsed if elapsed > 0 else 0
    print(f"{elapsed:7.2f} | {ph:8.3f} | {qs:5d} | {fs:5d} | {rate:.2f}x")

if samples:
    final_ph = samples[-1][1]
    final_t = samples[-1][0]
    actual_rate = final_ph / final_t if final_t > 0 else 0
    print()
    print(f"Final: playhead={final_ph:.3f}s after {final_t:.2f}s real")
    print(f"Playback rate: {actual_rate:.3f}x (should be 1.000x)")
    if 0.95 <= actual_rate <= 1.05:
        print("Status: CORRECT")
    elif actual_rate > 1.05:
        print(f"Status: WRONG - FAST ({actual_rate:.2f}x)")
    else:
        print(f"Status: WRONG - SLOW ({actual_rate:.2f}x)")

screen.close()
controller.stop()
