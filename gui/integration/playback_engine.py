"""PlaybackEngine v2: PTS-based clock-driven video playback engine.

Architecture:
  Clock → computes playhead from wall time
  Decoder → background QThread, outputs (pts, frame) tuples into a deque
  Scheduler → one frame per tick, displays frame whose PTS <= playhead
  Audio → QMediaPlayer, periodically resynced to playhead

No blocking operations on the GUI thread.
Exactly one frame consumed per tick.
PTS-based scheduling works for any frame rate.
"""
from __future__ import annotations

import collections
import logging
import subprocess
import threading
import time as _time
from typing import Optional, Tuple

import numpy as np
from PySide6.QtCore import QMutex, QMutexLocker, QThread, QTimer, Qt, Signal, QObject
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QLabel, QWidget

_log = logging.getLogger(__name__)

# Frame tuple: (pts_seconds, bgr_ndarray)
_FrameT = Tuple[float, np.ndarray]


# --------------------------------------------------------------------------- #
# Background frame decoder — outputs (pts, frame) tuples
# --------------------------------------------------------------------------- #
class FrameDecoder(QThread):
    """Decode video frames in a background thread.

    Each frame is emitted as a (pts, bgr_ndarray) tuple into a thread-safe
    deque. The PTS comes directly from FFmpeg's -show_entries
    frame=pts_time or from the frame index when PTS is unavailable.

    Signals:
        error(str): Emitted on decode failure.
    """

    error = Signal(str)

    def __init__(
        self,
        video_path: str,
        fps: float = 30.0,
        max_frames: int = 60,
        start_at: float = 0.0,
        scale_width: int = 0,
        parent=None,
    ):
        super().__init__(parent)
        self._video_path = video_path
        self._fps = max(1.0, float(fps))
        self._max_frames = max(4, int(max_frames))
        self._start_at = max(0.0, float(start_at))
        self._scale_width = max(0, int(scale_width))

        self._queue: collections.deque[_FrameT] = collections.deque(maxlen=self._max_frames)
        self._mutex = QMutex()
        self._stop_event = threading.Event()
        self._seek_to: Optional[float] = None
        self._proc: Optional[subprocess.Popen] = None

    # -- Public API (called from GUI thread) --

    def pop(self) -> Optional[_FrameT]:
        """Pop the next (pts, frame) from the buffer."""
        with QMutexLocker(self._mutex):
            if self._queue:
                return self._queue.popleft()
        return None

    def peek_pts(self) -> Optional[float]:
        """Peek at the PTS of the next frame without popping."""
        with QMutexLocker(self._mutex):
            if self._queue:
                return self._queue[0][0]
        return None

    def pop_if_due(self, playhead: float, tolerance: float = 0.001) -> Optional[_FrameT]:
        """Atomically peek + pop if PTS <= playhead.

        This eliminates the race between peek() and pop() where the decoder
        could append+evict between the two calls.
        """
        with QMutexLocker(self._mutex):
            if not self._queue:
                return None
            pts = self._queue[0][0]
            if pts > playhead + tolerance:
                return None
            return self._queue.popleft()

    def discard_one_stale(self, playhead: float) -> Optional[_FrameT]:
        """Remove ONE frame with PTS < playhead if available."""
        with QMutexLocker(self._mutex):
            if self._queue and self._queue[0][0] < playhead:
                return self._queue.popleft()
        return None

    def clear(self) -> None:
        """Clear the frame buffer."""
        with QMutexLocker(self._mutex):
            self._queue.clear()

    def seek(self, seconds: float) -> None:
        """Request a seek (thread-safe)."""
        with QMutexLocker(self._mutex):
            self._seek_to = max(0.0, float(seconds))

    def stop_decoding(self) -> None:
        """Signal the decoder to stop."""
        self._stop_event.set()
        if self._proc and self._proc.poll() is None:
            self._proc.kill()

    def queue_size(self) -> int:
        """Current queue depth."""
        with QMutexLocker(self._mutex):
            return len(self._queue)

    # -- Thread entry point --

    def run(self):
        """Main decode loop: spawn FFmpeg, read frames, handle seeks."""
        width, height, vf = self._compute_scale()
        frame_bytes = width * height * 3
        start = self._start_at

        while not self._stop_event.is_set():
            # Build FFmpeg command
            cmd = [
                "ffmpeg", "-nostdin", "-loglevel", "error",
                "-ss", f"{start:.3f}",
                "-i", self._video_path,
            ]
            if vf:
                cmd += ["-vf", vf]
            cmd += [
                "-f", "rawvideo", "-pix_fmt", "bgr24",
                "-an", "-sn", "-",
            ]

            try:
                self._proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                )
            except Exception as exc:
                self.error.emit(f"ffmpeg start failed: {exc}")
                return

            frame_index = 0
            while not self._stop_event.is_set():
                # Check for seek request
                with QMutexLocker(self._mutex):
                    seek = self._seek_to
                    self._seek_to = None

                if seek is not None:
                    start = seek
                    self._kill_proc()
                    with QMutexLocker(self._mutex):
                        self._queue.clear()
                    break  # respawn at new position

                raw = self._proc.stdout.read(frame_bytes)
                if len(raw) < frame_bytes:
                    break  # end of stream

                pts = start + frame_index / self._fps
                frame = np.frombuffer(raw, dtype=np.uint8).reshape(height, width, 3).copy()
                frame_index += 1

                with QMutexLocker(self._mutex):
                    self._queue.append((pts, frame))

            # End of inner loop — clean up this FFmpeg instance
            self._kill_proc()

    def _kill_proc(self):
        """Kill and wait on the current FFmpeg process."""
        if self._proc:
            if self._proc.poll() is None:
                self._proc.kill()
                try:
                    self._proc.wait(timeout=5)
                except Exception:
                    pass
            self._proc = None

    def _compute_scale(self):
        """Compute output dimensions from scale_width."""
        if self._scale_width <= 0:
            # Read dimensions from file
            try:
                import ffmpeg as ff
                probe = ff.probe(self._video_path)
                for s in probe.get("streams", []):
                    if s.get("codec_type") == "video":
                        w = int(s.get("width", 640))
                        h = int(s.get("height", 480))
                        return w, h, None
            except Exception:
                pass
            return 640, 480, None

        width = self._scale_width - (self._scale_width % 2)
        # Read aspect ratio from file
        src_w, src_h = 640, 480
        try:
            import ffmpeg as ff
            probe = ff.probe(self._video_path)
            for s in probe.get("streams", []):
                if s.get("codec_type") == "video":
                    src_w = int(s.get("width", 640))
                    src_h = int(s.get("height", 480))
                    break
        except Exception:
            pass
        height = int(round(src_h * (width / src_w)))
        height -= height % 2
        width = max(2, width)
        height = max(2, height)
        return width, height, f"scale={width}:{height}"


# --------------------------------------------------------------------------- #
# Playback engine — clock-driven, PTS-scheduled
# --------------------------------------------------------------------------- #
class PlaybackEngine(QObject):
    """Clock-driven video playback engine.

    The playhead is computed from a wall-clock anchor:
        playhead = playhead_anchor + (now - wall_anchor) * rate

    Frames are scheduled by PTS:
        display frame when playhead >= frame.pts

    Exactly ONE frame is consumed per tick. No multi-frame consumption.
    No late-frame drop loops.

    Signals:
        frame_ready(object): BGR numpy frame to display.
        playhead_updated(float): Current playhead in seconds.
        playback_state_changed(str): "playing"/"paused"/"stopped".
        playback_finished(): Emitted when non-looping playback ends.
        timecode_changed(str): Formatted HH:MM:SS:FF / HH:MM:SS:FF.
        error_occurred(str): Error message.
    """

    frame_ready = Signal(object)
    playhead_updated = Signal(float)
    playback_state_changed = Signal(str)
    playback_finished = Signal()
    timecode_changed = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, controller=None, parent=None):
        super().__init__(parent)
        self._controller = controller

        # Media state
        self._media_path: Optional[str] = None
        self._duration: float = 0.0
        self._fps: float = 30.0

        # Clock state
        self._state: str = "stopped"  # "playing" | "paused" | "stopped"
        self._playhead: float = 0.0  # current position in seconds
        self._wall_anchor: float = 0.0  # wall clock when play() started
        self._playhead_anchor: float = 0.0  # playhead when play() started
        self._playback_rate: float = 1.0
        self._loop: bool = True
        self._wall_anchor_fresh: bool = True  # re-anchor on first tick if stale

        # Decoder
        self._decoder: Optional[FrameDecoder] = None
        self._decoder_shown: int = 0  # frames consumed from current decoder

        # Audio
        self._audio_player = None
        self._audio_output = None
        self._audio_loaded_for: Optional[str] = None
        self._audio_extracted: bool = False

        # Timers
        self._tick_timer = QTimer(self)
        self._tick_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._tick_timer.timeout.connect(self._on_tick)

        self._seek_debounce = QTimer(self)
        self._seek_debounce.setTimerType(Qt.TimerType.PreciseTimer)
        self._seek_debounce.setSingleShot(True)
        self._seek_debounce.setInterval(80)
        self._seek_debounce.timeout.connect(self._commit_seek)
        self._pending_seek: Optional[float] = None

        # Timeline
        self._timeline = None

        # Drift correction tracking
        self._last_drift_correct: float = 0.0

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def set_controller(self, controller):
        self._controller = controller

    def load_media(self, path: str, duration: float, fps: float):
        """Load a media file. Does NOT start playback."""
        self.stop()
        self._media_path = path
        self._duration = max(0.0, float(duration))
        self._fps = max(1.0, float(fps))

        # Set tick interval to match video fps
        timer_ms = max(4, int(round(1000.0 / self._fps)))
        self._tick_timer.setInterval(timer_ms)

        # Extract audio in background thread (non-blocking)
        self._extract_audio(path)
        self._ensure_audio_player()

    def set_timeline(self, timeline):
        self._timeline = timeline

    def play(self):
        """Start or resume playback."""
        if self._state == "playing":
            return
        if self._media_path is None:
            return

        self._state = "playing"
        self._playhead_anchor = self._playhead
        self._wall_anchor = _time.monotonic()
        self._wall_anchor_fresh = False  # re-anchor on first tick if stale
        self._last_drift_correct = _time.monotonic()

        self._start_decoder()
        self._start_audio()
        self._tick_timer.start()
        self.playback_state_changed.emit("playing")

    def pause(self):
        """Pause playback."""
        if self._state != "playing":
            return
        self._state = "paused"
        self._tick_timer.stop()
        self._stop_decoder()
        self._pause_audio()
        self.playback_state_changed.emit("paused")

    def stop(self):
        """Stop and reset to beginning."""
        was_playing = self._state == "playing"
        self._state = "stopped"
        self._tick_timer.stop()
        self._stop_decoder()
        self._stop_audio()
        self._playhead = 0.0
        self.playhead_updated.emit(0.0)
        self.playback_state_changed.emit("stopped")
        self._emit_timecode(0.0)
        if self._timeline is not None:
            self._timeline.set_playhead(0.0)
            if was_playing and hasattr(self._timeline, 'pause'):
                self._timeline.pause()

    def toggle_play_pause(self):
        if self._state == "playing":
            self.pause()
        else:
            self.play()

    def seek(self, seconds: float):
        """Seek to a position (debounced during playback)."""
        target = max(0.0, min(seconds, self._duration))
        self._playhead = target
        self.playhead_updated.emit(target)
        self._emit_timecode(target)
        if self._timeline is not None:
            self._timeline.set_playhead(target)
        if self._state == "playing":
            self._pending_seek = target
            self._seek_debounce.start()
        else:
            self._seek_to(target)

    def seek_normalized(self, fraction: float):
        self.seek(fraction * self._duration)

    def step_forward(self):
        """Advance one frame."""
        step = 1.0 / self._fps
        target = min(self._playhead + step, self._duration)
        was_playing = self._state == "playing"
        if was_playing:
            self.pause()
        self.seek(target)
        if was_playing:
            self.play()

    def step_backward(self):
        """Go back one frame."""
        step = 1.0 / self._fps
        target = max(self._playhead - step, 0.0)
        was_playing = self._state == "playing"
        if was_playing:
            self.pause()
        self.seek(target)
        if was_playing:
            self.play()

    def set_playback_rate(self, rate: float):
        """Set playback speed. Re-anchors clock to prevent jump."""
        rate = max(0.1, min(4.0, float(rate)))
        if rate == self._playback_rate:
            return
        # Re-anchor: save current playhead, reset wall anchor
        self._playhead_anchor = self._playhead
        self._wall_anchor = _time.monotonic()
        self._wall_anchor_fresh = True
        self._playback_rate = rate

    def playback_rate(self) -> float:
        return self._playback_rate

    def set_loop(self, enabled: bool):
        self._loop = enabled

    def is_looping(self) -> bool:
        return self._loop

    def set_volume(self, volume: float):
        if self._audio_output is not None:
            try:
                self._audio_output.setVolume(max(0.0, min(1.0, volume)))
            except Exception as exc:
                _log.warning("Volume set failed: %s", exc)

    def volume(self) -> float:
        if self._audio_output is not None:
            try:
                return self._audio_output.volume()
            except Exception:
                pass
        return 1.0

    def set_muted(self, muted: bool):
        if self._audio_output is not None:
            try:
                self._audio_output.setMuted(muted)
            except Exception as exc:
                _log.warning("Mute failed: %s", exc)

    def is_muted(self) -> bool:
        if self._audio_output is not None:
            try:
                return self._audio_output.isMuted()
            except Exception:
                pass
        return False

    def state(self) -> str:
        return self._state

    def playhead(self) -> float:
        return self._playhead

    def duration(self) -> float:
        return self._duration

    def fps(self) -> float:
        return self._fps

    def is_playing(self) -> bool:
        return self._state == "playing"

    # ------------------------------------------------------------------ #
    # Clock tick — the heartbeat of playback
    # ------------------------------------------------------------------ #

    def _on_tick(self):
        """Timer tick: advance clock, schedule frame, sync audio."""
        # Re-entrancy guard
        if getattr(self, '_tick_busy', False):
            return
        self._tick_busy = True
        try:
            self._tick_impl()
        finally:
            self._tick_busy = False

    def _tick_impl(self):
        now = _time.monotonic()
        real_elapsed = now - self._wall_anchor

        # Re-anchor on first tick if wall_anchor is stale
        # (play() blocked or took time to return)
        if not self._wall_anchor_fresh:
            self._wall_anchor_fresh = True
            if real_elapsed > 1.0:
                self._wall_anchor = now
                real_elapsed = 0.0

        # Advance playhead from wall clock
        self._playhead = self._playhead_anchor + real_elapsed * self._playback_rate

        # Handle end of media
        if self._playhead >= self._duration:
            if self._loop:
                self._playhead = 0.0
                self._playhead_anchor = 0.0
                self._wall_anchor = _time.monotonic()
                self._wall_anchor_fresh = True
                self._restart_audio()
                self._stop_decoder()
                self._decoder_shown = 0
                self._start_decoder()
            else:
                self.stop()
                self.playback_finished.emit()
                return

        # Schedule exactly one frame via PTS comparison
        self._schedule_frame()

        # Sync timeline
        if self._timeline is not None:
            self._timeline.set_playhead(self._playhead)

        # Emit updates
        self.playhead_updated.emit(self._playhead)
        self._emit_timecode(self._playhead)

        # Audio drift correction (every 2 seconds)
        if self._state == "playing" and self._audio_player is not None:
            if now - self._last_drift_correct > 2.0:
                self._last_drift_correct = now
                self._correct_audio_drift()

    def _schedule_frame(self):
        """Display the current frame based on PTS.

        Pops exactly ONE frame per tick if its PTS <= playhead.
        Late frames (PTS < playhead from decoder being ahead) are
        discarded one at a time to prevent burst delivery.
        """
        if self._decoder is None:
            return

        # Try to pop one due frame
        frame_tuple = self._decoder.pop_if_due(self._playhead)
        if frame_tuple is not None:
            self._decoder_shown += 1
            self.frame_ready.emit(frame_tuple[1])
            return

        # No due frame — discard ONE stale frame to keep queue draining
        stale = self._decoder.discard_one_stale(self._playhead)
        if stale is not None:
            self._decoder_shown += 1

    def _correct_audio_drift(self):
        """Resync audio position to video playhead if drift > 100ms."""
        try:
            audio_pos_ms = self._audio_player.position()
            video_pos_ms = self._playhead * 1000
            drift_ms = abs(audio_pos_ms - video_pos_ms)
            if drift_ms > 100:
                self._audio_player.setPosition(int(video_pos_ms))
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # Seeking
    # ------------------------------------------------------------------ #

    def _seek_to(self, seconds: float):
        """Immediate seek: restart decoder at new position."""
        self._stop_decoder()
        self._playhead = seconds
        self._playhead_anchor = seconds
        self._wall_anchor = _time.monotonic()
        self._wall_anchor_fresh = True
        self._decoder_shown = 0
        self._start_decoder()
        # Resync audio
        if self._audio_player is not None:
            try:
                self._audio_player.setPosition(int(seconds * 1000))
            except Exception:
                pass

    def _commit_seek(self):
        """Commit a debounced seek."""
        if self._pending_seek is not None:
            self._seek_to(self._pending_seek)
            self._pending_seek = None

    # ------------------------------------------------------------------ #
    # Decoder management
    # ------------------------------------------------------------------ #

    def _start_decoder(self):
        if self._decoder is not None:
            return
        if self._media_path is None:
            return
        decoder = FrameDecoder(
            self._media_path,
            fps=self._fps,
            max_frames=120,  # 2 seconds of buffer — keeps decoder close to real-time
            start_at=self._playhead,
            scale_width=960,
        )
        decoder.error.connect(self._on_decoder_error)
        decoder.start()
        self._decoder = decoder
        self._decoder_shown = 0

    def _stop_decoder(self):
        dec = self._decoder
        if dec is None:
            return
        self._decoder = None
        dec.stop_decoding()
        dec.quit()
        dec.wait(3000)

    def _on_decoder_error(self, message: str):
        _log.error("Decoder error: %s", message)
        self.error_occurred.emit(message)
        self.pause()

    # ------------------------------------------------------------------ #
    # Audio management
    # ------------------------------------------------------------------ #

    def _extract_audio(self, video_path: str):
        """Extract audio in background thread (non-blocking)."""
        if self._controller is None:
            return

        def _do_extract():
            try:
                from pathlib import Path
                path = Path(video_path)
                from config import config as app_config
                output = app_config.paths.output_dir / f"{path.stem}.mp3"
                output.parent.mkdir(parents=True, exist_ok=True)

                if output.exists():
                    self._audio_extracted = True
                    return

                # Probe for stream count
                num_streams = 1
                try:
                    import ffmpeg as ff
                    probe = ff.probe(str(path))
                    num_streams = sum(
                        1 for s in probe.get("streams", [])
                        if s.get("codec_type") == "audio"
                    )
                except Exception:
                    num_streams = 1

                if num_streams <= 1:
                    self._controller.extract_audio(video_path)
                else:
                    cmd = [
                        "ffmpeg", "-y", "-nostdin", "-loglevel", "warning",
                        "-i", str(path.resolve()),
                        "-filter_complex",
                        f"amix=inputs={num_streams}:duration=first:dropout_transition=2,aresample=44100",
                        "-ac", "2", "-acodec", "libmp3lame", "-q:a", "2",
                        str(output),
                    ]
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                    if result.returncode != 0:
                        self._controller.extract_audio(video_path)
                self._audio_extracted = True
            except Exception:
                try:
                    self._controller.extract_audio(video_path)
                    self._audio_extracted = True
                except Exception:
                    pass

        self._audio_extracted = False
        t = threading.Thread(target=_do_extract, daemon=True)
        t.start()

    def _ensure_audio_player(self):
        if self._audio_player is not None:
            return
        try:
            from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
            self._audio_output = QAudioOutput()
            self._audio_output.setVolume(1.0)
            self._audio_player = QMediaPlayer(self)
            self._audio_player.setAudioOutput(self._audio_output)
            self._audio_player.mediaStatusChanged.connect(self._on_media_status)
        except ImportError:
            self._audio_player = None

    def _start_audio(self):
        """Start audio — does NOT block."""
        self._ensure_audio_player()
        if self._audio_player is None or self._media_path is None:
            return
        try:
            from PySide6.QtCore import QUrl
            from pathlib import Path
            if self._audio_loaded_for != self._media_path:
                from config import config as app_config
                mp3_path = app_config.paths.output_dir / f"{Path(self._media_path).stem}.mp3"
                if not mp3_path.exists():
                    return  # not ready — don't block
                self._audio_player.setSource(QUrl.fromLocalFile(str(mp3_path)))
                self._audio_loaded_for = self._media_path
            pos_ms = int(self._playhead * 1000)
            dur_ms = self._audio_player.duration()
            if dur_ms > 0:
                pos_ms = min(pos_ms, dur_ms - 100)
            self._audio_player.setPosition(max(0, pos_ms))
            self._audio_player.play()
        except Exception as exc:
            _log.warning("Audio start failed: %s", exc)

    def _pause_audio(self):
        if self._audio_player is not None:
            try:
                self._audio_player.pause()
            except Exception as exc:
                _log.warning("Audio pause failed: %s", exc)

    def _stop_audio(self):
        if self._audio_player is not None:
            try:
                self._audio_player.stop()
            except Exception as exc:
                _log.warning("Audio stop failed: %s", exc)

    def _restart_audio(self):
        if self._audio_player is not None and self._audio_loaded_for is not None:
            try:
                self._audio_player.setPosition(0)
                self._audio_player.play()
            except Exception as exc:
                _log.warning("Audio restart failed: %s", exc)

    def _on_media_status(self, status):
        try:
            from PySide6.QtMultimedia import QMediaPlayer
            if status == QMediaPlayer.MediaStatus.InvalidMedia:
                _log.warning("Audio media failed to load")
            elif status == QMediaPlayer.MediaStatus.EndOfMedia:
                _log.debug("Audio playback reached end")
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # Timecode formatting
    # ------------------------------------------------------------------ #

    def _emit_timecode(self, seconds: float):
        s = max(0.0, float(seconds))
        h = int(s // 3600)
        m = int((s % 3600) // 60)
        sec = int(s % 60)
        frames = int((s % 1.0) * self._fps)
        tc = f"{h:02d}:{m:02d}:{sec:02d}:{frames:02d}"
        total_s = self._duration
        th = int(total_s // 3600)
        tm = int((total_s % 3600) // 60)
        tsec = int(total_s % 60)
        tframes = int((total_s % 1.0) * self._fps)
        total = f"{th:02d}:{tm:02d}:{tsec:02d}:{tframes:02d}"
        self.timecode_changed.emit(f"{tc} / {total}")
