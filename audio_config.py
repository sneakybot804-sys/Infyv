"""Phase 5C: configuration for the Audio Analyzer.

All tunables live here so no threshold, weight or sample rate is hardcoded in
the logic (Open/Closed Principle), mirroring ``HighlightScoringConfig``.

The design is CPU-first and streaming for the target hardware (Ryzen 7 5700G,
16 GB shared RAM). See ``PHASE5C_DESIGN.md``.

No backend is hardcoded in this module: the concrete default backend is chosen
by implementation-time benchmarking. ``AudioConfig.backend`` names whichever
backend the caller selects; the analyzer resolves it via a small registry.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class TrackRole(str, Enum):
    """Closed set of audio track roles.

    ``gameplay`` tracks get energy/onset/peak features. ``commentary`` tracks
    additionally get an excitement (prosody) signal. Roles are the only place
    excitement is switched on, so nothing is hardcoded per track *name*.
    """

    GAMEPLAY = "gameplay"
    COMMENTARY = "commentary"


class AudioAnalyzerError(RuntimeError):
    """Raised when audio analysis fails or no track can be analyzed.

    Mirrors the ``FFmpegServiceError`` / ``HighlightScorerError`` pattern:
    fail loud, normalized, and logged before raising.
    """


@dataclass(frozen=True)
class TrackSpec:
    """Explicit mapping of one audio track.

    When one or more ``TrackSpec`` are supplied in :class:`AudioConfig`, they
    win over automatic detection (see ``PHASE5C_DESIGN.md`` section 3.1).

    Args:
        name: Track label (e.g. ``"gameplay"``). Unique within a config.
        role: Drives excitement on/off.
        source: Audio source path, or the sentinel ``"video"`` meaning "use
            the analyzed video's own audio".
        stream_index: Audio stream index within ``source``.
    """

    name: str
    role: TrackRole
    source: str = "video"
    stream_index: int = 0


@dataclass(frozen=True)
class AudioFeatureOptions:
    """Options handed to a backend for a single track.

    These are the subset of :class:`AudioConfig` a backend needs to compute
    features; the analyzer owns everything else (id assignment, scene mapping,
    I/O), keeping backends simple and swappable.
    """

    analysis_sample_rate: int
    frame_seconds: float
    hop_seconds: float
    onset_threshold: float
    energy_peak_percentile: float
    min_event_gap_seconds: float
    compute_excitement: bool
    excitement_loudness_weight: float
    excitement_pitch_weight: float
    excitement_rate_weight: float
    excitement_peak_threshold: float


@dataclass(frozen=True)
class AudioConfig:
    """Fully configurable audio-analysis settings.

    Nothing in the analysis logic is hardcoded; tuning happens here.
    Optimized for CPU-first streaming on the target hardware.
    """

    # --- Backend (chosen by benchmarking; not locked by the design) ---
    backend: str = "numpy"

    # --- Track mapping (empty => automatic detection, section 3.1) ---
    tracks: tuple[TrackSpec, ...] = ()

    # --- Decode / streaming params ---
    target_sample_rate: int = 16000       # mono, analysis timeline
    block_seconds: float = 30.0           # streaming block size
    block_overlap_seconds: float = 1.0    # boundary carryover (section 8.2)
    max_track_seconds: float = 6 * 60 * 60  # memory/work guard (section 8.1)

    # --- Feature params ---
    frame_seconds: float = 0.05
    hop_seconds: float = 0.5

    # --- Event thresholds ---
    onset_threshold: float = 0.15         # 0..1 rise in normalized energy
    energy_peak_percentile: float = 0.90  # 0..1 percentile for peak picking
    min_event_gap_seconds: float = 0.25   # merge nearby events (deterministic)

    # --- Excitement params (commentary only) ---
    excitement_loudness_weight: float = 0.5
    excitement_pitch_weight: float = 0.3
    excitement_rate_weight: float = 0.2
    excitement_peak_threshold: float = 0.6

    # --- Skip rules ---
    skip_black_idle: bool = False         # skip analysis.json black/idle spans

    def validate(self) -> None:
        """Validate ranges, ordering and (when given) unique track names."""
        for name, value in (
            ("target_sample_rate", self.target_sample_rate),
            ("block_seconds", self.block_seconds),
            ("frame_seconds", self.frame_seconds),
            ("hop_seconds", self.hop_seconds),
            ("max_track_seconds", self.max_track_seconds),
        ):
            if value <= 0:
                raise AudioAnalyzerError(f"{name} must be positive, got {value}.")

        if self.block_overlap_seconds < 0:
            raise AudioAnalyzerError("block_overlap_seconds must be >= 0.")
        if self.block_overlap_seconds >= self.block_seconds:
            raise AudioAnalyzerError(
                "block_overlap_seconds must be smaller than block_seconds."
            )
        if self.hop_seconds < self.frame_seconds:
            raise AudioAnalyzerError(
                "hop_seconds must be >= frame_seconds."
            )
        for name, value in (
            ("onset_threshold", self.onset_threshold),
            ("energy_peak_percentile", self.energy_peak_percentile),
            ("excitement_peak_threshold", self.excitement_peak_threshold),
        ):
            if not 0.0 <= value <= 1.0:
                raise AudioAnalyzerError(f"{name} must be within 0..1, got {value}.")
        if self.min_event_gap_seconds < 0:
            raise AudioAnalyzerError("min_event_gap_seconds must be >= 0.")

        names = [spec.name for spec in self.tracks]
        if len(names) != len(set(names)):
            raise AudioAnalyzerError("TrackSpec names must be unique.")

    def feature_options(self, *, compute_excitement: bool) -> AudioFeatureOptions:
        """Build the per-track option bundle passed to a backend."""
        return AudioFeatureOptions(
            analysis_sample_rate=self.target_sample_rate,
            frame_seconds=self.frame_seconds,
            hop_seconds=self.hop_seconds,
            onset_threshold=self.onset_threshold,
            energy_peak_percentile=self.energy_peak_percentile,
            min_event_gap_seconds=self.min_event_gap_seconds,
            compute_excitement=compute_excitement,
            excitement_loudness_weight=self.excitement_loudness_weight,
            excitement_pitch_weight=self.excitement_pitch_weight,
            excitement_rate_weight=self.excitement_rate_weight,
            excitement_peak_threshold=self.excitement_peak_threshold,
        )
