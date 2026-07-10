"""Theme foundation for the GUI.

This package owns every visual design decision as centralized *tokens* and the
machinery that turns those tokens into a Qt stylesheet, palette, fonts and
icons. :class:`~gui.theme.manager.ThemeManager` is the single authority for
the active theme; future widgets must query the manager rather than importing
token modules directly.

Only the Dark theme is implemented in Phase 8B. The architecture supports
additional themes, but none are registered yet.
"""
