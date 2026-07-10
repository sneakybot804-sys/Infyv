"""High-DPI configuration and token-aware scaling helpers.

Enabling high-DPI behaviour must happen before the :class:`QApplication` is
created, so :func:`configure_high_dpi` is called from the application entry
point. :func:`scale` converts a logical token value to device pixels using the
active screen's device pixel ratio, keeping spacing/radius crisp across
displays.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication


def configure_high_dpi() -> None:
    """Enable high-DPI pixmaps and a sensible rounding policy.

    Safe to call once at startup before the QApplication is constructed. On
    Qt 6 automatic high-DPI scaling is always on; this pins the rounding
    policy so fractional scale factors (e.g. 125%, 150%) render cleanly.
    """
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )


def device_pixel_ratio() -> float:
    """Return the primary screen's device pixel ratio (1.0 if unavailable)."""
    app = QGuiApplication.instance()
    if app is None:
        return 1.0
    screen = QGuiApplication.primaryScreen()
    return float(screen.devicePixelRatio()) if screen is not None else 1.0


def scale(value: float, dpr: float | None = None) -> int:
    """Scale a logical ``value`` by the device pixel ratio, rounded to int."""
    ratio = dpr if dpr is not None else device_pixel_ratio()
    return int(round(value * ratio))
