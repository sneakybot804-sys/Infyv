"""Full player runtime check — every control, real videos, real measurements."""
import os, time
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication, QLabel, QWidget
from PySide6.QtCore import QEventLoop, QTimer

app = QApplication.instance() or QApplication([])

from gui.theme.manager import ThemeManager
from gui.workspace_window import build_workspace_window, _build_production_controller

R = []
def check(name, ok, detail=""):
    R.append(("PASS" if ok else "FAIL", name, detail))

def pump(ms=200):
    loop = QEventLoop(); QTimer.singleShot(ms, loop.quit); loop.exec()

t = ThemeManager(); t.apply(app)
c = _build_production_controller()
w = build_workspace_window(t, c); w.show()
s = w.centralWidget()
pump(300)

# ---- 1. Select 720p30 media ----
items = s._browser.items()
idx = items.index("hd_test.avi")
s._browser.select(idx); pump(600)
check("media select", s._media_path is not None and s._media_path.name == "hd_test.avi")
check("fps detected", s._media_fps() == 30.0, f"fps={s._media_fps()}")
check("duration set", abs(s._timeline.duration() - 3.0) < 0.1, f"dur={s._timeline.duration()}")

# ---- 2. First frame shown, fills stage ----
sink = s._preview_frame
pm = sink.pixmap()
stage = sink.parentWidget()
check("first frame shown", pm is not None and not pm.isNull(), f"pm={pm.size() if pm else None}")
if pm and stage:
    fill_h = pm.height() / max(1, stage.height())
    fill_w = pm.width() / max(1, stage.width())
    check("frame fills stage", fill_h > 0.85 or fill_w > 0.85,
          f"{pm.width()}x{pm.height()} in {stage.width()}x{stage.height()}")

# ---- 3. Play: frames at native fps, drift < 150ms ----
frames = [0]
orig_show = s.show_frame
def counting(bgr):
    frames[0] += 1
    orig_show(bgr)
s.show_frame = counting
t0 = time.monotonic()
s._transport._play.clicked.emit()
pump(2000)
elapsed = time.monotonic() - t0
ph = s._timeline.playhead()
check("playback playing", s._timeline.is_playing() or ph >= 2.9)
check("decoder running", s._decoder is not None or ph >= 2.9)
rate = frames[0] / elapsed
check("display rate ~30fps", rate >= 24, f"{rate:.1f} fps ({frames[0]} in {elapsed:.1f}s)")
check("A/V drift < 150ms", abs(ph - elapsed) < 0.15, f"playhead={ph:.2f} wall={elapsed:.2f}")

# ---- 4. Pause freezes; resume continues ----
s._transport._pause.clicked.emit(); pump(300)
check("pause state", s._timeline.playback_state() == "paused")
check("decoder stopped on pause", s._decoder is None)
ph_paused = s._timeline.playhead()
pump(400)
check("playhead frozen while paused", s._timeline.playhead() == ph_paused)
frames[0] = 0
s._transport._play.clicked.emit(); pump(700)
check("resume plays", frames[0] > 0 and s._timeline.is_playing() or s._timeline.playhead() >= 2.9,
      f"frames={frames[0]}")

# ---- 5. Stop resets to 0 ----
s._transport._stop.clicked.emit(); pump(300)
check("stop resets", s._timeline.playback_state() == "stopped" and s._timeline.playhead() == 0.0)
check("decoder stopped on stop", s._decoder is None)

# ---- 6. Seek (paused): frame updates at position ----
s._frame_on_screen = None
s._on_transport_seek(0.5); pump(400)
check("seek moves playhead", abs(s._timeline.playhead() - 1.5) < 0.1,
      f"ph={s._timeline.playhead():.2f}")
pm2 = sink.pixmap()
check("seek decodes frame", pm2 is not None and not pm2.isNull())

# ---- 7. Seek during playback re-anchors decoder ----
s._transport._play.clicked.emit(); pump(300)
s._on_transport_seek(0.2); pump(500)
check("live seek re-anchor", abs(s._decoder_start - 0.6) < 0.05,
      f"decoder_start={getattr(s, '_decoder_start', -1):.2f}")
check("live seek playhead follows", s._timeline.playhead() >= 0.55,
      f"ph={s._timeline.playhead():.2f}")
s._transport._stop.clicked.emit(); pump(300)

# ---- 8. Frame stepping ----
s._timeline.set_playhead(1.0); pump(100)
before = s._timeline.playhead()
s._step_frames(1); pump(200)
check("step +1 frame", abs(s._timeline.playhead() - before - 1/30.0) < 0.01,
      f"{before:.3f} -> {s._timeline.playhead():.3f}")
s._step_frames(-1); pump(200)
check("step -1 frame", abs(s._timeline.playhead() - before) < 0.01)

# ---- 9. Shuttle ±5s (clamped to duration) ----
s._timeline.set_playhead(1.0)
s._shuttle(5.0); pump(100)
check("shuttle fwd clamps", s._timeline.playhead() == 3.0, f"ph={s._timeline.playhead()}")
s._shuttle(-5.0); pump(100)
check("shuttle back clamps", s._timeline.playhead() == 0.0)

# ---- 10. Playback speed ----
s._timeline.set_playback_rate(2.0)
s._timeline.set_playhead(0.0)
t0 = time.monotonic()
s._transport._play.clicked.emit()
pump(1000)
elapsed = time.monotonic() - t0
ph = s._timeline.playhead()
s._transport._stop.clicked.emit(); pump(200)
check("2x speed doubles playhead", abs(ph - 2 * elapsed) < 0.3,
      f"ph={ph:.2f} wall={elapsed:.2f} (expected ~{2*elapsed:.2f})")
s._timeline.set_playback_rate(1.0)

# ---- 11. Loop ----
s._loop_enabled = True
s._timeline.set_playhead(2.7)
s._transport._play.clicked.emit()
pump(1200)  # crosses 3.0 end -> should loop to 0 and continue
looped = s._timeline.is_playing() and s._timeline.playhead() < 2.0
check("loop wraps and continues", looped,
      f"state={s._timeline.playback_state()} ph={s._timeline.playhead():.2f}")
s._transport._stop.clicked.emit(); pump(200)
s._loop_enabled = False

# ---- 12. End-of-video without loop stops ----
s._timeline.set_playhead(2.7)
s._transport._play.clicked.emit()
pump(1000)
check("end stops playback", s._timeline.playback_state() == "stopped",
      f"state={s._timeline.playback_state()}")

# ---- 13. Zoom modes ----
s._preview_zoom = "50%"
s._invalidate_frame_cache()
s._decode_and_show(1.0); pump(100)
pm50 = sink.pixmap()
check("zoom 50%", pm50 is not None and abs(pm50.width() - 640) <= 2,
      f"pm={pm50.size() if pm50 else None} (expected 640 wide)")
s._preview_zoom = "Fill"
s._invalidate_frame_cache()
s._decode_and_show(1.0); pump(100)
pmf = sink.pixmap()
if pmf and stage:
    check("zoom Fill covers stage", pmf.width() >= stage.width() - 4,
          f"pm={pmf.width()} stage={stage.width()}")
s._preview_zoom = "Fit"

# ---- 14. Media switch: decoder cleanup + new frame ----
s._transport._play.clicked.emit(); pump(300)
idx2 = items.index("audit_clip.avi")
s._browser.select(idx2); pump(600)
check("switch stops decoder", s._decoder is None)
check("switch loads new media", s._media_path.name == "audit_clip.avi")
check("switch updates duration", abs(s._timeline.duration() - 6.0) < 0.1)
pm3 = sink.pixmap()
check("switch shows new frame", pm3 is not None and not pm3.isNull())

# ---- 15. Rapid scrub (no crash, no stall) ----
t0 = time.monotonic()
for frac in (0.1, 0.9, 0.3, 0.7, 0.5):
    s._on_transport_seek(frac); pump(50)
scrub_time = time.monotonic() - t0
check("rapid scrub responsive", scrub_time < 3.0, f"{scrub_time:.2f}s for 5 seeks")

c.stop()

print()
fails = [x for x in R if x[0] == "FAIL"]
print(f"PLAYER CHECK: {len(R)-len(fails)} PASS / {len(fails)} FAIL of {len(R)}")
for status, name, detail in R:
    line = f"[{status}] {name}"
    if detail:
        line += f"  ({detail})"
    print(line)
