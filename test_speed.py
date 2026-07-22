"""Instrument playback engine and measure frame timing."""
import sys, time, threading
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
from gui.integration.playback_engine import PlaybackEngine
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

# === INSTRUMENT: Log every frame display ===
frame_log = []
original_emit = engine.frame_ready.emit

def logging_emit(frame):
    now = time.monotonic()
    frame_log.append({
        'wall_clock': now,
        'playhead': engine._playhead,
        'state': engine._state,
        'rate': engine._playback_rate,
        'decoder_start': engine._decoder_start,
        'frames_shown': engine._decoder_frames_shown,
        'queue_size': len(engine._decoder._queue) if engine._decoder else 0,
    })
    original_emit(frame)

engine.frame_ready.connect(logging_emit)

# === INSTRUMENT: Log tick timing ===
tick_log = []
original_tick = engine._on_tick.__func__

def logging_tick(self):
    now = time.monotonic()
    tick_log.append({
        'wall_clock': now,
        'playhead': self._playhead,
        'state': self._state,
    })
    original_tick(self)

import types
engine._on_tick = types.MethodType(logging_tick, engine)

# === Load test video ===
test_video = str(Path('videos/test_30fps_60s.mp4').resolve())
print(f'Loading: {test_video}')

import ffmpeg
probe = ffmpeg.probe(test_video)
for s in probe['streams']:
    if s['codec_type'] == 'video':
        duration = float(s.get('duration', 0))
        fps_parts = s.get('r_frame_rate', '30/1').split('/')
        fps = int(fps_parts[0]) / int(fps_parts[1]) if len(fps_parts) == 2 else 30.0
        print(f'Video: {duration}s, {fps} FPS, {int(s.get("nb_frames", 0))} frames')

# Load into engine
engine.load_media(test_video, duration, fps)
app.processEvents()
time.sleep(0.5)

# === Play for 10 seconds ===
print('\\n=== PLAYING FOR 10 SECONDS ===')
engine.play()
app.processEvents()

# Run event loop for 10 seconds
start_time = time.monotonic()
while time.monotonic() - start_time < 10:
    app.processEvents()
    time.sleep(0.001)

engine.stop()
app.processEvents()

# === ANALYZE ===
print(f'\\n=== RESULTS ===')
print(f'Total frames displayed: {len(frame_log)}')
print(f'Total ticks: {len(tick_log)}')

if frame_log:
    # Expected frames in 10 seconds at 30fps = 300
    expected_frames = int(10 * fps)
    print(f'Expected frames in 10s at {fps}fps: {expected_frames}')
    print(f'Actual frames displayed: {len(frame_log)}')
    print(f'Frame ratio: {len(frame_log) / expected_frames:.2f}x')

    # Check playhead at end
    print(f'\\nFinal playhead: {frame_log[-1]["playhead"]:.3f}s')
    print(f'Expected playhead at 10s: ~10.000s')

    # Frame-by-frame analysis
    print(f'\\n--- FRAME TIMING ANALYSIS ---')
    if len(frame_log) > 1:
        intervals = []
        for i in range(1, len(frame_log)):
            dt = frame_log[i]['wall_clock'] - frame_log[i-1]['wall_clock']
            intervals.append(dt)

        avg_interval = sum(intervals) / len(intervals) if intervals else 0
        expected_interval = 1.0 / fps

        print(f'Average frame interval: {avg_interval*1000:.2f}ms')
        print(f'Expected frame interval: {expected_interval*1000:.2f}ms')
        print(f'Frame display rate: {1/avg_interval:.2f} fps (if avg interval correct)')

        # Check for skipped frames
        skips = 0
        for i in range(1, len(frame_log)):
            dt = frame_log[i]['wall_clock'] - frame_log[i-1]['wall_clock']
            if dt > expected_interval * 1.5:
                skips += 1
        print(f'Frames with >50% late interval: {skips}')

        # Check playhead progression
        print(f'\\n--- PLAYHEAD ANALYSIS ---')
        for i in range(0, min(len(frame_log), 20)):
            entry = frame_log[i]
            expected_pts = entry['decoder_start'] + entry['frames_shown'] / fps
            print(f'Frame {i}: playhead={entry["playhead"]:.3f}s '
                  f'queue={entry["queue_size"]} '
                  f'rate={entry["rate"]}x')

    # Check tick timing
    if tick_log and len(tick_log) > 1:
        print(f'\\n--- TICK TIMING ---')
        tick_intervals = []
        for i in range(1, len(tick_log)):
            dt = tick_log[i]['wall_clock'] - tick_log[i-1]['wall_clock']
            tick_intervals.append(dt)
        avg_tick = sum(tick_intervals) / len(tick_intervals) if tick_intervals else 0
        print(f'Average tick interval: {avg_tick*1000:.2f}ms')
        print(f'Expected tick interval: {1000/fps:.2f}ms (at {fps}fps)')
        print(f'Actual tick rate: {1/avg_tick:.2f} Hz')
else:
    print('NO FRAMES DISPLAYED!')

# === SAVE LOG ===
with open('speed_analysis.log', 'w') as f:
    f.write('Frame Index | Wall Clock | Playhead | Frames Shown | Queue | Rate\\n')
    for i, entry in enumerate(frame_log):
        f.write(f'{i:5d} | {entry["wall_clock"]:.6f} | {entry["playhead"]:.3f} | '
                f'{entry["frames_shown"]:5d} | {entry["queue_size"]:2d} | {entry["rate"]}\\n')

print(f'\\nFull log saved to speed_analysis.log')

screen.close()
controller.stop()
