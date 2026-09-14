"""pytest-qt tests for pastewheel.wheel_window — FR-1.4-1.5, FR-2.2-2.6, FR-3.1.

Runs headless via QT_QPA_PLATFORM=offscreen (set in tests/conftest.py, per
SPEC §10). Uses qtbot (pytest-qt) to drive real Qt widgets/events without
a real desktop.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from pastewheel.wheel_window import GEAR_TOOLTIP, POWER_TOOLTIP, WheelWindow

SCREEN_RECT = (0, 0, 1920, 1080)
CENTER = QPoint(960, 540)


def _clipboard_button(button_id="c1", label="TST", string="Test"):
    return {"id": button_id, "type": "clipboard", "label": label, "tooltip": "", "string": string}


def _expand_button(button_id="e1", label="🎯", children=None):
    if children is None:
        children = [_clipboard_button("c2", "HI", "Hello,")]
    return {"id": button_id, "type": "expand", "label": label, "tooltip": "", "children": children}


def _make_window(qtbot, on_copy=None, on_open_settings=None, on_quit=None):
    window = WheelWindow(on_copy=on_copy, on_open_settings=on_open_settings, on_quit=on_quit)
    qtbot.addWidget(window)
    return window


# --- FR-1.5: the wheel never takes keyboard focus ------------------------


def test_fr_1_5_wheel_window_has_no_focus_policy(qtbot):
    window = _make_window(qtbot)
    assert window.focusPolicy() == Qt.NoFocus


def test_fr_1_5_wheel_window_does_not_accept_focus_flag(qtbot):
    window = _make_window(qtbot)
    assert bool(window.windowFlags() & Qt.WindowDoesNotAcceptFocus)


def test_fr_1_5_wheel_buttons_have_no_focus_policy(qtbot):
    window = _make_window(qtbot)
    window.set_buttons([_clipboard_button()])
    window.show_at(CENTER, SCREEN_RECT)
    for button in window._ring_widgets[1]:
        assert button.focusPolicy() == Qt.NoFocus


# --- Window chrome: frameless, translucent, always-on-top ---------------


def test_wheel_window_is_frameless_translucent_always_on_top(qtbot):
    window = _make_window(qtbot)
    flags = window.windowFlags()
    assert bool(flags & Qt.FramelessWindowHint)
    assert bool(flags & Qt.WindowStaysOnTopHint)
    assert window.testAttribute(Qt.WA_TranslucentBackground)


# --- FR-2.2: L1 buttons always visible when the wheel is shown ----------


def test_fr_2_2_l1_buttons_visible_when_wheel_shown(qtbot):
    window = _make_window(qtbot)
    window.set_buttons([_clipboard_button(), _clipboard_button("c2", "AB", "ab")])
    window.show_at(CENTER, SCREEN_RECT)

    assert len(window._ring_widgets[1]) == 2
    for button in window._ring_widgets[1]:
        assert button.isVisible()


def test_fr_2_2_l1_buttons_cleared_when_wheel_hidden(qtbot):
    window = _make_window(qtbot)
    window.set_buttons([_clipboard_button()])
    window.show_at(CENTER, SCREEN_RECT)
    window.hide_wheel()

    assert window._ring_widgets[1] == []


# --- FR-2.3: power/gear fixed positions, visible in every state --------


def test_fr_2_3_power_and_gear_visible_with_zero_l1_buttons(qtbot):
    window = _make_window(qtbot)
    window.set_buttons([])
    window.show_at(CENTER, SCREEN_RECT)

    assert window._power_button is not None
    assert window._gear_button is not None
    assert window._power_button.isVisible()
    assert window._gear_button.isVisible()


def test_fr_2_3_power_and_gear_tooltips(qtbot):
    window = _make_window(qtbot)
    window.set_buttons([_clipboard_button()])
    window.show_at(CENTER, SCREEN_RECT)

    assert window._power_button.toolTip() == POWER_TOOLTIP
    assert window._gear_button.toolTip() == GEAR_TOOLTIP


def test_fr_2_3_power_gear_positions_fixed_regardless_of_l2_visibility(qtbot):
    window = _make_window(qtbot)
    window.set_buttons([_expand_button()])
    window.show_at(CENTER, SCREEN_RECT)
    pos_before = window._power_button.pos()

    window._handle_expand_click("e1", level=1)  # opens L2

    pos_after = window._power_button.pos()
    assert pos_before == pos_after


# --- FR-2.4: labels + tooltip fallback to label --------------------------


def test_fr_2_4_button_label_is_rendered(qtbot):
    window = _make_window(qtbot)
    window.set_buttons([_clipboard_button(label="TST")])
    window.show_at(CENTER, SCREEN_RECT)

    assert window._ring_widgets[1][0].text() == "TST"


def test_fr_2_4_tooltip_falls_back_to_label_when_not_configured(qtbot):
    window = _make_window(qtbot)
    window.set_buttons([_clipboard_button(label="TST")])
    window.show_at(CENTER, SCREEN_RECT)

    assert window._ring_widgets[1][0].toolTip() == "TST"


def test_fr_2_4_configured_tooltip_takes_priority(qtbot):
    window = _make_window(qtbot)
    button_data = _clipboard_button(label="TST")
    button_data["tooltip"] = "Custom tooltip"
    window.set_buttons([button_data])
    window.show_at(CENTER, SCREEN_RECT)

    assert window._ring_widgets[1][0].toolTip() == "Custom tooltip"


# --- Button type visual distinction: dashed border + "+" corner glyph ---
# (User-requested UX enhancement, not tied to a specific FR id.)


def test_clipboard_button_has_solid_border_and_no_glyph(qtbot):
    window = _make_window(qtbot)
    window.set_buttons([_clipboard_button()])
    window.show_at(CENTER, SCREEN_RECT)

    button = window._ring_widgets[1][0]
    assert "solid" in button.styleSheet()
    assert "dashed" not in button.styleSheet()
    assert button._expand_glyph is None
    assert button.findChild(QWidget, "expand_glyph") is None


def test_expand_button_has_dashed_border_and_plus_glyph(qtbot):
    window = _make_window(qtbot)
    window.set_buttons([_expand_button()])
    window.show_at(CENTER, SCREEN_RECT)

    button = window._ring_widgets[1][0]
    assert "dashed" in button.styleSheet()
    assert button._expand_glyph is not None
    assert button._expand_glyph.text() == "+"
    assert button._expand_glyph.isVisible()


def test_expand_glyph_is_transparent_for_mouse_events(qtbot):
    """The glyph must not intercept clicks meant for the expand button."""
    window = _make_window(qtbot)
    window.set_buttons([_expand_button()])
    window.show_at(CENTER, SCREEN_RECT)

    glyph = window._ring_widgets[1][0]._expand_glyph
    assert glyph.testAttribute(Qt.WA_TransparentForMouseEvents)


def test_expand_button_click_still_works_with_glyph_present(qtbot):
    """Sanity check: adding the glyph doesn't break FR-3.2 expand toggling."""
    window = _make_window(qtbot)
    window.set_buttons([_expand_button()])
    window.show_at(CENTER, SCREEN_RECT)

    QTest.mouseClick(window._ring_widgets[1][0], Qt.LeftButton)

    assert window.state.is_expand_on("e1", level=1) is True


def test_power_gear_and_plus_buttons_have_solid_border_and_no_glyph(qtbot):
    window = _make_window(qtbot)
    window.set_buttons([])
    window.show_at(CENTER, SCREEN_RECT)

    for button in (window._power_button, window._gear_button, window._center_widget):
        assert "solid" in button.styleSheet()
        assert "dashed" not in button.styleSheet()
        assert button._expand_glyph is None


def test_l3_clipboard_only_children_have_solid_border_and_no_glyph(qtbot):
    """FR-3.3: L3 is clipboard-only, so no L3 button should ever be dashed."""
    window = _make_window(qtbot)
    l3_child = _clipboard_button("c3", "OK", "ok")
    l2_expand = _expand_button("e2", "🔧", children=[l3_child])
    window.set_buttons([_expand_button(children=[l2_expand])])
    window.show_at(CENTER, SCREEN_RECT)

    QTest.mouseClick(window._ring_widgets[1][0], Qt.LeftButton)  # open L2
    QTest.mouseClick(window._ring_widgets[2][0], Qt.LeftButton)  # open L3

    l3_button = window._ring_widgets[3][0]
    assert "solid" in l3_button.styleSheet()
    assert l3_button._expand_glyph is None


# --- FR-2.6: first run (zero L1 buttons) shows only "+" and power/gear --


def test_fr_2_6_zero_l1_buttons_shows_plus_button(qtbot):
    window = _make_window(qtbot)
    window.set_buttons([])
    window.show_at(CENTER, SCREEN_RECT)

    assert window._center_widget is not None
    assert window._center_widget.text() == "+"
    assert window._ring_widgets[1] == []


def test_fr_2_6_plus_button_opens_settings(qtbot):
    calls = []
    window = _make_window(qtbot, on_open_settings=lambda: calls.append(True))
    window.set_buttons([])
    window.show_at(CENTER, SCREEN_RECT)

    QTest.mouseClick(window._center_widget, Qt.LeftButton)

    assert calls == [True]


def test_non_first_run_shows_non_interactive_dot_not_plus(qtbot):
    window = _make_window(qtbot)
    window.set_buttons([_clipboard_button()])
    window.show_at(CENTER, SCREEN_RECT)

    assert not isinstance(window._center_widget, type(window._power_button))
    assert window._center_widget.testAttribute(Qt.WA_TransparentForMouseEvents)


# --- FR-2.7: accessible names --------------------------------------------


def test_fr_2_7_buttons_expose_accessible_names(qtbot):
    window = _make_window(qtbot)
    window.set_buttons([_clipboard_button(label="TST")])
    window.show_at(CENTER, SCREEN_RECT)

    assert window._ring_widgets[1][0].accessibleName() == "TST"
    assert window._power_button.accessibleName() == POWER_TOOLTIP
    assert window._gear_button.accessibleName() == GEAR_TOOLTIP


# --- FR-3.1: clipboard button click copies, then hides -------------------


def test_fr_3_1_clipboard_click_copies_string(qtbot):
    copied = []
    window = _make_window(qtbot, on_copy=copied.append)
    window.set_buttons([_clipboard_button(string="Hello, world!")])
    window.show_at(CENTER, SCREEN_RECT)

    QTest.mouseClick(window._ring_widgets[1][0], Qt.LeftButton)

    assert copied == ["Hello, world!"]


def test_fr_3_1_clipboard_click_hides_wheel(qtbot):
    window = _make_window(qtbot)
    window.set_buttons([_clipboard_button()])
    window.show_at(CENTER, SCREEN_RECT)

    QTest.mouseClick(window._ring_widgets[1][0], Qt.LeftButton)

    assert window.state.is_visible is False
    assert not window.isVisible()


# --- FR-1.4: hide conditions ----------------------------------------------


def test_fr_1_4_gear_click_hides_and_opens_settings(qtbot):
    calls = []
    window = _make_window(qtbot, on_open_settings=lambda: calls.append(True))
    window.set_buttons([_clipboard_button()])
    window.show_at(CENTER, SCREEN_RECT)

    QTest.mouseClick(window._gear_button, Qt.LeftButton)

    assert window.state.is_visible is False
    assert calls == [True]


def test_fr_1_4_power_click_hides_and_quits(qtbot):
    calls = []
    window = _make_window(qtbot, on_quit=lambda: calls.append(True))
    window.set_buttons([_clipboard_button()])
    window.show_at(CENTER, SCREEN_RECT)

    QTest.mouseClick(window._power_button, Qt.LeftButton)

    assert window.state.is_visible is False
    assert calls == [True]


def test_fr_1_4_d2_left_click_on_empty_space_hides_wheel(qtbot):
    window = _make_window(qtbot)
    window.set_buttons([_clipboard_button()])
    window.show_at(CENTER, SCREEN_RECT)

    # Click somewhere far from any button (top-left corner of the window).
    QTest.mouseClick(window, Qt.LeftButton, pos=QPoint(2, 2))

    assert window.state.is_visible is False


def test_fr_1_4_expand_click_does_not_hide_wheel(qtbot):
    window = _make_window(qtbot)
    window.set_buttons([_expand_button()])
    window.show_at(CENTER, SCREEN_RECT)

    QTest.mouseClick(window._ring_widgets[1][0], Qt.LeftButton)

    assert window.state.is_visible is True
    assert window.state.is_expand_on("e1", level=1) is True


def test_fr_3_2_expand_click_shows_l2_children(qtbot):
    window = _make_window(qtbot)
    window.set_buttons([_expand_button()])
    window.show_at(CENTER, SCREEN_RECT)

    QTest.mouseClick(window._ring_widgets[1][0], Qt.LeftButton)

    assert len(window._ring_widgets[2]) == 1
    assert window._ring_widgets[2][0].text() == "HI"


def test_fr_3_2_second_expand_click_hides_l2_children(qtbot):
    window = _make_window(qtbot)
    window.set_buttons([_expand_button()])
    window.show_at(CENTER, SCREEN_RECT)

    QTest.mouseClick(window._ring_widgets[1][0], Qt.LeftButton)
    QTest.mouseClick(window._ring_widgets[1][0], Qt.LeftButton)

    assert window._ring_widgets[2] == []


# --- FR-3.4: toggles reset to OFF when the wheel hides -------------------


def test_fr_3_4_reopening_wheel_resets_expand_toggles(qtbot):
    window = _make_window(qtbot)
    window.set_buttons([_expand_button()])
    window.show_at(CENTER, SCREEN_RECT)
    QTest.mouseClick(window._ring_widgets[1][0], Qt.LeftButton)  # toggle ON
    window.hide_wheel()

    window.show_at(CENTER, SCREEN_RECT)

    assert window.state.is_expand_on("e1", level=1) is False
    assert window._ring_widgets[2] == []


# --- FR-2.5: wheel is clamped to the pointer's monitor -------------------


def test_fr_2_5_wheel_clamped_near_screen_edge(qtbot):
    window = _make_window(qtbot)
    window.set_buttons([_clipboard_button()])
    window.show_at(QPoint(2, 2), SCREEN_RECT)

    # Every L1 button center must stay within the screen bounds.
    for button in window._ring_widgets[1]:
        global_pos = window.pos() + button.pos() + QPoint(
            button.width() // 2, button.height() // 2
        )
        assert 0 <= global_pos.x() <= SCREEN_RECT[2]
        assert 0 <= global_pos.y() <= SCREEN_RECT[3]
