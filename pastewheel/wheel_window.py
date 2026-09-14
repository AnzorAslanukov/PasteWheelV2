"""The radial wheel popup window (SPEC §4, §6, §7.1, §7.2, §7.3).

Design notes (not dictated verbatim by SPEC.md, filled in by the
implementer within its constraints):

- The window is sized to cover the *entire monitor* the pointer is on
  (``screen_rect`` passed to :meth:`WheelWindow.show_at`), not just the
  button cluster's bounding box. This lets a single ``mousePressEvent``
  on the window itself implement "left-click on empty space inside or
  outside the wheel closes it" (D2, FR-1.4) without needing an OS-level
  global mouse hook for that specific behavior — clicks that land on a
  button widget are consumed by that widget and never reach this
  handler. The wheel *graphic* (buttons) is what gets clamped to stay
  fully on that monitor (FR-2.5); the window itself is simply the
  monitor's size.
- Triggers (FR-1.1/1.2/1.3, middle-click / Alt+backtick) and Esc (FR-1.4)
  are global-hook concerns and live in ``hooks.py`` (M5); this module
  only reacts to clicks that land on itself/its children, per the note
  above.
- Clipboard copying is delegated to an injected ``on_copy`` callback so
  this module has no dependency on the real clipboard backend
  (``clipboard_service.py``, M5); tests inject a stub.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QLabel, QPushButton, QWidget

from pastewheel import geometry
from pastewheel.state import WheelState

CENTER_DOT_DIAMETER = 10
POWER_TOOLTIP = "Quit PasteWheel"
GEAR_TOOLTIP = "Settings"

# Visual distinction between clipboard and expand buttons (not SPEC-mandated;
# user-requested UX enhancement): expand buttons get a dashed border plus a
# small "+" corner glyph; clipboard/power/gear/"+" buttons stay solid-border,
# no glyph.
EXPAND_GLYPH_DIAMETER = 16


def _find_button(buttons: list[dict[str, Any]], button_id: str) -> dict[str, Any] | None:
    """Find a button dict by id in a (non-recursive) list of siblings."""
    for button in buttons:
        if button.get("id") == button_id:
            return button
    return None


class WheelButton(QPushButton):
    """A single circular wheel button (clipboard, expand, power, gear, +).

    Expand buttons are visually distinguished from clipboard (and
    power/gear/"+") buttons: a dashed border instead of a solid one, plus a
    small "+" glyph badge in the top-right corner indicating expansion.
    """

    def __init__(
        self,
        parent: QWidget,
        diameter: int = geometry.BUTTON_DIAMETER,
        is_expand: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setFixedSize(diameter, diameter)
        self.setFocusPolicy(Qt.NoFocus)
        border_style = "dashed" if is_expand else "solid"
        self.setStyleSheet(
            f"QPushButton {{ border-radius: {diameter // 2}px; "
            "background-color: rgba(60, 60, 60, 220); color: white; "
            f"border: 1px {border_style} rgba(255, 255, 255, 60); }}"
            "QPushButton:hover { background-color: rgba(90, 90, 90, 230); }"
        )
        self._expand_glyph: QLabel | None = None
        if is_expand:
            glyph = QLabel("+", self)
            glyph.setObjectName("expand_glyph")
            glyph.setFixedSize(EXPAND_GLYPH_DIAMETER, EXPAND_GLYPH_DIAMETER)
            glyph.setAlignment(Qt.AlignCenter)
            glyph.setAttribute(Qt.WA_TransparentForMouseEvents)
            glyph.setFocusPolicy(Qt.NoFocus)
            glyph.setStyleSheet(
                f"QLabel {{ border-radius: {EXPAND_GLYPH_DIAMETER // 2}px; "
                "background-color: rgba(230, 230, 230, 235); color: black; "
                "font-weight: bold; border: 1px solid rgba(0, 0, 0, 120); }}"
            )
            # Anchor to the top-right corner of the circular button.
            glyph.move(diameter - EXPAND_GLYPH_DIAMETER, 0)
            glyph.show()
            self._expand_glyph = glyph


class WheelWindow(QWidget):
    """Frameless, translucent, always-on-top, no-focus radial wheel.

    Owns a :class:`~pastewheel.state.WheelState` and renders buttons from a
    button-tree config (see §9.1) around whatever center point ``show_at``
    is called with. Clipboard copying and settings-opening are delegated
    to injected callbacks (``on_copy``, ``on_open_settings``) so this
    module stays decoupled from ``clipboard_service.py``/``settings_window.py``
    (both introduced in later milestones).
    """

    def __init__(
        self,
        on_copy: Callable[[str], None] | None = None,
        on_open_settings: Callable[[], None] | None = None,
        on_quit: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        # FR-1.5: the wheel never takes keyboard focus; underlying apps
        # keep focus. WindowDoesNotAcceptFocus + Qt.NoFocus + the
        # show-without-activating attribute together ensure this holds
        # both at the Qt level and (per Windows) at the WM_ACTIVATE level.
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.NoFocus)

        self._on_copy = on_copy
        self._on_open_settings = on_open_settings
        self._on_quit = on_quit

        self.state = WheelState()
        self.buttons: list[dict[str, Any]] = []
        self._center: tuple[float, float] = (0.0, 0.0)

        self._center_widget: QWidget | None = None
        self._power_button: WheelButton | None = None
        self._gear_button: WheelButton | None = None
        self._ring_widgets: dict[int, list[WheelButton]] = {1: [], 2: [], 3: []}

    # --- Public API -------------------------------------------------

    def set_buttons(self, buttons: list[dict[str, Any]]) -> None:
        """Set the L1 button tree (see §9.1 schema) and re-render."""
        self.buttons = buttons
        if self.state.is_visible:
            self._rebuild()

    def show_at(self, center: QPoint, screen_rect: tuple[int, int, int, int] | None = None) -> None:
        """Show the wheel centered on ``center`` (FR-1.1/1.2), clamped to
        the pointer's monitor (FR-2.5).

        ``screen_rect`` is ``(left, top, right, bottom)``; when omitted it
        is looked up from the real screen at ``center`` via Qt.
        """
        if screen_rect is None:
            screen_rect = self._screen_rect_at(center)

        max_level = self._max_visible_ring_level_for_current_buttons()
        outer_radius = geometry.wheel_outer_radius(max_level)
        clamped = geometry.clamp_center_to_screen(
            (center.x(), center.y()), outer_radius, screen_rect
        )
        self._center = clamped

        left, top, right, bottom = screen_rect
        self.setGeometry(left, top, right - left, bottom - top)

        self.state.show()
        self._rebuild()
        self.show()

    def hide_wheel(self) -> None:
        """Hide the wheel and reset all expand toggles (FR-3.4)."""
        self.state.hide()
        self._rebuild()
        self.hide()

    # --- Internal: geometry / screen lookup --------------------------

    def _screen_rect_at(self, point: QPoint) -> tuple[int, int, int, int]:
        screen = QGuiApplication.screenAt(point) or QGuiApplication.primaryScreen()
        geo = screen.geometry()
        return (geo.left(), geo.top(), geo.right() + 1, geo.bottom() + 1)

    def _max_visible_ring_level_for_current_buttons(self) -> int:
        """Highest ring level that *could* be visible for outer-radius sizing.

        Uses the static button tree (not the live toggle state) so the
        window is always sized generously enough for FR-2.5 clamping even
        immediately after a fresh ``show()`` before any expand is toggled.
        """
        if any(b.get("type") == "expand" for b in self.buttons):
            for b in self.buttons:
                if b.get("type") == "expand" and any(
                    c.get("type") == "expand" for c in b.get("children", [])
                ):
                    return 3
            return 2
        return 1

    # --- Internal: rendering -----------------------------------------

    def _clear_widgets(self) -> None:
        for widget in (self._center_widget, self._power_button, self._gear_button):
            if widget is not None:
                widget.deleteLater()
        self._center_widget = None
        self._power_button = None
        self._gear_button = None
        for level in (1, 2, 3):
            for widget in self._ring_widgets[level]:
                widget.deleteLater()
            self._ring_widgets[level] = []

    def _to_local(self, point: tuple[float, float]) -> QPoint:
        """Translate a global-coordinate center point to window-local coords."""
        wx, wy = self.x(), self.y()
        return QPoint(round(point[0] - wx), round(point[1] - wy))

    def _place_button(self, button: WheelButton, center_point: tuple[float, float]) -> None:
        local = self._to_local(center_point)
        size = button.width()
        button.move(local.x() - size // 2, local.y() - size // 2)
        button.show()

    def _rebuild(self) -> None:
        """Re-render all buttons/widgets from ``self.buttons`` + ``self.state``.

        Implements FR-2.2 (L1 always visible when shown), FR-2.3
        (power/gear always visible, fixed position), FR-2.6 (first-run
        "+" center when there are zero L1 buttons, else a non-interactive
        dot), and §5/D3 ring visibility + even spacing.
        """
        self._clear_widgets()
        if not self.state.is_visible:
            return

        center = self._center

        self._power_button = self._make_fixed_button(
            geometry.power_button_position(center), "\u23fb", POWER_TOOLTIP, self._handle_power
        )
        self._gear_button = self._make_fixed_button(
            geometry.gear_button_position(center), "\u2699", GEAR_TOOLTIP, self._handle_gear
        )

        if not self.buttons:
            self._center_widget = self._make_fixed_button(
                center, "+", "Settings", self._handle_open_settings
            )
        else:
            dot = QWidget(self)
            dot.setFixedSize(CENTER_DOT_DIAMETER, CENTER_DOT_DIAMETER)
            dot.setStyleSheet(
                f"background-color: rgba(255, 255, 255, 160); "
                f"border-radius: {CENTER_DOT_DIAMETER // 2}px;"
            )
            dot.setAttribute(Qt.WA_TransparentForMouseEvents)
            local = self._to_local(center)
            dot.move(local.x() - CENTER_DOT_DIAMETER // 2, local.y() - CENTER_DOT_DIAMETER // 2)
            dot.show()
            self._center_widget = dot

        self._render_ring(level=1, buttons=self.buttons, center=center)

        if self.state.is_level_visible(2):
            l1_on_id = self.state.on_expand_id(1)
            l1_expand = _find_button(self.buttons, l1_on_id) if l1_on_id else None
            l2_children = l1_expand.get("children", []) if l1_expand else []
            self._render_ring(level=2, buttons=l2_children, center=center)

            if self.state.is_level_visible(3):
                l2_on_id = self.state.on_expand_id(2)
                l2_expand = _find_button(l2_children, l2_on_id) if l2_on_id else None
                l3_children = l2_expand.get("children", []) if l2_expand else []
                self._render_ring(level=3, buttons=l3_children, center=center)

    def _make_fixed_button(
        self,
        position: tuple[float, float],
        label: str,
        tooltip: str,
        handler: Callable[[], None],
    ) -> WheelButton:
        button = WheelButton(self)
        button.setText(label)
        button.setToolTip(tooltip)
        button.setAccessibleName(tooltip)  # FR-2.7: accessible name for UIA tooling
        button.clicked.connect(handler)
        self._place_button(button, position)
        return button

    def _render_ring(
        self, level: int, buttons: list[dict[str, Any]], center: tuple[float, float]
    ) -> None:
        positions = geometry.ring_positions(level, center, len(buttons))
        widgets: list[WheelButton] = []
        for button_data, position in zip(buttons, positions, strict=True):
            widget = self._make_ring_button(level, button_data)
            self._place_button(widget, position)
            widgets.append(widget)
        self._ring_widgets[level] = widgets

    def _make_ring_button(self, level: int, button_data: dict[str, Any]) -> WheelButton:
        button_type = button_data.get("type")
        button = WheelButton(self, is_expand=(button_type == "expand"))
        label = button_data.get("label", "")
        tooltip = button_data.get("tooltip") or label
        button.setText(label)
        button.setToolTip(tooltip)  # FR-2.4: hover tooltip (configured, else label)
        button.setAccessibleName(tooltip)  # FR-2.7
        button_id = button_data.get("id")
        if button_type == "clipboard":
            string = button_data.get("string", "")
            button.clicked.connect(lambda: self._handle_clipboard_click(string))
        elif button_type == "expand":
            button.clicked.connect(lambda: self._handle_expand_click(button_id, level))
        return button

    # --- Internal: click handlers -------------------------------------

    def _handle_clipboard_click(self, string: str) -> None:
        """FR-3.1: copy the string, then hide the wheel (FR-1.4)."""
        if self._on_copy is not None:
            self._on_copy(string)
        self.hide_wheel()

    def _handle_expand_click(self, button_id: str, level: int) -> None:
        """FR-3.2: toggle the expand button's children ring."""
        self.state.toggle_expand(button_id, level)
        self._rebuild()

    def _handle_power(self) -> None:
        """Power click: exits the app (FR-1.4)."""
        self.hide_wheel()
        if self._on_quit is not None:
            self._on_quit()

    def _handle_gear(self) -> None:
        """Gear click: hides the wheel, then opens settings (FR-1.4)."""
        self.hide_wheel()
        self._handle_open_settings()

    def _handle_open_settings(self) -> None:
        if self._on_open_settings is not None:
            self._on_open_settings()

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt override name)
        """Left-click on empty space (in/outside the button cluster, but
        inside this monitor-sized window) closes the wheel (D2, FR-1.4).

        Clicks that land on a button widget are consumed by that widget
        and never reach this handler, so this only fires for genuinely
        empty space.
        """
        if event.button() == Qt.LeftButton:
            self.hide_wheel()
        super().mousePressEvent(event)
