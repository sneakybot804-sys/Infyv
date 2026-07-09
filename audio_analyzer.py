"""Phase 5C: Audio Analyzer -- independent producer of ``audio.json``.

Orchestrates automatic track detection, streaming (block-wise, bounded-memory)
feature extraction via a pluggable :class:`AudioAnalyzerBackend`, deterministic
event-id assignment, optional scene mapping from a Phase 4A ``analysis.json``,
and never-overwrite output of ``audio.json`` (schema ``5c.1``).

Hard boundaries (``PHASE5C_DESIGN.md``):
- **Fully decoupled.** No import of ``highlight_scorer``, ``video_analyzer``,
  ``scene_detector`` or any OCR module. Audio produces ``audio.json`` only.
- **Game-agnostic.** Generic acoustic events only; no interpretation.
- **CPU-first, streaming.** Never loads a whole track into RAM.
- **No magic numbers.** All tunables live in :class:`AudioConfig`.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from audio_backend import (
    AudioAnalyzerBackend,
    AudioBlock,
    RawEvent,
    TrackFeatures,
    create_backend,
)
from audio_config import (
    AudioAnalyzerError,
    AudioConfig,
    TrackRole,
    TrackSpec,
)
from config import AppConfig, config
from logger import get_logger

logger = get_logger(__name__)

SCHEMA_VERSION = "5c.1"
INPUT_SCHEMA_VERSION = "4a.1"


class AudioAnalyzer:
    """Analyze one or more audio tracks into a standalone ``audio.json``."""

    def __init__(
        self,
        app_config: AppConfig | None = None,
        audio_config: AudioConfig | None = None,
        ffmpeg_service: Any | None = None,
    ) -> None:
        """Create an analyzer.

        Args:
            app_config: Shared application config (paths).
            audio_config: Tunables; defaults are CPU-first and streaming.
            ffmpeg_service: Object exposing ``count_audio_streams`` and
                ``stream_pcm_blocks``. Injectable for tests. Imported lazily
                so unit tests never require FFmpeg.
        """
        self._config = app_config or config
        self._audio = audio_config or AudioConfig()
        self._audio.validate()
        self._ffmpeg = ffmpeg_service or self._default_ffmpeg()
        logger.info("Initialized AudioAnalyzer (backend=%s)", self._audio.backend)

    @staticmethod
    def _default_ffmpeg() -> Any:
        """Lazily construct the real FFmpegService (kept out of unit tests)."""
        from ffmpeg_service import FFmpegService

        return FFmpegService()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def analyze(
        self,
        video: str | Path,
        analysis_path: str | Path | None = None,
    ) -> dict[str, Any]:
        """Analyze ``video`` and return the ``audio.json`` document (dict)."""
        video = str(video)
        specs = self._resolve_tracks(video)
        scenes = self._load_scenes(analysis_path, video)

        tracks: list[dict[str, Any]] = []
        for spec in specs:
            try:
                tracks.append(self._analyze_track(spec, video, scenes))
            except Exception as exc:  # tolerate partial-track failure
                logger.warning(
                    "Track '%s' failed and is skipped: %s", spec.name, exc
                )

        if not tracks:
            raise AudioAnalyzerError(
                "No audio track could be analyzed for " f"'{video}'."
            )

        return {
            "schema_version": SCHEMA_VERSION,
            "video": video,
            "backend": self._audio.backend,
            "tracks": tracks,
        }

    def analyze_to_file(
        self,
        video: str | Path,
        analysis_path: str | Path | None = None,
        output_name: str | None = None,
    ) -> Path:
        """Analyze and write ``<video>_audio.json`` (never overwritten)."""
        document = self.analyze(video, analysis_path)
        out_dir = self._config.paths.output_dir
        out_dir.mkdir(parents=True, exist_ok=True)

        stem = Path(str(video)).stem
        base_name = output_name or f"{stem}_audio.json"
        output = self._unique_path(out_dir, base_name)
        output.write_text(json.dumps(document, indent=2), encoding="utf-8")
        logger.info("Wrote audio JSON -> %s", output)
        return output

    # ------------------------------------------------------------------ #
    # Track resolution (section 3.1)
    # ------------------------------------------------------------------ #
    def _resolve_tracks(self, video: str) -> list[TrackSpec]:
        """Resolve tracks by the documented priority order."""
        if self._audio.tracks:
            logger.info("Track detection: using %d config TrackSpec(s)", len(self._audio.tracks))
            return list(self._audio.tracks)

        count = self._ffmpeg.count_audio_streams(video)
        if count >= 2:
            if count > 2:
                logger.info(
                    "Track detection: %d streams found; using 0=gameplay, "
                    "1=commentary, ignoring %d extra stream(s).",
                    count,
                    count - 2,
                )
            else:
                logger.info("Track detection: auto-2 (gameplay + commentary)")
            return [
                TrackSpec("gameplay", TrackRole.GAMEPLAY, "video", 0),
                TrackSpec("commentary", TrackRole.COMMENTARY, "video", 1),
            ]
        if count == 1:
            logger.info("Track detection: auto-1 (gameplay only)")
            return [TrackSpec("gameplay", TrackRole.GAMEPLAY, "video", 0)]

        raise AudioAnalyzerError(
            f"No audio stream found in '{video}' and no TrackSpec configured."
        )

    # ------------------------------------------------------------------ #
    # Per-track streaming analysis
    # ------------------------------------------------------------------ #
    def _analyze_track(
        self,
        spec: TrackSpec,
        video: str,
        scenes: list[dict[str, float]] | None,
    ) -> dict[str, Any]:
        """Stream one track through the backend and build its track object."""
        source = video if spec.source == "video" else spec.source
        compute_excitement = spec.role == TrackRole.COMMENTARY
        options = self._audio.feature_options(compute_excitement=compute_excitement)

        backend: AudioAnalyzerBackend = create_backend(self._audio.backend)
        sr = self._audio.target_sample_rate
        backend.start_track(sr, options)

        total_samples = 0
        max_samples = int(self._audio.max_track_seconds * sr)
        for block in self._iter_blocks(source, spec.stream_index):
            start_seconds = total_samples / float(sr)
            backend.process_block(AudioBlock(samples=block, start_seconds=start_seconds))
            total_samples += block.size
            if total_samples > max_samples:
                raise AudioAnalyzerError(
                    f"Track '{spec.name}' exceeds max_track_seconds "
                    f"({self._audio.max_track_seconds}s)."
                )

        if total_samples == 0:
            raise AudioAnalyzerError(f"Track '{spec.name}' has no audio samples.")

        features: TrackFeatures = backend.finalize()
        duration = round(total_samples / float(sr), 3)

        events = self._assign_event_ids(spec.name, features.events)
        events_json = [self._event_to_json(e, scenes) for e in events]
        excitement_json = self._excitement_to_json(spec.name, features, scenes)

        return {
            "name": spec.name,
            "role": spec.role.value,
            "source": source,
            "stream_index": spec.stream_index,
            "source_sample_rate": self._probe_source_rate(source, spec.stream_index),
            "analysis_sample_rate": sr,
            "duration": duration,
            "features": {
                "rms_series": {
                    "hop_seconds": features.hop_seconds,
                    "values": features.rms_series,
                },
                "avg_rms": features.avg_rms,
                "peak_rms": features.peak_rms,
            },
            "events": events_json,
            "excitement": excitement_json,
        }

    def _iter_blocks(self, source: str, stream_index: int) -> Iterable[np.ndarray]:
        """Yield streaming PCM blocks for one source stream."""
        return self._ffmpeg.stream_pcm_blocks(
            source,
            sample_rate=self._audio.target_sample_rate,
            stream_index=stream_index,
            block_seconds=self._audio.block_seconds,
        )

    def _probe_source_rate(self, source: str, stream_index: int) -> int | None:
        """Best-effort source sample rate for provenance (never fatal)."""
        probe = getattr(self._ffmpeg, "audio_stream_sample_rate", None)
        if callable(probe):
            try:
                return int(probe(source, stream_index))
            except Exception:  # pragma: no cover - provenance only
                return None
        return None

    # ------------------------------------------------------------------ #
    # Deterministic event ids (section 5.1)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _assign_event_ids(
        track_name: str, events: list[RawEvent]
    ) -> list[RawEvent]:
        """Assign stable ids per (track, type) in chronological order.

        Ordering: ascending ``start``, ties broken by ``end`` then ``type``
        for full determinism. Ids are attached via a parallel list to keep
        :class:`RawEvent` id-free at the backend boundary.
        """
        ordered = sorted(events, key=lambda e: (e.start, e.end, e.type))
        counters: dict[tuple[str, str], int] = {}
        for ev in ordered:
            key = (track_name, ev.type)
            counters[key] = counters.get(key, 0) + 1
            ev.id = f"{track_name}-{ev.type}-{counters[key]:04d}"
        return ordered

    def _event_to_json(
        self, event: RawEvent, scenes: list[dict[str, float]] | None
    ) -> dict[str, Any]:
        return {
            "id": event.id,
            "start": event.start,
            "end": event.end,
            "type": event.type,
            "energy": event.energy,
            "confidence": event.confidence,
            "scene_index": self._scene_index_for(event.start, scenes),
        }

    def _excitement_to_json(
        self,
        track_name: str,
        features: TrackFeatures,
        scenes: list[dict[str, float]] | None,
    ) -> dict[str, Any] | None:
        if features.excitement is None:
            return None
        exc = features.excitement
        ordered = sorted(exc.peaks, key=lambda p: (p.start, p.end))
        peaks_json = []
        for i, peak in enumerate(ordered, start=1):
            peaks_json.append(
                {
                    "id": f"{track_name}-excitement_peak-{i:04d}",
                    "start": peak.start,
                    "end": peak.end,
                    "score": peak.score,
                    "scene_index": self._scene_index_for(peak.start, scenes),
                }
            )
        return {
            "hop_seconds": exc.hop_seconds,
            "score_series": exc.score_series,
            "peaks": peaks_json,
        }

    # ------------------------------------------------------------------ #
    # Scene mapping (section 8.3)
    # ------------------------------------------------------------------ #
    def _load_scenes(
        self, analysis_path: str | Path | None, video: str
    ) -> list[dict[str, float]] | None:
        """Load scene bounds from an optional analysis.json.

        Returns None (=> all scene_index null) when the file is absent,
        unreadable, or its ``video`` key does not match this input.
        """
        if analysis_path is None:
            return None
        path = Path(analysis_path).expanduser()
        if not path.is_file():
            logger.warning("analysis.json not found at %s; scene_index=null", path)
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not read analysis.json (%s); scene_index=null", exc)
            return None

        recorded = str(data.get("video", ""))
        if recorded and Path(recorded).name != Path(video).name:
            logger.warning(
                "analysis.json video '%s' does not match '%s'; scene_index=null",
                recorded,
                video,
            )
            return None

        scenes = data.get("scenes", [])
        if not isinstance(scenes, list):
            return None
        return [
            {"start": float(s.get("start", 0.0)), "end": float(s.get("end", 0.0))}
            for s in scenes
        ]

    @staticmethod
    def _scene_index_for(
        start: float, scenes: list[dict[str, float]] | None
    ) -> int | None:
        """Map an event start to a scene using a half-open interval.

        Rule: ``scene.start <= start < scene.end``. Events outside all scenes,
        or when no scenes are available, map to ``None`` (never 0).
        """
        if not scenes:
            return None
        for index, scene in enumerate(scenes):
            if scene["start"] <= start < scene["end"]:
                return index
        return None

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _unique_path(directory: Path, base_name: str) -> Path:
        """Return a path in ``directory`` that does not already exist."""
        candidate = directory / base_name
        if not candidate.exists():
            return candidate
        stem = Path(base_name).stem
        suffix = Path(base_name).suffix
        counter = 1
        while True:
            candidate = directory / f"{stem}_{counter}{suffix}"
            if not candidate.exists():
                return candidate
            counter += 1
