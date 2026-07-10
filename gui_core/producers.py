"""Default backend-producer factory bundle.

:class:`DefaultProducerFactories` constructs the real, frozen backend
producers bound to the shared application config. Every producer is imported
**lazily** inside its factory method so that merely importing ``gui_core`` (or
running the Qt-free unit tests with fakes) never imports FFmpeg, Ollama or
Tesseract dependencies.

This is the single place the core touches concrete backend classes; commands
receive the bundle via their context and call only the producers' existing
public methods.

No Qt symbol is imported here.
"""
from __future__ import annotations

from typing import Any


class DefaultProducerFactories:
    """Build real backend producers on demand, bound to the app config.

    Args:
        app_config: The shared application config passed to each producer.
    """

    def __init__(self, app_config: Any) -> None:
        self._config = app_config

    def analysis(self) -> Any:
        """Return a Phase 4A :class:`VideoAnalyzer`."""
        from video_analyzer import VideoAnalyzer

        return VideoAnalyzer(self._config)

    def highlight(self) -> Any:
        """Return a Phase 5A :class:`HighlightScorer`."""
        from highlight_scorer import HighlightScorer

        return HighlightScorer(self._config)

    def ocr(self) -> Any:
        """Return a Phase 5B :class:`HudTextExtractor`."""
        from hud_text_extractor import HudTextExtractor

        return HudTextExtractor(self._config)

    def audio(self) -> Any:
        """Return a Phase 5C :class:`AudioAnalyzer`."""
        from audio_analyzer import AudioAnalyzer

        return AudioAnalyzer(self._config)

    def fusion(self) -> Any:
        """Return a Phase 5D :class:`SignalFusionEngine`."""
        from signal_fusion import SignalFusionEngine

        return SignalFusionEngine(self._config)

    def decision(self) -> Any:
        """Return a Phase 5E :class:`DecisionAgent`."""
        from decision_agent import DecisionAgent

        return DecisionAgent(self._config)

    def render(self) -> Any:
        """Return a Phase 6 :class:`VideoEditor`."""
        from video_editor import VideoEditor

        return VideoEditor(self._config)

    def subtitles(self) -> Any:
        """Return a Phase 7 :class:`SubtitleEngine`."""
        from subtitle_engine import SubtitleEngine

        return SubtitleEngine(self._config)
