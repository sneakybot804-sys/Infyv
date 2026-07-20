"""Offscreen Qt tests for the studio screen's media -> preview wiring.

Integration Milestone 2. Builds
:func:`gui.screens.studio_screen.build_studio_screen` headlessly with an
injected fake media source and asserts: the existing MediaBrowser /
TransportBar are embedded (hidden children, the approved Milestone 1
pattern), selection loads a first frame into the preview stage and updates
the window title / timecode, clearing restores the demo presentation, and
the visible transport glyphs drive the TransportBar's frozen state machine.
Skipped when PySide6 is unavailable; runs under the ``offscreen`` platform.
No backend and no :mod:`gui_core` involvement (the fake source stands in).
"""
from __future__ import annotations

import os

import pytest

pytest.importorskip("PySide6")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QImage  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

from gui.screens.studio_screen import build_studio_screen  # noqa: E402
from gui.theme.manager import ThemeManager  # noqa: E402
from gui.widgets import MediaBrowser, TransportBar  # noqa: E402


class FakeMediaSource:
    """A deterministic, in-memory stand-in for PreviewMediaSource."""

    def __init__(self, items=("alpha.mp4", "beta.mp4")):
        self._items = list(items)
        self.frame_requests = []

    def list_items(self):
        return list(self._items)

    def load_first_frame(self, name):
        self.frame_requests.append(name)
        image = QImage(4, 4, QImage.Format.Format_RGB32)
        image.fill(0xFF336699)
        return image

    def duration_timecode(self, name):
        return "00:01:30:00"


class EmptyMediaSource:
    """A source that discovers nothing (backend unavailable path)."""

    def list_items(self):
        return []

    def load_first_frame(self, name):
        return None

    def duration_timecode(self, name):
        return None


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    yield application


@pytest.fixture
def theme(app):
    manager = ThemeManager()
    manager.apply(app)
    return manager


def _build(theme, source=None):
    return build_studio_screen(theme, media_source=source or FakeMediaSource())


def test_embeds_media_browser_and_transport(theme):
    screen = _build(theme)
    assert screen.findChildren(MediaBrowser)
    assert screen.findChildren(TransportBar)


def test_embedded_widgets_are_hidden(theme):
    screen = _build(theme)
    assert not screen.findChildren(MediaBrowser)[0].isVisible()
    assert not screen.findChildren(TransportBar)[0].isVisible()


def test_browser_seeded_from_media_source(theme):
    screen = _build(theme)
    browser = screen.findChildren(MediaBrowser)[0]
    assert browser.items() == ["alpha.mp4", "beta.mp4"]
    assert browser.current_index() == -1


def test_browser_falls_back_to_demo_items_when_source_empty(theme):
    screen = _build(theme, EmptyMediaSource())
    browser = screen.findChildren(MediaBrowser)[0]
    assert browser.count() >= 1  # demo seed, never an empty browser


def test_selection_loads_first_frame_into_stage(theme):
    source = FakeMediaSource()
    screen = _build(theme, source)
    browser = screen.findChildren(MediaBrowser)[0]
    stage = screen.findChild(object, "StudioPreviewStage")
    assert not stage.has_frame()
    browser.select(0)
    assert source.frame_requests == ["alpha.mp4"]
    assert stage.has_frame()


def test_selection_updates_window_title_and_timecode(theme):
    screen = _build(theme)
    browser = screen.findChildren(MediaBrowser)[0]
    timecode = screen.findChild(QLabel, "StudioTimecode")
    browser.select(1)
    assert "beta.mp4" in screen.windowTitle()
    assert timecode.text() == "00:00:00:00 / 00:01:30:00"


def test_clearing_selection_restores_demo_presentation(theme):
    screen = _build(theme)
    browser = screen.findChildren(MediaBrowser)[0]
    stage = screen.findChild(object, "StudioPreviewStage")
    timecode = screen.findChild(QLabel, "StudioTimecode")
    browser.select(0)
    browser.select(-1)
    assert not stage.has_frame()
    assert screen.windowTitle() == "AI Gaming Video Editor"
    assert timecode.text() == "00:00:42:16 / 00:02:15:08"


def test_failed_frame_decode_keeps_demo_art(theme):
    class NoFrameSource(FakeMediaSource):
        def load_first_frame(self, name):
            return None

    screen = _build(theme, NoFrameSource())
    browser = screen.findChildren(MediaBrowser)[0]
    stage = screen.findChild(object, "StudioPreviewStage")
    browser.select(0)
    assert not stage.has_frame()  # placeholder art retained


def test_visible_glyphs_drive_transport_state_machine(theme):
    screen = _build(theme)
    transport = screen.findChildren(TransportBar)[0]
    play = screen.findChild(QLabel, "StudioTransportPlay")
    pause = screen.findChild(QLabel, "StudioTransportPause")
    stop = screen.findChild(QLabel, "StudioTransportStop")
    assert transport.state() == "stopped"
    play.mouseReleaseEvent(None)
    assert transport.state() == "playing"
    pause.mouseReleaseEvent(None)
    assert transport.state() == "paused"
    stop.mouseReleaseEvent(None)
    assert transport.state() == "stopped"


def test_transport_state_restyles_active_glyph(theme):
    screen = _build(theme)
    transport = screen.findChildren(TransportBar)[0]
    play = screen.findChild(QLabel, "StudioTransportPlay")
    transport.set_state("playing")
    theme_colors = theme.tokens.colors
    assert theme_colors.accent_cyan in play.styleSheet()


def test_default_media_source_is_lazy_and_safe(theme):
    # Without an injected source the real PreviewMediaSource is constructed;
    # with no videos on disk it must fall back to the demo seed, not raise.
    screen = build_studio_screen(theme)
    browser = screen.findChildren(MediaBrowser)[0]
    assert browser.count() >= 1
