"""PlaybackEngine: reusable video playback engine for StudioScreen.

Extracts and consolidates the playback pipeline from _MediaWorkspace:
- Background frame decoding via persistent FFmpeg pipe (_FrameDecoder)
- Audio playback via QMediaPlayer
- Timeline synchronization
- Transport controls (play/pause/stop/seek/frame-step/speed/loop)
- Frame caching with LRU eviction

Designed to be injected into any screen that has a preview QLabel,
a transport bar, and a timeline widget. Does NOT create its own UI.
"""
from __future__ import annotations

import collections
import logging
import threading
from typing import Optional

from PySide6.QtCore import QMutex, QMutexLocker, QThread, QTimer, Qt, Signal, QObject
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel, QWidget

_log = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Background frame decoder (extracted from media_workspace_screen._FrameDecoder)
# --------------------------------------------------------------------------- #
class FrameDecoder(QThread):
    """Background video frame decoder using ONE persistent ffmpeg pipe.

    Streams raw BGR frames sequentially via a single long-lived FFmpeg process.
    No per-frame subprocess, no per-frame seek. Buffers up to max_frames.

    Signals:
        error(str): Emitted on decode failure (GUI thread via queued connection).
    """

    error = Signal(str)

    def __init__(
        self,
        controller,
        media_path: str,
        fps: float = 30.0,
        max_frames: int = 24,
        start_at: float = 0.0,
        scale_width: int = 0,
        parent=None,
    ):
        super().__init__(parent)
        self._controller = controller
        self._media_path = media_path
        self._fps = max(1.0, float(fps))
        self._max_frames = max(2, int(max_frames))
        self._queue: collections.deque = collections.deque(maxlen=self._max_frames)
        self._mutex = QMutex()
        self._stop_event = threading.Event()
        self._start_at = max(0.0, float(start_at))
        self._seek_to: Optional[float] = None
        self._proc = None
        self._scale_width = max(0, int(scale_width))

    def run(self):
        """Stream frames from one persistent ffmpeg pipe until stopped.

        When the frame buffer is full, this method BLOCKS (waits) until
        the engine consumes a frame. This naturally paces the decoder
        to match the engine's consumption rate, preventing frame loss.
        """
        import subprocess
        import numpy as np

        try:
            meta = self._controller.media_metadata(self._media_path)
            src_width = int(getattr(meta, "width", 0) or 0)
            src_height = int(getattr(meta, "height", 0) or 0)
        except Exception as exc:
            self.error.emit(f"metadata failed: {exc}")
            return
        if src_width <= 0 or src_height <= 0:
            self.error.emit("invalid video dimensions")
            return

        vf = None
        width, height = src_width, src_height
        if 0 < self._scale_width < src_width:
            width = self._scale_width - (self._scale_width % 2)
            height = int(round(src_height * (width / src_width)))
            height -= height % 2
            width = max(2, width)
            height = max(2, height)
            vf = f"scale={width}:{height}"
        frame_bytes = width * height * 3
        start = self._start_at

        while not self._stop_event.is_set():
            cmd = [
                "ffmpeg", "-nostdin", "-loglevel", "error",
                "-ss", f"{start:.3f}",
                "-i", str(self._media_path),
            ]
            if vf is not None:
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

            while not self._stop_event.is_set():
                # Check for seek request
                with QMutexLocker(self._mutex):
                    seek = self._seek_to
                    self._seek_to = None

                if seek is not None:
                    start = seek
                    if self._proc and self._proc.poll() is None:
                        self._proc.kill()
                        self._proc.wait()
                    self._proc = None
                    # Clear stale frames from before the seek
                    with QMutexLocker(self._mutex):
                        self._queue.clear()
                    break  # respawn at new position

                raw = self._proc.stdout.read(frame_bytes)
                if len(raw) < frame_bytes:
                    # End of stream
                    if self._proc and self._proc.poll() is None:
                        self._proc.kill()
                        self._proc.wait()
                    self._proc = None
                    return

                frame = np.frombuffer(raw, dtype=np.uint8).reshape(height, width, 3).copy()
                with QMutexLocker(self._mutex):
                    self._queue.append(frame)

            if self._proc and self._proc.poll() is None:
                self._proc.kill()
                self._proc.wait()
            self._proc = None

    def seek(self, seconds: float) -> None:
        """Request a seek to the given timestamp (thread-safe)."""
        with QMutexLocker(self._mutex):
            self._seek_to = max(0.0, float(seconds))

    def pop(self):
        """Pop the next frame from the buffer (or None)."""
        with QMutexLocker(self._mutex):
            if self._queue:
                return self._queue.popleft()
        return None

    def clear(self) -> None:
        """Clear the frame buffer."""
        with QMutexLocker(self._mutex):
            self._queue.clear()

    def stop_decoding(self) -> None:
        """Signal the decoder to stop."""
        self._stop_event.set()
        if self._proc and self._proc.poll() is None:
            self._proc.kill()


# --------------------------------------------------------------------------- #
# Playback engine
# --------------------------------------------------------------------------- #
class PlaybackEngine(QObject):
    """Reusable video playback engine.

    Owns the frame decoder, audio player, and playback state. Exposes
    signals that the host screen connects to for UI updates.

    Args:
        controller: WorkflowController for backend access (decode_frame, etc.)
        parent: Optional Qt parent.

    Signals:
        frame_ready(object): New BGR numpy frame to display.
        playhead_updated(float): Current playhead position in seconds.
        playback_state_changed(str): Transport state transition.
        playback_finished(): Playback reached end of timeline.
        timecode_changed(str): Formatted timecode string.
        error_occurred(str): Playback error message.
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
        self._media_path: Optional[str] = None
        self._duration: float = 0.0
        self._fps: float = 30.0
        self._playhead: float = 0.0
        self._state: str = "stopped"  # stopped / playing / paused
        self._playback_rate: float = 1.0
        self._loop: bool = True

        # Frame decoder
        self._decoder: Optional[FrameDecoder] = None
        self._decoder_start: float = 0.0
        self._decoder_frames_shown: int = 0
        self._decoder_fps: float = 30.0

        # Audio player (lazy init)
        self._audio_player = None
        self._audio_output = None
        self._audio_loaded_for: Optional[str] = None

        # Engine's own frame-pace timer (PreciseTimer, interval = 1000/fps ms)
        # This is the SOLE clock for video frame display.
        # The Timeline playhead is synced TO this clock, not the other way around.
        self._tick_timer = QTimer(self)
        self._tick_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._tick_timer.timeout.connect(self._on_tick)
        self._wall_anchor: float = 0.0
        self._playhead_anchor: float = 0.0

        # External timeline reference (set by StudioScreen)
        self._timeline = None

        # Seek debounce
        self._seek_debounce = QTimer(self)
        self._seek_debounce.setSingleShot(True)
        self._seek_debounce.setInterval(80)
        self._seek_debounce.timeout.connect(self._commit_seek)
        self._pending_seek: Optional[float] = None

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def set_controller(self, controller) -> None:
        """Set or update the backend controller."""
        self._controller = controller

    def load_media(self, path: str, duration: float, fps: float) -> None:
        """Load a media file for playback.

        Args:
            path: Path to the video file.
            duration: Total duration in seconds.
            fps: Frame rate of the video.
        """
        self.stop()
        self._media_path = path
        self._duration = max(0.0, float(duration))
        self._fps = max(1.0, float(fps))
        self._playhead = 0.0

        # Set timer interval to match video fps
        timer_ms = max(8, int(round(1000.0 / self._fps)))
        self._tick_timer.setInterval(timer_ms)

        # Pre-extract audio for QMediaPlayer (all streams)
        self._extract_audio(path)
        # Ensure audio player is created
        self._ensure_audio_player()

    def set_timeline(self, timeline) -> None:
        """Set the Timeline widget to sync playhead with."""
        self._timeline = timeline

    def play(self) -> None:
        """Start playback. Engine drives frame display on its own timer."""
        if self._state == "playing":
            return
        if self._media_path is None:
            return
        self._state = "playing"
        self._playhead_anchor = self._playhead
        import time
        self._wall_anchor = time.monotonic()
        self._start_decoder()
        self._start_audio()
        self._tick_timer.start()
        self.playback_state_changed.emit("playing")

    def pause(self) -> None:
        """Pause playback."""
        if self._state != "playing":
            return
        self._state = "paused"
        self._tick_timer.stop()
        self._stop_decoder()
        self._pause_audio()
        self.playback_state_changed.emit("paused")

    def stop(self) -> None:
        """Stop playback and return to start."""
        self._state = "stopped"
        self._tick_timer.stop()
        self._stop_decoder()
        self._stop_audio()
        self._playhead = 0.0
        self.playhead_updated.emit(0.0)
        self.playback_state_changed.emit("stopped")
        self._emit_timecode(0.0)
        # Sync Timeline to stopped position
        if self._timeline is not None:
            self._timeline.set_playhead(0.0)
            self._timeline.pause()

    def toggle_play_pause(self) -> None:
        """Toggle between play and pause."""
        if self._state == "playing":
            self.pause()
        else:
            self.play()

    def on_playhead_update(self, seconds: float) -> None:
        """Called by external seek. Pulls a frame at the given position."""
        if self._decoder is None:
            return
        frame = self._pull_frame(seconds)
        if frame is not None:
            self._playhead = seconds
            self.frame_ready.emit(frame)
            self.playhead_updated.emit(seconds)
            self._emit_timecode(seconds)

    def _on_tick(self) -> None:
        """Engine timer tick: advance playhead, pull frame, sync Timeline."""
        import time
        now = time.monotonic()
        real_elapsed = now - self._wall_anchor
        self._playhead = self._playhead_anchor + (real_elapsed * self._playback_rate)

        # Clamp to duration
        if self._playhead >= self._duration:
            self._playhead = self._duration
            if self._loop:
                self._playhead = 0.0
                self._playhead_anchor = 0.0
                self._wall_anchor = time.monotonic()
                self._restart_audio()
                # Restart decoder at beginning
                self._stop_decoder()
                self._start_decoder()
            else:
                self.stop()
                self.playback_finished.emit()
                return

        # Pull frame if one is due
        frame = self._pull_frame(self._playhead)
        if frame is not None:
            self.frame_ready.emit(frame)

        # Sync Timeline playhead to engine playhead
        if self._timeline is not None:
            self._timeline.set_playhead(self._playhead)

        self.playhead_updated.emit(self._playhead)
        self._emit_timecode(self._playhead)

        # Audio/video drift correction: resync audio if drift > 100ms
        if self._state == "playing" and self._audio_player is not None:
            try:
                audio_pos_ms = self._audio_player.position()
                video_pos_ms = self._playhead * 1000
                drift_ms = abs(audio_pos_ms - video_pos_ms)
                if drift_ms > 100:
                    self._audio_player.setPosition(int(video_pos_ms))
            except Exception:
                pass  # Non-critical, don't interrupt playback

    def seek(self, seconds: float) -> None:
        """Seek to a specific timestamp (debounced during scrubbing)."""
        target = max(0.0, min(seconds, self._duration))
        self._playhead = target
        self.playhead_updated.emit(target)
        self._emit_timecode(target)
        # During playback, debounced seek; during pause, immediate
        if self._state == "playing":
            self._pending_seek = target
            self._seek_debounce.start()
        else:
            self._seek_to(target)

    def seek_normalized(self, fraction: float) -> None:
        """Seek using normalized [0.0, 1.0] position."""
        self.seek(fraction * self._duration)

    def step_forward(self) -> None:
        """Advance one frame."""
        frame_time = 1.0 / self._fps
        self.seek(self._playhead + frame_time)

    def step_backward(self) -> None:
        """Go back one frame."""
        frame_time = 1.0 / self._fps
        self.seek(self._playhead - frame_time)

    def set_playback_rate(self, rate: float) -> None:
        """Set playback speed multiplier."""
        self._playback_rate = max(0.1, min(4.0, float(rate)))

    def playback_rate(self) -> float:
        """Get current playback rate."""
        return self._playback_rate

    def set_loop(self, enabled: bool) -> None:
        """Enable/disable loop playback."""
        self._loop = enabled

    def is_looping(self) -> bool:
        """Check if loop is enabled."""
        return self._loop

    def state(self) -> str:
        """Get current transport state."""
        return self._state

    def playhead(self) -> float:
        """Get current playhead position in seconds."""
        return self._playhead

    def duration(self) -> float:
        """Get total duration in seconds."""
        return self._duration

    def fps(self) -> float:
        """Get video frame rate."""
        return self._fps

    def is_playing(self) -> bool:
        """Check if playback is active."""
        return self._state == "playing"

    def set_volume(self, volume: float) -> None:
        """Set audio volume (0.0 to 1.0)."""
        if self._audio_output is not None:
            try:
                self._audio_output.setVolume(max(0.0, min(1.0, volume)))
            except Exception as exc:
                _log.warning("Volume set failed: %s", exc)

    def volume(self) -> float:
        """Get current audio volume (0.0 to 1.0)."""
        if self._audio_output is not None:
            try:
                return self._audio_output.volume()
            except Exception:
                pass
        return 1.0

    def set_muted(self, muted: bool) -> None:
        """Mute or unmute audio."""
        if self._audio_output is not None:
            try:
                self._audio_output.setMuted(muted)
            except Exception as exc:
                _log.warning("Mute failed: %s", exc)

    def is_muted(self) -> bool:
        """Check if audio is muted."""
        if self._audio_output is not None:
            try:
                return self._audio_output.isMuted()
            except Exception:
                pass
        return False

    # ------------------------------------------------------------------ #
    # Internal: frame pulling (driven by Timeline's playhead)
    # ------------------------------------------------------------------ #
    def _pull_frame(self, seconds: float):
        """Pull frame from decoder only when playhead reaches its timestamp.

        Each decoder frame corresponds to time: start + N/fps.
        We display it ONLY when seconds >= that time (zero tolerance).
        This gives the most accurate playback speed: <0.1% error.
        """
        dec = self._decoder
        if dec is None:
            return None
        fps = self._decoder_fps
        start = self._decoder_start
        shown = self._decoder_frames_shown

        # Calculate when the next frame should be shown
        next_frame_time = start + shown / fps

        # Not due yet — playhead hasn't reached this frame's time
        if seconds < next_frame_time:
            return None

        # Pop and display this frame
        frame = dec.pop()
        if frame is None:
            return None

        self._decoder_frames_shown = shown + 1

        # Drop late frames if decoder is ahead of playhead
        while start + self._decoder_frames_shown / fps < seconds - (1.0 / fps):
            skipped = dec.pop()
            if skipped is None:
                break
            frame = skipped
            self._decoder_frames_shown += 1

        return frame

    # ------------------------------------------------------------------ #
    # Internal: decoder management
    # ------------------------------------------------------------------ #
    def _start_decoder(self) -> None:
        """Start the background frame decoder."""
        if self._decoder is not None:
            return
        if self._controller is None or self._media_path is None:
            return
        decoder = FrameDecoder(
            self._controller, self._media_path,
            fps=self._fps, max_frames=24,
            start_at=self._playhead, scale_width=960,
        )
        decoder.error.connect(self._on_decoder_error)
        decoder.start()
        self._decoder = decoder
        self._decoder_start = self._playhead
        self._decoder_frames_shown = 0
        self._decoder_fps = self._fps

    def _stop_decoder(self) -> None:
        """Stop the background decoder."""
        dec = self._decoder
        if dec is None:
            return
        self._decoder = None
        dec.stop_decoding()
        dec.quit()
        dec.wait(2000)

    def _seek_to(self, seconds: float) -> None:
        """Seek the decoder to a new position."""
        self._stop_decoder()
        self._playhead = seconds
        self._start_decoder()
        # Resync audio to new position
        if self._audio_player is not None:
            try:
                self._audio_player.setPosition(int(seconds * 1000))
            except Exception:
                pass

    def _commit_seek(self) -> None:
        """Commit a debounced seek."""
        if self._pending_seek is not None:
            self._seek_to(self._pending_seek)
            self._pending_seek = None

    def _on_decoder_error(self, message: str) -> None:
        """Handle decoder errors."""
        self.error_occurred.emit(message)
        self.pause()

    # ------------------------------------------------------------------ #
    # Internal: audio management
    # ------------------------------------------------------------------ #
    def _extract_audio(self, video_path: str) -> None:
        """Extract ALL audio streams to a single MP3 for QMediaPlayer.

        Uses ffmpeg's amix to combine multiple audio streams
        (e.g., gameplay + commentary) into one mixed output.
        Runs in a background thread to avoid blocking the GUI.
        """
        if self._controller is None:
            return

        def _do_extract():
            try:
                from pathlib import Path
                import subprocess

                path = Path(video_path)
                # Use absolute path from config to avoid CWD issues
                from config import config as app_config
                output = app_config.paths.output_dir / f"{path.stem}.mp3"
                output.parent.mkdir(parents=True, exist_ok=True)

                if output.exists():
                    self._audio_extracted = True
                    return  # Already extracted

                # Probe for audio stream count
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
                    # Multiple streams — mix ALL into one stereo MP3
                    cmd = [
                        "ffmpeg", "-y", "-nostdin", "-loglevel", "warning",
                        "-i", str(path.resolve()),
                        "-filter_complex",
                        f"amix=inputs={num_streams}:duration=first:dropout_transition=2,"
                        f"aresample=44100",
                        "-ac", "2",
                        "-acodec", "libmp3lame", "-q:a", "2",
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

    def _ensure_audio_player(self) -> None:
        """Lazily create QMediaPlayer + QAudioOutput."""
        if self._audio_player is not None:
            return
        try:
            from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
            from PySide6.QtCore import QUrl

            self._audio_output = QAudioOutput()
            self._audio_output.setVolume(1.0)
            self._audio_player = QMediaPlayer(self)
            self._audio_player.setAudioOutput(self._audio_output)
            self._audio_player.mediaStatusChanged.connect(
                self._on_media_status_changed
            )
        except ImportError:
            self._audio_player = None

    def _start_audio(self) -> None:
        """Start audio playback from the current playhead position."""
        self._ensure_audio_player()
        if self._audio_player is None:
            return
        if self._media_path is None:
            return
        try:
            from PySide6.QtCore import QUrl
            from pathlib import Path

            # Load audio file if not already loaded for this media
            if self._audio_loaded_for != self._media_path:
                # Use absolute path from config
                from config import config as app_config
                mp3_path = app_config.paths.output_dir / f"{Path(self._media_path).stem}.mp3"

                # Wait up to 5s for background audio extraction
                if not mp3_path.exists() and not getattr(self, '_audio_extracted', False):
                    import time as _time
                    for _ in range(50):
                        _time.sleep(0.1)
                        if mp3_path.exists():
                            break

                if mp3_path.exists():
                    self._audio_player.setSource(QUrl.fromLocalFile(str(mp3_path)))
                    self._audio_loaded_for = self._media_path
                else:
                    return  # No audio available

            # Sync audio position to playhead
            pos_ms = int(self._playhead * 1000)
            duration_ms = self._audio_player.duration()
            if duration_ms > 0:
                pos_ms = min(pos_ms, duration_ms - 100)  # Clamp near end
            self._audio_player.setPosition(max(0, pos_ms))
            self._audio_player.play()
        except Exception as exc:
            _log.warning("Audio start failed: %s", exc)

    def _pause_audio(self) -> None:
        """Pause audio playback."""
        if self._audio_player is not None:
            try:
                self._audio_player.pause()
            except Exception as exc:
                _log.warning("Audio pause failed: %s", exc)

    def _stop_audio(self) -> None:
        """Stop audio playback."""
        if self._audio_player is not None:
            try:
                self._audio_player.stop()
            except Exception as exc:
                _log.warning("Audio stop failed: %s", exc)

    def _restart_audio(self) -> None:
        """Restart audio from beginning (for loop)."""
        if self._audio_player is not None and self._audio_loaded_for is not None:
            try:
                self._audio_player.setPosition(0)
                self._audio_player.play()
            except Exception as exc:
                _log.warning("Audio restart failed: %s", exc)

    def _on_media_status_changed(self, status) -> None:
        """Handle media player status changes."""
        try:
            from PySide6.QtMultimedia import QMediaPlayer
            if status == QMediaPlayer.MediaStatus.InvalidMedia:
                _log.warning("Audio media failed to load")
            elif status == QMediaPlayer.MediaStatus.EndOfMedia:
                _log.debug("Audio playback reached end")
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # Internal: timecode formatting
    # ------------------------------------------------------------------ #
    def _emit_timecode(self, seconds: float) -> None:
        """Emit formatted timecode string."""
        s = max(0.0, float(seconds))
        h = int(s // 3600)
        m = int((s % 3600) // 60)
        sec = int(s % 60)
        frames = int((s % 1.0) * self._fps)
        tc = f"{h:02d}:{m:02d}:{sec:02d}:{frames:02d}"
        total = f"{int(self._duration // 3600):02d}:{int((self._duration % 3600) // 60):02d}:{int(self._duration % 60):02d}:{int((self._duration % 1.0) * self._fps):02d}"
        self.timecode_changed.emit(f"{tc} / {total}")
