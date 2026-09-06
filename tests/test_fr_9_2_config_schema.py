"""Tests for pastewheel.validation aggregate/schema validators (§9.2)."""

from __future__ import annotations

from pastewheel import validation


def _clipboard_button(label="TST", string="Test", **overrides):
    button = {
        "id": "3f9c",
        "type": "clipboard",
        "label": label,
        "tooltip": "Inserts test text",
        "string": string,
    }
    button.update(overrides)
    return button


def _expand_button(children=None, **overrides):
    if children is None:
        children = [_clipboard_button(label="HI", string="Hello,", id="b2e4")]
    button = {
        "id": "8ad1",
        "type": "expand",
        "label": "🎯",
        "tooltip": "Email snippets",
        "children": children,
    }
    button.update(overrides)
    return button


def _valid_config():
    return {
        "schema_version": 1,
        "settings": {"autostart": False, "theme": "system"},
        "buttons": [_clipboard_button(), _expand_button()],
    }


# --- §9.2: a fully valid document round-trips clean ----------------------


def test_fr_9_2_example_config_from_spec_is_valid():
    assert validation.validate_config(_valid_config()) == []


# --- §9.2: unknown fields rejected on load --------------------------------


def test_fr_9_2_unknown_top_level_field_is_rejected():
    data = _valid_config()
    data["extra"] = True
    assert validation.validate_config(data) != []


def test_fr_9_2_unknown_button_field_is_rejected():
    data = _valid_config()
    data["buttons"][0]["unexpected"] = "x"
    assert validation.validate_config(data) != []


def test_fr_9_2_unknown_settings_field_is_rejected():
    data = _valid_config()
    data["settings"]["extra"] = 1
    assert validation.validate_config(data) != []


# --- §9.2: children present iff type=expand -------------------------------


def test_fr_9_2_clipboard_button_with_children_field_is_rejected():
    button = _clipboard_button()
    button["children"] = []
    assert validation.validate_button(button, level=1) != []


def test_fr_9_2_expand_button_missing_children_field_is_rejected():
    button = _expand_button()
    del button["children"]
    assert validation.validate_button(button, level=1) != []


# --- FR-3.3: type=expand forbidden at L3, checked through the tree -------


def test_fr_3_3_expand_button_nested_at_l3_is_rejected():
    data = _valid_config()
    # L1 expand -> L2 expand -> L3 expand (forbidden: an expand button
    # living three levels deep, at L3, must be rejected).
    l3_expand = _expand_button(id="l3", children=[_clipboard_button(id="l4")])
    l2_expand = _expand_button(id="l2", children=[l3_expand])
    l1_expand = _expand_button(id="l1", children=[l2_expand])
    data["buttons"] = [l1_expand]
    errors = validation.validate_config(data)
    assert errors != []


def test_fr_9_2_l1_array_over_8_is_rejected():
    data = _valid_config()
    data["buttons"] = [_clipboard_button(id=str(i)) for i in range(9)]
    assert validation.validate_config(data) != []


def test_fr_9_2_schema_version_missing_is_rejected():
    data = _valid_config()
    del data["schema_version"]
    assert validation.validate_config(data) != []


def test_fr_9_2_config_not_a_dict_is_rejected():
    assert validation.validate_config([1, 2, 3]) != []


def test_fr_9_2_button_missing_id_is_rejected():
    button = _clipboard_button()
    del button["id"]
    assert validation.validate_button(button, level=1) != []


def test_fr_9_2_validate_button_tree_recurses_into_grandchildren():
    grandchild = _clipboard_button(id="gc", label="TOOLONGLABEL")
    child = _expand_button(id="c", children=[grandchild])
    top = _expand_button(id="top", children=[child])
    errors = validation.validate_button_tree(top, level=1)
    assert errors != []
