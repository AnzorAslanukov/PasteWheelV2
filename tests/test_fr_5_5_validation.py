"""Tests for pastewheel.validation — FR-5.5 and §9.2 validation rules."""

from __future__ import annotations

from pastewheel import validation

# --- FR-5.5 / §9.2: label must be a single emoji or 1-3 characters ------


def test_fr_5_5_label_single_char_is_valid():
    assert validation.validate_label("A") is None


def test_fr_5_5_label_three_chars_is_valid():
    assert validation.validate_label("TST") is None


def test_fr_5_5_label_single_emoji_is_valid():
    assert validation.validate_label("🎯") is None


def test_fr_5_5_label_zwj_emoji_sequence_counts_as_one_character():
    family_emoji = "\U0001F468\u200D\U0001F469\u200D\U0001F467\u200D\U0001F466"
    assert validation.validate_label(family_emoji) is None


def test_fr_5_5_label_empty_is_invalid():
    assert validation.validate_label("") is not None


def test_fr_5_5_label_four_chars_is_invalid():
    assert validation.validate_label("TEST") is not None


def test_fr_5_5_label_non_string_is_invalid():
    assert validation.validate_label(None) is not None
    assert validation.validate_label(123) is not None


# --- FR-5.5 / §9.2: clipboard string non-empty (trimmed) <=10,000 chars -


def test_fr_5_5_string_non_empty_is_valid():
    assert validation.validate_string("Hello,") is None


def test_fr_5_5_string_whitespace_only_is_invalid():
    assert validation.validate_string("   \t\n  ") is not None


def test_fr_5_5_string_empty_is_invalid():
    assert validation.validate_string("") is not None


def test_fr_5_5_string_exactly_10000_chars_is_valid():
    assert validation.validate_string("a" * 10_000) is None


def test_fr_5_5_string_over_10000_chars_is_invalid():
    assert validation.validate_string("a" * 10_001) is not None


def test_fr_5_5_string_trims_whitespace_before_length_check():
    padded = " " * 5 + "a" * 10_000 + " " * 5
    assert validation.validate_string(padded) is None


def test_fr_5_5_string_non_string_is_invalid():
    assert validation.validate_string(None) is not None


# --- FR-5.5 / FR-3.5: expand buttons require >=1 child; count limits ----


def test_fr_5_5_expand_requires_at_least_one_child():
    assert validation.validate_children_count(1, []) is not None


def test_fr_3_5_expand_from_l1_allows_up_to_16_children():
    children = [{"id": str(i)} for i in range(16)]
    assert validation.validate_children_count(1, children) is None


def test_fr_3_5_expand_from_l1_rejects_more_than_16_children():
    children = [{"id": str(i)} for i in range(17)]
    assert validation.validate_children_count(1, children) is not None


def test_fr_3_5_expand_from_l2_allows_up_to_32_children():
    children = [{"id": str(i)} for i in range(32)]
    assert validation.validate_children_count(2, children) is None


def test_fr_3_5_expand_from_l2_rejects_more_than_32_children():
    children = [{"id": str(i)} for i in range(33)]
    assert validation.validate_children_count(2, children) is not None


def test_fr_5_5_children_not_a_list_is_invalid():
    assert validation.validate_children_count(1, "not-a-list") is not None


# --- FR-5.5 / FR-3.3: L3 cannot be expand --------------------------------


def test_fr_3_3_l3_button_cannot_be_expand_type():
    assert validation.validate_button_type("expand", level=3) is not None


def test_fr_3_3_l1_and_l2_buttons_can_be_expand_type():
    assert validation.validate_button_type("expand", level=1) is None
    assert validation.validate_button_type("expand", level=2) is None


def test_fr_3_3_clipboard_type_valid_at_every_level():
    for level in (1, 2, 3):
        assert validation.validate_button_type("clipboard", level=level) is None


def test_fr_5_5_button_type_must_be_clipboard_or_expand():
    assert validation.validate_button_type("bogus", level=1) is not None


# --- §9.2: settings.theme in {system, dark, light} -----------------------


def test_fr_5_10_theme_system_dark_light_are_valid():
    assert validation.validate_theme("system") is None
    assert validation.validate_theme("dark") is None
    assert validation.validate_theme("light") is None


def test_fr_5_10_theme_invalid_value_is_rejected():
    assert validation.validate_theme("purple") is not None
    assert validation.validate_theme(None) is not None


# --- §9.2: L1 array <=8; unknown fields rejected -------------------------


def test_fr_2_1_l1_array_of_8_is_valid():
    buttons = [{"id": str(i)} for i in range(8)]
    assert validation.validate_l1_count(buttons) is None


def test_fr_2_1_l1_array_of_9_is_invalid():
    buttons = [{"id": str(i)} for i in range(9)]
    assert validation.validate_l1_count(buttons) is not None


def test_fr_2_1_l1_not_a_list_is_invalid():
    assert validation.validate_l1_count("not-a-list") is not None
