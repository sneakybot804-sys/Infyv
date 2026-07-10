"""gui: the PySide6 presentation layer.

Qt is used **only** inside this package. The application core
(:mod:`gui_core`) remains completely Qt-free; the GUI talks to the backend
exclusively through :class:`gui_core.ApplicationFacade` (wired in a later
phase).

Phase 8B provides the theme foundation only: design tokens, the dark theme,
and the :class:`~gui.theme.manager.ThemeManager`. No widgets, pages, or
business logic live here yet.
"""
