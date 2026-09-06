"""Tests for pastewheel.state — wheel FSM & expand toggles (§5, FR-3.x)."""

from __future__ import annotations

import pytest

from pastewheel.state import WheelPhase, WheelState

# --- Wheel FSM: HIDDEN <-> VISIBLE (§5) ----------------------------------


def test_fr_1_1_show_transitions_hidden_to_visible():
    state = WheelState()
    assert state.phase is WheelPhase.HIDDEN
    state.show()
    assert state.phase is WheelPhase.VISIBLE
    assert state.is_visible is True


def test_fr_1_4_hide_transitions_visible_to_hidden():
    state = WheelState()
    state.show()
    state.hide()
    assert state.phase is WheelPhase.HIDDEN
    assert state.is_visible is False


def test_fr_1_2_toggle_flips_between_hidden_and_visible():
    state = WheelState()
    state.toggle()
    assert state.is_visible is True
    state.toggle()
    assert state.is_visible is False


# --- FR-3.2: expand button click toggles its children ring --------------


def test_fr_3_2_toggle_expand_turns_on_and_returns_true():
    state = WheelState()
    state.show()
    result = state.toggle_expand("a", level=1)
    assert result is True
    assert state.is_expand_on("a", level=1) is True


def test_fr_3_2_toggle_expand_again_turns_off_and_returns_false():
    state = WheelState()
    state.show()
    state.toggle_expand("a", level=1)
    result = state.toggle_expand("a", level=1)
    assert result is False
    assert state.is_expand_on("a", level=1) is False


# --- D1: only one expand per level may be ON; sibling exclusivity -------


def test_d1_turning_on_a_sibling_turns_off_the_previous_one():
    state = WheelState()
    state.show()
    state.toggle_expand("a", level=1)
    state.toggle_expand("b", level=1)

    assert state.is_expand_on("a", level=1) is False
    assert state.is_expand_on("b", level=1) is True
    assert state.on_expand_id(1) == "b"


def test_d1_levels_are_independent_of_each_other():
    state = WheelState()
    state.show()
    state.toggle_expand("a", level=1)
    state.toggle_expand("x", level=2)

    assert state.is_expand_on("a", level=1) is True
    assert state.is_expand_on("x", level=2) is True


def test_fr_3_3_expand_toggle_rejects_level_3():
    state = WheelState()
    state.show()
    with pytest.raises(ValueError):
        state.toggle_expand("z", level=3)


# --- §5: L2 visible iff some L1 expand ON; L3 iff some visible L2 ON ----


def test_fr_2_2_l1_always_visible_when_wheel_visible():
    state = WheelState()
    state.show()
    assert state.is_level_visible(1) is True


def test_l1_not_visible_when_wheel_hidden():
    state = WheelState()
    assert state.is_level_visible(1) is False


def test_l2_not_visible_when_no_l1_expand_is_on():
    state = WheelState()
    state.show()
    assert state.is_level_visible(2) is False


def test_l2_visible_when_an_l1_expand_is_on():
    state = WheelState()
    state.show()
    state.toggle_expand("a", level=1)
    assert state.is_level_visible(2) is True


def test_l3_not_visible_when_no_l2_expand_is_on_even_if_l2_visible():
    state = WheelState()
    state.show()
    state.toggle_expand("a", level=1)
    assert state.is_level_visible(2) is True
    assert state.is_level_visible(3) is False


def test_l3_visible_when_l2_expand_is_on_under_a_visible_l2():
    state = WheelState()
    state.show()
    state.toggle_expand("a", level=1)
    state.toggle_expand("x", level=2)
    assert state.is_level_visible(3) is True


def test_l3_not_visible_if_l2_expand_on_but_l1_expand_off():
    """An L2 expand ON with no L1 expand ON means L2 (and thus L3) is hidden."""
    state = WheelState()
    state.show()
    state.toggle_expand("a", level=1)
    state.toggle_expand("x", level=2)
    state.toggle_expand("a", level=1)  # turn L1 expand back off

    assert state.is_level_visible(2) is False
    assert state.is_level_visible(3) is False


def test_is_level_visible_rejects_invalid_level():
    state = WheelState()
    with pytest.raises(ValueError):
        state.is_level_visible(4)


# --- FR-3.4: all expand toggles reset to OFF when the wheel hides -------


def test_fr_3_4_hide_resets_all_expand_toggles():
    state = WheelState()
    state.show()
    state.toggle_expand("a", level=1)
    state.toggle_expand("x", level=2)

    state.hide()

    assert state.on_expand_id(1) is None
    assert state.on_expand_id(2) is None


def test_fr_3_4_toggles_stay_reset_after_showing_again():
    state = WheelState()
    state.show()
    state.toggle_expand("a", level=1)
    state.hide()
    state.show()

    assert state.is_level_visible(2) is False
    assert state.on_expand_id(1) is None
