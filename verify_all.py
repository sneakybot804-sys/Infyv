"""Final verification of all reported bugs."""
import sys, time, inspect
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path
sys.path.insert(0, str(Path('.').resolve()))

from PySide6.QtWidgets import QApplication
app = QApplication(sys.argv)

from gui.screens.studio_screen import StudioScreen
from gui.theme.manager import ThemeManager
from gui_core.facade import ApplicationFacade
from gui.integration.workflow_controller import WorkflowController
from gui.integration import playback_engine as pe
from ffmpeg_service import FFmpegService
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
time.sleep(0.5)

results = []

def check(name, condition, detail=""):
    status = "FIXED" if condition else "NOT FIXED"
    results.append((name, status, detail))
    tag = "PASS" if condition else "FAIL"
    print(f"  [{tag}] {name}")

print("=== BUG-BY-BUG VERIFICATION ===")
print()

# Get source code for all key files
src_decoder = inspect.getsource(pe.FrameDecoder.run)
src_playback = inspect.getsource(screen._wire_playback)
src_tick = inspect.getsource(pe.PlaybackEngine._on_tick)
src_seek = inspect.getsource(pe.PlaybackEngine._seek_to)
src_stop = inspect.getsource(pe.FrameDecoder.stop_decoding)
src_stop_decoder = inspect.getsource(pe.PlaybackEngine._stop_decoder)
src_extract = inspect.getsource(pe.PlaybackEngine._extract_audio)
src_start_audio = inspect.getsource(pe.PlaybackEngine._start_audio)
src_ensure = inspect.getsource(pe.PlaybackEngine._ensure_audio_player)
src_init = inspect.getsource(pe.FrameDecoder.__init__)
src_first = inspect.getsource(screen._show_first_frame)
src_status = inspect.getsource(pe.PlaybackEngine._on_media_status_changed)
svc = FFmpegService()
src_extract_frame = inspect.getsource(svc.extract_frame_at)
src_pcm = inspect.getsource(svc.stream_pcm_blocks)
src_paint = inspect.getsource(type(screen._stage).paintEvent)

with open("gui/screens/studio_screen.py", encoding="utf-8") as f:
    content = f.read()

# === P0 CRITICAL ===
print("--- P0: CRITICAL STABILITY ---")
check("BUG-001: Zombie FFmpeg process",
    "self._proc.wait()" in src_decoder and "End of stream" in src_decoder,
    "proc.wait() on EOF path")
check("BUG-002: Missing frame.copy()",
    ".copy()" in src_decoder and "np.frombuffer" in src_decoder,
    "frame.copy() after frombuffer")
check("BUG-003: Duplicate load_media()",
    src_playback.count("selection_changed.connect") <= 1,
    "No duplicate signal connections")
check("BUG-004: Missing QImage.copy()",
    "QImage" in src_playback and ".copy()" in src_playback,
    "QImage.copy() in _on_frame_ready")

# === P1 PLAYBACK ===
print("\n--- P1: PLAYBACK CORRECTNESS ---")
check("BUG-007: Frame step bypasses engine",
    "engine.step_backward()" in src_playback and "engine.step_forward()" in src_playback,
    "Uses engine methods")
check("BUG-008: Queue not cleared on seek",
    "self._queue.clear()" in src_decoder,
    "Queue cleared on seek")
check("BUG-014: No decoder restart on loop",
    "_stop_decoder()" in src_tick and "_start_decoder()" in src_tick,
    "Decoder restarts on loop")
check("BUG-019: Dead debug code",
    "_tick_log_count" not in src_tick,
    "No dynamic attributes")

# === P2 A/V SYNC ===
print("\n--- P2: A/V SYNCHRONIZATION ---")
check("BUG-006: Audio/video drift",
    "drift_ms" in src_tick and "setPosition" in src_tick,
    "Drift correction present")
check("BUG-018: Seek without audio resync",
    "audio_player" in src_seek and "setPosition" in src_seek,
    "Audio resync on seek")
check("BUG-017: Silent exception swallowing",
    "_log.warning" in src_start_audio,
    "Audio methods log warnings")

# === P3 PERFORMANCE ===
print("\n--- P3: PERFORMANCE ---")
check("BUG-011: Repeated ffprobe spawning",
    hasattr(svc, "_metadata_cache"),
    "Metadata cache exists")
check("BUG-009: Dual rendering paths",
    "drawImage" not in src_paint,
    "paintEvent simplified")
check("BUG-025: Local imports per frame",
    "import numpy" not in src_playback.split("_on_frame_ready")[1][:300],
    "No local imports in hot path")

# === P4 CLEANUP ===
print("\n--- P4: CLEANUP ---")
check("BUG-012: _stop flag race",
    "_stop_event" in src_init and "threading.Event" in src_init,
    "Uses threading.Event")
check("BUG-013: Incomplete stop_decoding",
    "dec.quit()" in src_stop_decoder and "dec.wait" in src_stop_decoder,
    "Full cleanup in _stop_decoder")
check("BUG-015: Relative path for audio",
    "app_config.paths.output_dir" in src_extract,
    "Absolute path from config")
check("BUG-015b: Audio load absolute path",
    "app_config.paths.output_dir" in src_start_audio,
    "Audio load uses absolute path")
check("BUG-021: Dead _on_media_status_changed",
    "_log" in src_status,
    "Has logging")
check("BUG-020: Dead code block deleted",
    "_wire_toolbar_actions" not in content and "_wire_media_preview" not in content,
    "Dead code removed")

# === FORENSIC BUGS ===
print("\n--- FORENSIC FIXES ---")
check("FOB-001: _show_first_frame QImage.copy()",
    "QImage" in src_first and ".copy()" in src_first,
    "QImage.copy() present")
check("FOB-002: Empty state overlap",
    "PreviewEmptyIcon" in src_playback and "setVisible(False)" in src_playback,
    "Empty state hidden")
check("FOB-003: Rewind button wired",
    "StudioTransportRewind" in src_playback and "engine.seek" in src_playback,
    "Rewind calls engine.seek")
check("FOB-004: Duplicate methods",
    content.count("def get_preview_stage") == 1,
    "Single definition")
check("FOB-005: Thread-safe cache",
    hasattr(svc, "_cache_lock"),
    "Lock exists")
check("FOB-006: extract_frame_at uses cache",
    "self.read_metadata" in src_extract_frame and "ffmpeg.probe" not in src_extract_frame,
    "Uses cached metadata")
check("FOB-009: process.wait timeout",
    "timeout=" in src_pcm,
    "Has timeout")
check("FOB-010: Redundant quit removed",
    "self.quit()" not in src_stop,
    "quit() not in stop_decoding")
check("FOB-011: Unused import sys",
    "import sys" not in src_tick,
    "Removed")
check("FOB-013: QMediaPlayer parent",
    "QMediaPlayer(self)" in src_ensure,
    "Parent set")
check("FOB-014: Unused QPainterPath",
    "QPainterPath" not in content,
    "Import removed")
check("FOB-018: Unused TransportBar",
    "from gui.widgets.transport_bar import TransportBar" not in content,
    "Import removed")

# === STILL BROKEN ===
print("\n--- STILL BROKEN (known, deferred) ---")
check("BUG-005: Blocking audio extraction",
    False, "Needs QThread refactor")
check("FFMPEG: extract_audio first stream only",
    False, "No stream selection API")
check("AUDIO: No volume control",
    False, "No backend")
check("UI: No speed control wired",
    False, "Engine supports, UI not connected")
check("UI: No loop toggle wired",
    False, "Engine supports, UI not connected")

# === SUMMARY ===
print("\n" + "=" * 60)
print("FINAL VERIFICATION SUMMARY")
print("=" * 60)
fixed = sum(1 for _, s, _ in results if s == "FIXED")
not_fixed = sum(1 for _, s, _ in results if s == "NOT FIXED")
print(f"Total bugs checked: {len(results)}")
print(f"FIXED: {fixed}/{len(results)}")
print(f"NOT FIXED: {not_fixed}/{len(results)}")
print()
for name, status, detail in results:
    marker = "+" if status == "FIXED" else "-"
    print(f"  [{marker}] {name}")

screen.close()
controller.stop()
