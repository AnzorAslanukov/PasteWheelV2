"""pytest-qt tests for pastewheel.settings_window — FR-5.1-5.10.

Runs headless via QT_QPA_PLATFORM=offscreen (tests/conftest.py, §10).
"""

from __future__ import annotations

from PySide6.QtCore import Qt

from pastewheel.config import default_config
from pastewheel.settings_window import (
    AUTOSTART_DISABLED_NOTE,
    BUTTON_ID_ROLE,
    SettingsWindow,
    count_descendants,
    max_children_for_level,
)
from pastewheel.validation import MAX_L1_BUTTONS, MAX_LEVEL


def _config_with_buttons():
    data = default_config()
    data["buttons"] = [
        {"id": "c1", "type": "clipboard", "label": "TST", "tooltip": "", "string": "Test"},
        {
            "id": "e1",
            "type": "expand",
            "label": "🎯",
            "tooltip": "",
            "children": [
                {"id": "c2", "type": "clipboard", "label": "HI", "tooltip": "", "string": "Hi"}
            ],
        },
    ]
    return data


def _make_window(qtbot, data=None, on_save=None, confirm_delete=None, frozen=None):
    window = SettingsWindow(
        data if data is not None else default_config(),
        on_save=on_save,
        confirm_delete=confirm_delete if confirm_delete is not None else lambda *_: True,
        frozen=frozen,
    )
    qtbot.addWidget(window)
    return window


def _select(window, button_id):
    for i in range(window.tree.topLevelItemCount()):
        top = window.tree.topLevelItem(i)
        stack = [top]
        while stack:
            item = stack.pop()
            if item.data(0, BUTTON_ID_ROLE) == button_id:
                window.tree.setCurrentItem(item)
                return
            stack.extend(item.child(j) for j in range(item.childCount()))
    raise AssertionError(f"button {button_id} not found in tree")


# --- FR-5.1: reused instance, load() resets working copy -----------------


def test_fr_5_1_load_resets_working_copy(qtbot):
    window = _make_window(qtbot, data=default_config())
    window.load(_config_with_buttons())

    assert len(window.data["buttons"]) == 2
    assert window.tree.topLevelItemCount() == 2


# --- FR-5.2: tree shows L1 buttons and nested expand children ------------


def test_fr_5_2_tree_shows_l1_and_nested_children(qtbot):
    window = _make_window(qtbot, data=_config_with_buttons())

    assert window.tree.topLevelItemCount() == 2
    expand_item = window.tree.topLevelItem(1)
    assert expand_item.childCount() == 1
    assert expand_item.child(0).data(0, BUTTON_ID_ROLE) == "c2"


# --- FR-5.3: add L1 (disabled at 8); add child (disabled at limit) -------


def test_fr_5_3_add_l1_button_appends_and_selects(qtbot):
    window = _make_window(qtbot)
    window._on_add_l1_clicked()

    assert len(window.data["buttons"]) == 1
    assert window.tree.topLevelItemCount() == 1
    assert window._selected_id == window.data["buttons"][0]["id"]


def test_fr_5_3_add_l1_disabled_at_max(qtbot):
    data = default_config()
    data["buttons"] = [
        {"id": f"b{i}", "type": "clipboard", "label": "AB", "tooltip": "", "string": "x"}
        for i in range(MAX_L1_BUTTONS)
    ]
    window = _make_window(qtbot, data=data)

    assert window.add_l1_button.isEnabled() is False
    window._on_add_l1_clicked()
    assert len(window.data["buttons"]) == MAX_L1_BUTTONS


def test_fr_5_3_add_child_disabled_at_limit(qtbot):
    data = default_config()
    max_children = max_children_for_level(1)
    data["buttons"] = [
        {
            "id": "e1",
            "type": "expand",
            "label": "🎯",
            "tooltip": "",
            "children": [
                {"id": f"c{i}", "type": "clipboard", "label": "AB", "tooltip": "", "string": "x"}
                for i in range(max_children)
            ],
        }
    ]
    window = _make_window(qtbot, data=data)
    _select(window, "e1")

    assert window.add_child_button.isEnabled() is False
    window._on_add_child_clicked()
    assert len(window.data["buttons"][0]["children"]) == max_children


def test_fr_5_3_add_child_enabled_for_expand_under_limit(qtbot):
    window = _make_window(qtbot, data=_config_with_buttons())
    _select(window, "e1")

    assert window.add_child_button.isEnabled() is True
    window._on_add_child_clicked()
    assert len(window.data["buttons"][1]["children"]) == 2


# --- FR-5.4: per-button editor fields -------------------------------------


def test_fr_5_4_editor_loads_selected_button_fields(qtbot):
    window = _make_window(qtbot, data=_config_with_buttons())
    _select(window, "c1")

    assert window.label_edit.text() == "TST"
    assert window.type_combo.currentData() == "clipboard"
    assert window.string_edit.toPlainText() == "Test"
    assert window.string_edit.isHidden() is False


def test_fr_5_4_editing_label_updates_data_and_tree(qtbot):
    window = _make_window(qtbot, data=_config_with_buttons())
    _select(window, "c1")

    window.label_edit.setText("NEW")

    button = window._selected_button()
    assert button["label"] == "NEW"
    item = window.tree.topLevelItem(0)
    assert "NEW" in item.text(0)


def test_fr_5_4_editing_string_updates_data(qtbot):
    window = _make_window(qtbot, data=_config_with_buttons())
    _select(window, "c1")

    window.string_edit.setPlainText("Updated string")

    assert window._selected_button()["string"] == "Updated string"


def test_fr_5_4_editing_tooltip_updates_data(qtbot):
    window = _make_window(qtbot, data=_config_with_buttons())
    _select(window, "c1")

    window.tooltip_edit.setText("A tip")

    assert window._selected_button()["tooltip"] == "A tip"


def test_fr_5_4_changing_type_to_expand_adds_children_field(qtbot):
    window = _make_window(qtbot, data=_config_with_buttons())
    _select(window, "c1")

    window.type_combo.setCurrentIndex(window.type_combo.findData("expand"))

    button = window._selected_button()
    assert button["type"] == "expand"
    assert button["children"] == []
    assert "string" not in button


def test_fr_5_4_expand_type_disabled_at_l3(qtbot):
    data = default_config()
    data["buttons"] = [
        {
            "id": "e1",
            "type": "expand",
            "label": "🎯",
            "tooltip": "",
            "children": [
                {
                    "id": "e2",
                    "type": "expand",
                    "label": "🎨",
                    "tooltip": "",
                    "children": [
                        {
                            "id": "c3",
                            "type": "clipboard",
                            "label": "AB",
                            "tooltip": "",
                            "string": "x",
                        }
                    ],
                }
            ],
        }
    ]
    window = _make_window(qtbot, data=data)
    _select(window, "c3")

    assert window._selected_level() == MAX_LEVEL
    expand_item = window.type_combo.model().item(window.type_combo.findData("expand"))
    assert expand_item.isEnabled() is False


# --- FR-5.5: validation blocks saving; inline error messages -------------


def test_fr_5_5_save_blocked_by_invalid_label(qtbot):
    saved = []
    data = default_config()
    data["buttons"] = [
        {"id": "c1", "type": "clipboard", "label": "", "tooltip": "", "string": "Test"}
    ]
    window = _make_window(qtbot, data=data, on_save=saved.append)
    _select(window, "c1")

    window._on_save_clicked()

    assert saved == []
    assert window.error_label.text() != ""


def test_fr_5_5_save_blocked_by_empty_clipboard_string(qtbot):
    saved = []
    data = default_config()
    data["buttons"] = [
        {"id": "c1", "type": "clipboard", "label": "AB", "tooltip": "", "string": "   "}
    ]
    window = _make_window(qtbot, data=data, on_save=saved.append)

    errors = window.current_errors()

    assert any("empty" in e.lower() for e in errors)
    window._on_save_clicked()
    assert saved == []


def test_fr_5_5_save_blocked_by_expand_with_zero_children(qtbot):
    data = default_config()
    data["buttons"] = [{"id": "e1", "type": "expand", "label": "🎯", "tooltip": "", "children": []}]
    window = _make_window(qtbot, data=data)

    errors = window.current_errors()

    assert any("child" in e.lower() for e in errors)


def test_fr_5_5_inline_error_shown_for_selected_button(qtbot):
    data = default_config()
    data["buttons"] = [
        {"id": "c1", "type": "clipboard", "label": "TOOLONG", "tooltip": "", "string": "Test"}
    ]
    window = _make_window(qtbot, data=data)
    _select(window, "c1")

    assert "label" in window.error_label.text().lower()


# --- FR-5.6: delete with confirmation; expand warns with descendant count -


def test_fr_5_6_delete_confirmed_removes_button(qtbot):
    window = _make_window(qtbot, data=_config_with_buttons(), confirm_delete=lambda *_: True)
    _select(window, "c1")

    window._on_delete_clicked()

    assert len(window.data["buttons"]) == 1
    assert window.tree.topLevelItemCount() == 1


def test_fr_5_6_delete_cancelled_keeps_button(qtbot):
    window = _make_window(qtbot, data=_config_with_buttons(), confirm_delete=lambda *_: False)
    _select(window, "c1")

    window._on_delete_clicked()

    assert len(window.data["buttons"]) == 2


def test_fr_5_6_deleting_expand_reports_descendant_count(qtbot):
    seen = []
    window = _make_window(
        qtbot,
        data=_config_with_buttons(),
        confirm_delete=lambda label, count: seen.append((label, count)) or True,
    )
    _select(window, "e1")

    window._on_delete_clicked()

    assert seen == [("🎯", 1)]
    assert len(window.data["buttons"]) == 1


def test_fr_5_6_count_descendants_recursive():
    button = {
        "id": "e1",
        "type": "expand",
        "children": [
            {"id": "c1", "type": "clipboard"},
            {
                "id": "e2",
                "type": "expand",
                "children": [{"id": "c2", "type": "clipboard"}, {"id": "c3", "type": "clipboard"}],
            },
        ],
    }
    assert count_descendants(button) == 4


# --- FR-5.7: Save persists (via on_save callback); Cancel discards -------


def test_fr_5_7_save_calls_on_save_with_final_document(qtbot):
    saved = []
    window = _make_window(qtbot, data=default_config(), on_save=saved.append)
    window._on_add_l1_clicked()
    _select(window, window.data["buttons"][0]["id"])
    window.label_edit.setText("AB")
    window.string_edit.setPlainText("hello")

    window._on_save_clicked()

    assert len(saved) == 1
    assert saved[0]["buttons"][0]["label"] == "AB"
    assert saved[0]["buttons"][0]["string"] == "hello"


def test_fr_5_7_save_does_not_mutate_original_via_reference(qtbot):
    saved = []
    original = default_config()
    window = _make_window(qtbot, data=original, on_save=saved.append)
    window._on_add_l1_clicked()
    button = window.data["buttons"][0]
    button["label"] = "AB"
    button["string"] = "hi"

    window._on_save_clicked()

    assert saved[0] is not window.data
    assert original["buttons"] == []  # the caller's original dict is untouched


def test_fr_5_7_cancel_does_not_call_on_save(qtbot):
    saved = []
    window = _make_window(qtbot, data=_config_with_buttons(), on_save=saved.append)
    _select(window, "c1")
    window.label_edit.setText("CHANGED")

    window._on_cancel_clicked()

    assert saved == []


# --- FR-5.8: autostart toggle; disabled with note when running from source


def test_fr_5_8_autostart_disabled_when_not_frozen(qtbot):
    window = _make_window(qtbot, frozen=False)

    assert window.autostart_checkbox.isEnabled() is False
    assert window.autostart_note_label.text() == AUTOSTART_DISABLED_NOTE


def test_fr_5_8_autostart_enabled_when_frozen(qtbot):
    window = _make_window(qtbot, frozen=True)

    assert window.autostart_checkbox.isEnabled() is True


def test_fr_5_8_autostart_default_off(qtbot):
    window = _make_window(qtbot, frozen=True)

    assert window.autostart_checkbox.isChecked() is False
    assert window.data["settings"]["autostart"] is False


def test_fr_5_8_toggling_autostart_updates_data(qtbot):
    window = _make_window(qtbot, frozen=True)

    window.autostart_checkbox.setChecked(True)

    assert window.data["settings"]["autostart"] is True


# --- FR-5.9: normal window behavior (not frameless/always-on-top) --------


def test_fr_5_9_settings_window_is_a_normal_resizable_window(qtbot):
    window = _make_window(qtbot)

    flags = window.windowFlags()
    assert not bool(flags & Qt.FramelessWindowHint)
    assert not bool(flags & Qt.WindowStaysOnTopHint)
    assert window.isWindow()


# --- FR-5.10: theme selector System/Dark/Light, default System -----------


def test_fr_5_10_theme_default_system(qtbot):
    window = _make_window(qtbot)

    assert window.theme_combo.currentData() == "system"


def test_fr_5_10_theme_options_present(qtbot):
    window = _make_window(qtbot)

    values = {window.theme_combo.itemData(i) for i in range(window.theme_combo.count())}
    assert values == {"system", "dark", "light"}


def test_fr_5_10_selecting_theme_updates_data_and_persists_on_save(qtbot):
    saved = []
    window = _make_window(qtbot, on_save=saved.append)

    window.theme_combo.setCurrentIndex(window.theme_combo.findData("dark"))
    window._on_save_clicked()

    assert window.data["settings"]["theme"] == "dark"
    assert saved[0]["settings"]["theme"] == "dark"


def test_fr_5_10_loading_existing_theme_selects_correct_combo_item(qtbot):
    data = default_config()
    data["settings"]["theme"] = "light"

    window = _make_window(qtbot, data=data)

    assert window.theme_combo.currentData() == "light"
