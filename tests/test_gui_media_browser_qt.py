"""Offscreen Qt tests for the Phase 8H Milestone 2 media widgets.

Covers the two new UI-only widgets -- :class:`MediaBrowser` and
:class:`TransportBar` -- for object names, public API, signals and state
transitions. Additive and independent of existing tests. Skipped when PySide6
is unavailable; runs under the ``offscreen`` Qt platform. No backend and no
:mod:`gui_core` involvement.
"""
from __future__ import annotations

import os

import pytest

pytest.importorskip("PySide6")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from gui.theme.manager import ThemeManager  # noqa: E402
from gui.widgets import MediaBrowser, TransportBar  # noqa: E402


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    yield application


@pytest.fixture
def theme(app):
    manager = ThemeManager()
    manager.apply(app)
    return manager


def _find(root, object_name):
    for child in root.findChildren(QWidget):
        if child.objectName() == object_name:
            return child
    return None


# ---------------------------------------------------------------------- #
# MediaBrowser
# ---------------------------------------------------------------------- #
def test_media_browser_object_names(theme):
    browser = MediaBrowser(theme)
    assert browser.objectName() == "MediaBrowser"
    assert _find(browser, "MediaBrowserImport") is not None
    assert _find(browser, "MediaBrowserList") is not None


def test_media_browser_empty_by_default(theme):
    browser = MediaBrowser(theme)
    assert browser.items() == []
    assert browser.count() == 0
    assert browser.current_index() == -1
    assert browser.current_item() is None


def test_media_browser_set_items_populates_rows(theme):
    browser = MediaBrowser(theme)
    browser.set_items(["a.mp4", "b.mp4"])
    assert browser.items() == ["a.mp4", "b.mp4"]
    assert browser.count() == 2
    rows = [w for w in browser.findChildren(QWidget) if w.objectName() == "MediaItem"]
    assert len(rows) == 2


def test_media_browser_set_items_emits_cleared_selection(theme):
    browser = MediaBrowser(theme)
    received = []
    browser.selection_changed.connect(received.append)
    browser.set_items(["a.mp4", "b.mp4"])
    assert received == [-1]
    assert browser.current_index() == -1


def test_media_browser_select_emits_and_updates(theme):
    browser = MediaBrowser(theme, items=["a.mp4", "b.mp4", "c.mp4"])
    received = []
    browser.selection_changed.connect(received.append)
    browser.select(1)
    assert received == [1]
    assert browser.current_index() == 1
    assert browser.current_item() == "b.mp4"


def test_media_browser_select_same_is_noop(theme):
    browser = MediaBrowser(theme, items=["a.mp4", "b.mp4"])
    browser.select(0)
    received = []
    browser.selection_changed.connect(received.append)
    browser.select(0)
    assert received == []


def test_media_browser_select_clear(theme):
    browser = MediaBrowser(theme, items=["a.mp4"])
    browser.select(0)
    browser.select(-1)
    assert browser.current_index() == -1
    assert browser.current_item() is None


def test_media_browser_select_out_of_range_raises(theme):
    browser = MediaBrowser(theme, items=["a.mp4"])
    with pytest.raises(ValueError):
        browser.select(5)


def test_media_browser_import_signal(theme):
    browser = MediaBrowser(theme)
    fired = {"n": 0}
    browser.import_requested.connect(lambda: fired.__setitem__("n", fired["n"] + 1))
    button = _find(browser, "MediaBrowserImport")
    button.clicked.emit()
    assert fired["n"] == 1


# ---------------------------------------------------------------------- #
# TransportBar
# ---------------------------------------------------------------------- #
def test_transport_object_names(theme):
    bar = TransportBar(theme)
    assert bar.objectName() == "TransportBar"
    for name in ("TransportPlay", "TransportPause", "TransportStop", "TransportSeek"):
        assert _find(bar, name) is not None, f"missing {name}"


def test_transport_initial_state(theme):
    bar = TransportBar(theme)
    assert bar.state() == "stopped"
    assert bar.position() == 0.0


def test_transport_play_pause_stop_state_machine(theme):
    bar = TransportBar(theme)
    states = []
    bar.state_changed.connect(states.append)

    _find(bar, "TransportPlay").clicked.emit()
    assert bar.state() == "playing"
    _find(bar, "TransportPause").clicked.emit()
    assert bar.state() == "paused"
    _find(bar, "TransportStop").clicked.emit()
    assert bar.state() == "stopped"
    assert states == ["playing", "paused", "stopped"]


def test_transport_request_signals(theme):
    bar = TransportBar(theme)
    fired = []
    bar.play_requested.connect(lambda: fired.append("play"))
    bar.pause_requested.connect(lambda: fired.append("pause"))
    bar.stop_requested.connect(lambda: fired.append("stop"))
    _find(bar, "TransportPlay").clicked.emit()
    _find(bar, "TransportPause").clicked.emit()
    _find(bar, "TransportStop").clicked.emit()
    assert fired == ["play", "pause", "stop"]


def test_transport_set_state_valid_and_invalid(theme):
    bar = TransportBar(theme)
    bar.set_state("playing")
    assert bar.state() == "playing"
    with pytest.raises(ValueError):
        bar.set_state("nope")


def test_transport_stop_resets_position(theme):
    bar = TransportBar(theme)
    bar.set_position(0.7)
    assert bar.position() == pytest.approx(0.7, abs=1e-3)
    _find(bar, "TransportStop").clicked.emit()
    assert bar.position() == 0.0


def test_transport_set_position_clamps_without_seek_signal(theme):
    bar = TransportBar(theme)
    seeks = []
    bar.seek_requested.connect(seeks.append)
    bar.set_position(2.0)  # clamps to 1.0, must not emit seek_requested
    assert bar.position() == pytest.approx(1.0, abs=1e-3)
    assert seeks == []


def test_transport_seek_signal_from_slider(theme):
    bar = TransportBar(theme)
    seeks = []
    bar.seek_requested.connect(seeks.append)
    seek = _find(bar, "TransportSeek")
    seek.set_value(0.5)
    assert seeks, "expected a seek_requested emission from the slider"
    assert seeks[-1] == pytest.approx(0.5, abs=1e-3)
