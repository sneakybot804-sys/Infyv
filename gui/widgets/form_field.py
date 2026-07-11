"""FormField: a label + one injected control + optional helper/error text.

A composite presentation widget (Phase 8C-6) that pairs a descriptive label
with a single, pre-built control widget and optional helper text. It composes
:class:`MetaLabel` members and lays out an injected control; it never creates
the control itself and never inspects its value. All visuals come from the
injected :class:`ThemeManager`. Installs no :class:`QGraphicsEffect`, so it is
safe inside an effect-bearing container such as ``GlassCard``.

The control is immutable after construction: there is no ``set_control``. The
widget exposes no signals and performs no validation logic; ``set_error`` is a
presentation-only display method (the caller decides validity).
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from gui.theme.manager import ThemeManager
from gui.widgets import styling
from gui.widgets.base import ThemedWidget
from gui.widgets.meta_label import MetaLabel

#: Suffix appended to the label text when the field is required.
_REQUIRED_MARK = " *"


class FormField(ThemedWidget):
    """A labeled wrapper around a single injected control.

    Args:
        theme: Injected theme manager (sole source of visual values).
        label: The descriptive label shown above the control.
        control: A pre-built child widget (e.g. ``TextField``, ``Dropdown``,
            ``ToggleSwitch``, ``Checkbox``, ``Slider``). Accepted as a plain
            ``QWidget`` to stay decoupled from concrete control types. It is
            immutable after construction.
        helper: Optional helper text below the control; when empty the row is
            hidden and its layout spacing collapses.
        required: When ``True``, a marker is appended to the label and the
            accessible name notes that the field is required. This is visual
            and accessibility metadata only; no validation is performed.
        parent: Optional Qt parent.

    Raises:
        TypeError: If ``control`` is not a ``QWidget`` or ``label`` is not a
            ``str``.
    """

    def __init__(
        self,
        theme: ThemeManager,
        label: str,
        control: QWidget,
        *,
        helper: str = "",
        required: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(theme, parent)
        if not isinstance(label, str):
            raise TypeError(f"label must be str, got {type(label).__name__}.")
        if not isinstance(control, QWidget):
            raise TypeError(
                f"control must be a QWidget, got {type(control).__name__}."
            )

        self._label_text = label
        self._control = control
        self._helper_text = helper
        self._required = bool(required)
        self._error: Optional[str] = None

        self._column = QVBoxLayout(self)
        self._column.setContentsMargins(0, 0, 0, 0)

        # Composed themed labels: label (secondary caption) and helper (muted
        # caption) are MetaLabels that self-style. The error row is a plain
        # QLabel owned and colored directly by this widget: it must be styled
        # with the error color, and a MetaLabel would re-apply its own role
        # color to the shared '#MetaLabel' selector on every theme change
        # (subscriber order is undefined), overwriting the error tint. Owning
        # a QLabel here keeps the error color under FormField.apply_theme()
        # exclusively, so it survives theme changes.
        self._label = MetaLabel(theme, self._display_label(), role="secondary", style="caption")
        self._helper = MetaLabel(theme, helper, role="muted", style="caption")
        self._error_label = QLabel("", self)
        self._error_label.setObjectName("FormFieldError")
        self._error_label.setWordWrap(True)

        control.setParent(self)
        self._column.addWidget(self._label)
        self._column.addWidget(control)
        self._column.addWidget(self._helper)
        self._column.addWidget(self._error_label)

        self._sync_helper_visibility()
        self._sync_error_visibility()
        self._refresh_accessible_name()
        self.apply_theme()

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _display_label(self) -> str:
        """Return the label text with the required marker when applicable."""
        if self._required and self._label_text:
            return f"{self._label_text}{_REQUIRED_MARK}"
        if self._required:
            return _REQUIRED_MARK.strip()
        return self._label_text

    def _sync_helper_visibility(self) -> None:
        """Show the helper row only when it has text and no error is shown."""
        show = bool(self._helper_text) and self._error is None
        self._helper.setVisible(show)
        self._apply_spacing()

    def _sync_error_visibility(self) -> None:
        """Show the error row only when an error message is set."""
        self._error_label.setVisible(self._error is not None)
        self._apply_spacing()

    def _apply_spacing(self) -> None:
        """Collapse column spacing when neither helper nor error is shown."""
        has_sub = self._helper.isVisibleTo(self) or self._error_label.isVisibleTo(self)
        gap = self.scaled(self.tokens.spacing.xxs) if has_sub else 0
        self._column.setSpacing(gap)

    def _refresh_accessible_name(self) -> None:
        """Recompute the accessible name from label + required state."""
        name = self._label_text or "field"
        if self._required:
            name = f"{name} (required)"
        self.setAccessibleName(name)
        self.setAccessibleDescription(self._error or "")

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def label(self) -> str:
        """Return the label text (without the required marker)."""
        return self._label_text

    def set_label(self, label: str) -> None:
        """Set the label text."""
        self._label_text = label
        self._label.set_text(self._display_label())
        self._refresh_accessible_name()

    def control(self) -> QWidget:
        """Return the injected control (immutable after construction)."""
        return self._control

    def helper(self) -> str:
        """Return the helper text."""
        return self._helper_text

    def set_helper(self, helper: str) -> None:
        """Set the helper text; hides the row and collapses spacing when empty."""
        self._helper_text = helper
        self._helper.set_text(helper)
        self._sync_helper_visibility()

    def is_required(self) -> bool:
        """Return whether the field is marked required."""
        return self._required

    def set_required(self, required: bool) -> None:
        """Set the required marker (visual + accessibility only)."""
        self._required = bool(required)
        self._label.set_text(self._display_label())
        self._refresh_accessible_name()

    def set_error(self, message: Optional[str]) -> None:
        """Set (or clear with ``None``) a presentation-only error message.

        This performs no validation; it only displays ``message`` in the error
        color. Passing ``None`` clears the error and restores the helper row.
        """
        self._error = message if message else None
        self._error_label.setText(self._error or "")
        self._sync_error_visibility()
        self._sync_helper_visibility()
        self._refresh_accessible_name()
        self.apply_theme()

    def error(self) -> Optional[str]:
        """Return the current error message, or ``None``."""
        return self._error

    # ------------------------------------------------------------------ #
    # Theming
    # ------------------------------------------------------------------ #
    def apply_theme(self) -> None:
        """Apply spacing, the error font and the error text color.

        The label and helper are MetaLabels that restyle themselves. The error
        QLabel is owned here, so its font and error color are (re)applied on
        every theme change without any competing subscriber, which is what
        makes the error tint survive a theme change.
        """
        self._apply_spacing()
        colors = self.tokens.colors
        self._error_label.setFont(self._theme.font("caption"))
        self._error_label.setStyleSheet(
            styling.label_color_qss(colors.error, selector="#FormFieldError")
        )
