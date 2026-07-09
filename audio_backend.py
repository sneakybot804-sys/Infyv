"""Phase 5C: pluggable, streaming audio-analysis backends.

The backend contract is **block-wise / streaming** (``PHASE5C_DESIGN.md``
section 6): a backend never receives a whole track. The analyzer feeds it
sequential mono PCM blocks and then calls ``finalize()``. A backend must only
keep bounded state (running aggregates + a small boundary carryover) so peak
memory stays constant regardless of track length.

Backends return **raw** features and events: no ids and no ``scene_index``.
The analyzer performs block-boundary reconciliation, deterministic id
assignment and scene mapping (see ``audio_analyzer.py``). This keeps ids
stable and identical across backends.

CPU-only, no GPU, no heavy ML. The default :class:`NumpyAudioBackend` uses
only numpy so it stays light on the Ryzen 7 5700G target. The concrete default
is a benchmarking decision; other CPU backends can register without touching
the analyzer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Protocol, runtime_checkable

import numpy as np
from numpy.typing import NDArray

from audio_config import AudioFeatureOptions
from logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class AudioBlock:
    """One streaming block of mono audio at the analysis sample rate."""

    samples: NDArray[np.float32]
    start_seconds: float


@dataclass
class RawEvent:
    """A discrete acoustic event.

    ``type`` is a generic acoustic label (``onset`` | ``energy_peak`` |
    ``loudness_peak``), never a game concept. All magnitudes are normalized
    0..1. Backends leave ``id`` as ``None``; the analyzer assigns the stable
    ``id`` (after reconciliation) and the ``scene_index`` later.
    """

    start: float
    end: float
    type: str
    energy: float
    confidence: float
    id: str | None = None


@dataclass
class RawExcitementPeak:
    """An excitement peak (commentary prosody), WITHOUT id or scene_index."""

    start: float
    end: float
    score: float


@dataclass
class ExcitementResult:
    """Commentary-only prosody output."""

    hop_seconds: float
    score_series: list[float]
    peaks: list[RawExcitementPeak]


@dataclass
class TrackFeatures:
    """Aggregated per-track result returned by ``finalize()``."""

    hop_seconds: float
    rms_series: list[float]
    avg_rms: float
    peak_rms: float
    events: list[RawEvent] = field(default_factory=list)
    excitement: ExcitementResult | None = None


@runtime_checkable
class AudioAnalyzerBackend(Protocol):
    """Streaming, block-wise feature backend.

    Lifecycle per track: ``start_track`` -> N x ``process_block`` ->
    ``finalize``. Implementations must not retain whole-track buffers.
    """

    name: str

    def start_track(self, sample_rate: int, options: AudioFeatureOptions, /) -> None:
        """Begin a new track; reset per-track accumulators."""
        ...

    def process_block(self, block: AudioBlock, /) -> None:
        """Consume one streaming block, updating only bounded state."""
        ...

    def finalize(self) -> TrackFeatures:
        """Return aggregated features + raw (id-less) events for the track."""
        ...


class NumpyAudioBackend:
    """Default CPU-only backend using numpy alone (no heavy ML, no GPU).

    Computes a hop-aligned RMS energy series, onset and energy-peak events,
    and (for commentary) a lightweight excitement proxy from loudness
    dynamics + speech-rate (onset density). Pitch is intentionally omitted to
    keep the default fast on the 5700G; a richer backend may add it.

    Streaming: audio arrives in blocks. Frames that straddle a block boundary
    are handled by carrying a small tail of samples into the next block, so
    the hop grid is continuous and events near boundaries are not split.
    """

    name = "numpy"

    def __init__(self) -> None:
        self._sr = 0
        self._opts: AudioFeatureOptions | None = None
        self._frame_len = 0
        self._hop_len = 0
        # Pending samples and the absolute index of buffer[0] in the track.
        self._carry = np.empty(0, dtype=np.float32)
        self._buffer_start_sample = 0
        # Absolute sample index of the next hop to emit (global grid).
        self._next_hop_sample = 0
        self._rms: list[float] = []
        self._hop_times: list[float] = []

    # -- lifecycle -------------------------------------------------------- #
    def start_track(self, sample_rate: int, options: AudioFeatureOptions, /) -> None:
        self._sr = sample_rate
        self._opts = options
        self._frame_len = max(int(round(options.frame_seconds * sample_rate)), 1)
        self._hop_len = max(int(round(options.hop_seconds * sample_rate)), 1)
        self._carry = np.empty(0, dtype=np.float32)
        self._buffer_start_sample = 0
        self._next_hop_sample = 0
        self._rms = []
        self._hop_times = []

    def process_block(self, block: AudioBlock, /) -> None:
        # Append the new block to any pending tail. Hops are emitted on a
        # GLOBAL sample grid (multiples of hop_len from track start), so the
        # RMS series is identical no matter how the stream is chunked.
        buf = (
            block.samples
            if self._carry.size == 0
            else np.concatenate([self._carry, block.samples])
        )
        n = buf.size
        while True:
            local = self._next_hop_sample - self._buffer_start_sample
            if local + self._frame_len > n:
                break
            frame = buf[local : local + self._frame_len]
            rms = float(np.sqrt(np.mean(np.square(frame, dtype=np.float64))))
            self._rms.append(rms)
            self._hop_times.append(self._next_hop_sample / float(self._sr))
            self._next_hop_sample += self._hop_len
        # Discard only samples strictly before the next hop; keep the rest.
        keep_from = max(0, self._next_hop_sample - self._buffer_start_sample)
        keep_from = min(keep_from, n)
        self._carry = buf[keep_from:].astype(np.float32, copy=True)
        self._buffer_start_sample += keep_from

    def finalize(self) -> TrackFeatures:
        assert self._opts is not None, "start_track must be called first"
        opts = self._opts
        rms = np.asarray(self._rms, dtype=np.float64)
        norm = self._normalize(rms)
        events = self._detect_events(norm, opts)
        excitement = (
            self._excitement(norm, opts) if opts.compute_excitement else None
        )
        return TrackFeatures(
            hop_seconds=opts.hop_seconds,
            rms_series=[round(float(v), 6) for v in norm],
            avg_rms=round(float(norm.mean()) if norm.size else 0.0, 6),
            peak_rms=round(float(norm.max()) if norm.size else 0.0, 6),
            events=events,
            excitement=excitement,
        )

    # -- feature math (pure, testable) ------------------------------------ #
    @staticmethod
    def _normalize(rms: NDArray[np.float64]) -> NDArray[np.float64]:
        """Scale an RMS series to 0..1 by its own peak (deterministic)."""
        if rms.size == 0:
            return rms
        peak = float(rms.max())
        if peak <= 0.0:
            return np.zeros_like(rms)
        return rms / peak

    def _detect_events(
        self, norm: NDArray[np.float64], opts: AudioFeatureOptions
    ) -> list[RawEvent]:
        """Detect onsets (rising energy) and energy peaks over the hop grid."""
        events: list[RawEvent] = []
        if norm.size == 0:
            return events

        times = self._hop_times
        hop = opts.hop_seconds

        # Onsets: positive jump between consecutive hops above a threshold.
        for i in range(1, norm.size):
            rise = norm[i] - norm[i - 1]
            if rise >= opts.onset_threshold:
                events.append(
                    RawEvent(
                        start=round(times[i], 3),
                        end=round(times[i] + hop, 3),
                        type="onset",
                        energy=round(float(norm[i]), 6),
                        confidence=round(min(1.0, rise), 6),
                    )
                )

        # Energy peaks: hops at/above a percentile that are local maxima.
        # A flat or silent series has no meaningful peak, so require the value
        # to be strictly positive and above the onset threshold; this ensures
        # silence (all zeros) produces no events.
        threshold = max(
            float(np.quantile(norm, opts.energy_peak_percentile)),
            opts.onset_threshold,
        )
        for i in range(norm.size):
            left = norm[i - 1] if i > 0 else -np.inf
            right = norm[i + 1] if i + 1 < norm.size else -np.inf
            if (
                norm[i] > 0.0
                and norm[i] >= threshold
                and norm[i] >= left
                and norm[i] >= right
            ):
                events.append(
                    RawEvent(
                        start=round(times[i], 3),
                        end=round(times[i] + hop, 3),
                        type="energy_peak",
                        energy=round(float(norm[i]), 6),
                        confidence=round(float(norm[i]), 6),
                    )
                )

        return self._merge_events(events, opts.min_event_gap_seconds)

    @staticmethod
    def _merge_events(events: list[RawEvent], min_gap: float) -> list[RawEvent]:
        """Deterministically merge same-type events closer than ``min_gap``.

        Stable ordering: (type, start). The higher-confidence instance wins
        when two of the same type are merged, extending the span.
        """
        if not events:
            return events
        ordered = sorted(events, key=lambda e: (e.type, e.start))
        merged: list[RawEvent] = []
        for ev in ordered:
            if merged and merged[-1].type == ev.type and (
                ev.start - merged[-1].start
            ) < min_gap:
                prev = merged[-1]
                prev.end = max(prev.end, ev.end)
                if ev.confidence > prev.confidence:
                    prev.energy = ev.energy
                    prev.confidence = ev.confidence
            else:
                merged.append(ev)
        # Final ordering chronological, ties by type for determinism.
        return sorted(merged, key=lambda e: (e.start, e.type))

    def _excitement(
        self, norm: NDArray[np.float64], opts: AudioFeatureOptions
    ) -> ExcitementResult:
        """Lightweight prosody proxy for commentary (loudness + rate).

        No pitch tracking in the default backend. Excitement combines
        normalized loudness with a local rate proxy (density of rises),
        weighted per config. Pitch weight is folded into loudness when pitch
        is unavailable so the weights still sum meaningfully.
        """
        if norm.size == 0:
            return ExcitementResult(opts.hop_seconds, [], [])

        # Local rate proxy: fraction of recent hops that rose.
        rises = np.zeros_like(norm)
        rises[1:] = np.clip(np.diff(norm), 0.0, None)
        window = max(3, int(round(1.0 / opts.hop_seconds)))
        kernel = np.ones(window) / float(window)
        rate = np.convolve(rises, kernel, mode="same")
        rate = self._normalize(rate)

        loud_w = opts.excitement_loudness_weight + opts.excitement_pitch_weight
        rate_w = opts.excitement_rate_weight
        total = loud_w + rate_w or 1.0
        score = (loud_w * norm + rate_w * rate) / total
        score = np.clip(score, 0.0, 1.0)

        peaks: list[RawExcitementPeak] = []
        times = self._hop_times
        for i in range(score.size):
            left = score[i - 1] if i > 0 else -np.inf
            right = score[i + 1] if i + 1 < score.size else -np.inf
            if (
                score[i] >= opts.excitement_peak_threshold
                and score[i] >= left
                and score[i] >= right
            ):
                peaks.append(
                    RawExcitementPeak(
                        start=round(times[i], 3),
                        end=round(times[i] + opts.hop_seconds, 3),
                        score=round(float(score[i]), 6),
                    )
                )

        return ExcitementResult(
            hop_seconds=opts.hop_seconds,
            score_series=[round(float(v), 6) for v in score],
            peaks=peaks,
        )


# --------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------- #
BackendFactory = Callable[[], AudioAnalyzerBackend]

_REGISTRY: dict[str, BackendFactory] = {
    NumpyAudioBackend.name: NumpyAudioBackend,
}


def register_backend(name: str, factory: BackendFactory) -> None:
    """Register a backend factory under ``name`` (idempotent overwrite)."""
    _REGISTRY[name] = factory


def create_backend(name: str) -> AudioAnalyzerBackend:
    """Instantiate a registered backend by name."""
    try:
        factory = _REGISTRY[name]
    except KeyError as exc:
        available = ", ".join(sorted(_REGISTRY)) or "(none)"
        raise KeyError(
            f"Unknown audio backend '{name}'. Available: {available}."
        ) from exc
    return factory()


def available_backends() -> list[str]:
    """Return the sorted list of registered backend names."""
    return sorted(_REGISTRY)
