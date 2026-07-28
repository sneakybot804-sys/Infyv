"""Test 60fps playback speed."""
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
theme = ThemeManager(); theme.apply(app)
screen = StudioScreen(theme, controller=controller)
screen.show(); app.processEvents()
engine = screen._playback_engine

video = str(Path('videos/test_60fps.mp4').resolve())
print("=== 60FPS VIDEO TEST ===")
engine.load_media(video, 30.0, 60.0)
app.processEvents(); time.sleep(0.5)

print("Starting playback...")
engine.play()

samples = []
t0 = time.monotonic()
while True:
    app.processEvents()
    time.sleep(0.02)
    elapsed = time.monotonic() - t0
    ph = engine._playhead
    idx = int(elapsed * 5)
    if idx > len(samples):
        samples.append((elapsed, ph))
        print(f"  t={elapsed:.1f}s ph={ph:.3f}s")
    if elapsed >= 5:
        break

engine.stop()

print()
print("=== RESULTS ===")
for e, ph in samples:
    rate = ph / e if e > 0 else 0
    print(f"  t={e:.1f}s ph={ph:.3f}s rate={rate:.2f}x")

if samples:
    final_rate = samples[-1][1] / samples[-1][0]
    print(f"\n  FINAL: {final_rate:.3f}x")
    if 0.97 <= final_rate <= 1.03:
        print("  STATUS: CORRECT")
    elif final_rate > 1.03:
        print(f"  STATUS: FAST ({final_rate:.2f}x)")
    else:
        print(f"  STATUS: SLOW ({final_rate:.2f}x)")

screen.close(); controller.stop()
