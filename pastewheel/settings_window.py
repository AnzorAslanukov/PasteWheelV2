"""The settings window: button-tree editor (SPEC §7.5, FR-5.1-5.10).

Design notes (implementer decisions within SPEC's constraints):

- This module owns a *working copy* of the config document (deep-copied on
  construction) so edits are staged in memory; ``Cancel`` simply discards
  the widget (FR-5.7). ``Save`` validates the whole document via
  :func:`pastewheel.validation.validate_config` and, only if it is valid,
  calls the injected ``on_save`` callback with the final document. Actual
  file persistence (``config.save_config``) and pushing the new buttons to
  the live wheel are the caller's responsibility (wired in ``main.py``,
  M5) — this keeps the widget testable without real file I/O, mirroring
  how ``wheel_window.py`` delegates clipboard/quit/settings actions.
- Delete confirmation (FR-5.6) is delegated to an injected
  ``confirm_delete`` callback (``(label, descendant_count) -> bool``) so
  tests never trigger a real blocking ``QMessageBox``. When not supplied,
  a real ``QMessageBox.question`` is used (production default).
- Autostart's actual registry management lives in ``autostart.py`` (M5);
  this widget only edits the ``settings.autostart`` boolean and disables
  the checkbox (with an explanatory note, FR-5.8) when running from
  source, per an injected/detected ``frozen`` flag.
"""

from __future__ import annotations

import copy
import sys
import uuid
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pastewheel import validation
from pastewheel.config import SCHEMA_VERSION

BUTTON_ID_ROLE = Qt.UserRole

AUTOSTART_DISABLED_NOTE = (
    "Autostart is only available in the packaged application; it is"
    " disabled when running from source."
)

TYPE_LABELS = {"clipboard": "Clipboard", "expand": "Expand"}
THEME_LABELS = {"system": "System", "dark": "Dark", "light": "Light"}


def is_frozen() -> bool:
    """True when running from a PyInstaller-packaged executable (FR-5.8)."""
    return bool(getattr(sys, "frozen", False))


def new_button_id() -> str:
    """Generate a fresh unique button id (see the ``id`` field, SPEC §9.1)."""
    return str(uuid.uuid4())


def item_level(item: QTreeWidgetItem) -> int:
    """The ring level (1, 2, or 3) of a tree item, by counting ancestors."""
    level = 1
    parent = item.parent()
    while parent is not None:
        level += 1
        parent = parent.parent()
    return level


def count_descendants(button: dict[str, Any]) -> int:
    """Total number of descendant buttons under ``button`` (FR-5.6)."""
    children = button.get("children") or []
    total = len(children)
    for child in children:
        if isinstance(child, dict):
            total += count_descendants(child)
    return total


def find_item_by_id(root_items: list[QTreeWidgetItem], button_id: str) -> QTreeWidgetItem | None:
    """Depth-first search for the tree item whose stored button id matches."""
    stack = list(root_items)
    while stack:
        item = stack.pop()
        if item.data(0, BUTTON_ID_ROLE) == button_id:
            return item
        stack.extend(item.child(i) for i in range(item.childCount()))
    return None


def find_button_by_id(buttons: list[dict[str, Any]], button_id: str) -> dict[str, Any] | None:
    """Depth-first search of the *data* tree (not the widget tree) by id."""
    for button in buttons:
        if button.get("id") == button_id:
            return button
        found = find_button_by_id(button.get("children") or [], button_id)
        if found is not None:
            return found
    return None


def find_parent_list_and_index(
    buttons: list[dict[str, Any]], button_id: str
) -> tuple[list[dict[str, Any]], int] | None:
    """Find the list containing ``button_id`` and its index within it."""
    for index, button in enumerate(buttons):
        if button.get("id") == button_id:
            return buttons, index
        found = find_parent_list_and_index(button.get("children") or [], button_id)
        if found is not None:
            return found
    return None


def max_children_for_level(level: int) -> int:
    """Max children allowed for an expand button at ``level`` (FR-3.5)."""
    if level == 1:
        return validation.MAX_CHILDREN_OF_L1_EXPAND
    if level == 2:
        return validation.MAX_CHILDREN_OF_L2_EXPAND
    return 0


def _default_confirm_delete(label: str, descendant_count: int) -> bool:
    """Real (blocking) delete confirmation dialog (FR-5.6), production default."""
    message = f"Delete the '{label}' button?"
    if descendant_count > 0:
        message += f" This will also remove {descendant_count} descendant button(s)."
    button = QMessageBox.question(
        None, "Confirm delete", message, QMessageBox.Yes | QMessageBox.No, QMessageBox.No
    )
    return button == QMessageBox.Yes


class SettingsWindow(QWidget):
    """Settings window: button-tree editor + autostart/theme (SPEC §7.5).

    Normal top-level window (taskbar entry, resizable — FR-5.9), unlike
    ``WheelWindow``. Operates on an in-memory *working copy* of the config
    document (``self.data``); nothing touches disk until ``on_save`` fires
    (FR-5.7). One instance is created and reused by the caller (FR-5.1).
    """

    def __init__(
        self,
        data: dict[str, Any],
        on_save: Callable[[dict[str, Any]], None] | None = None,
        confirm_delete: Callable[[str, int], bool] | None = None,
        frozen: bool | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("PasteWheel Settings")
        self.data: dict[str, Any] = copy.deepcopy(data)
        self.data.setdefault("schema_version", SCHEMA_VERSION)
        self.data.setdefault("settings", {"autostart": False, "theme": "system"})
        self.data.setdefault("buttons", [])

        self._on_save = on_save
        self._confirm_delete = confirm_delete or _default_confirm_delete
        self._frozen = is_frozen() if frozen is None else frozen
        self._selected_id: str | None = None
        self._loading_editor = False

        self._build_ui()
        self._populate_tree()
        self._load_editor_for(None, level=1)
        self._update_add_l1_enabled()

    # --- Public API -----------------------------------------------------

    def load(self, data: dict[str, Any]) -> None:
        """Reset the working copy to ``data`` (for reopening, FR-5.1)."""
        self.data = copy.deepcopy(data)
        self.data.setdefault("schema_version", SCHEMA_VERSION)
        self.data.setdefault("settings", {"autostart": False, "theme": "system"})
        self.data.setdefault("buttons", [])
        self._selected_id = None
        self._populate_tree()
        self._load_editor_for(None, level=1)
        self._update_add_l1_enabled()
        self._load_top_level_settings()

    # --- UI construction --------------------------------------------------

    def _build_ui(self) -> None:
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.itemSelectionChanged.connect(self._on_tree_selection_changed)

        self.add_l1_button = QPushButton("Add top-level button")
        self.add_l1_button.clicked.connect(self._on_add_l1_clicked)
        self.add_child_button = QPushButton("Add child")
        self.add_child_button.clicked.connect(self._on_add_child_clicked)
        self.delete_button = QPushButton("Delete")
        self.delete_button.clicked.connect(self._on_delete_clicked)

        tree_buttons = QHBoxLayout()
        tree_buttons.addWidget(self.add_l1_button)
        tree_buttons.addWidget(self.add_child_button)
        tree_buttons.addWidget(self.delete_button)

        left = QVBoxLayout()
        left.addWidget(self.tree)
        left.addLayout(tree_buttons)
        left_widget = QWidget()
        left_widget.setLayout(left)

        right_widget = self._build_editor_panel()

        splitter = QSplitter()
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)

        bottom = self._build_bottom_panel()

        root = QVBoxLayout(self)
        root.addWidget(splitter)
        root.addLayout(bottom)

    def _build_editor_panel(self) -> QWidget:
        self.label_edit = QLineEdit()
        self.label_edit.setAccessibleName("Label")
        self.label_edit.textChanged.connect(self._on_label_changed)

        self.tooltip_edit = QLineEdit()
        self.tooltip_edit.setAccessibleName("Tooltip")
        self.tooltip_edit.textChanged.connect(self._on_tooltip_changed)

        self.type_combo = QComboBox()
        self.type_combo.setAccessibleName("Type")
        self.type_combo.addItem(TYPE_LABELS["clipboard"], "clipboard")
        self.type_combo.addItem(TYPE_LABELS["expand"], "expand")
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)

        self.string_edit = QPlainTextEdit()
        self.string_edit.setAccessibleName("String")
        self.string_edit.textChanged.connect(self._on_string_changed)

        self.children_info_label = QLabel("")
        self.children_info_label.setAccessibleName("Children")

        self.error_label = QLabel("")
        self.error_label.setAccessibleName("Errors")
        self.error_label.setStyleSheet("color: red;")
        self.error_label.setWordWrap(True)

        form = QFormLayout()
        form.addRow("Label", self.label_edit)
        form.addRow("Tooltip", self.tooltip_edit)
        form.addRow("Type", self.type_combo)
        form.addRow("String", self.string_edit)
        form.addRow("Children", self.children_info_label)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(self.error_label)
        layout.addStretch(1)
        widget = QWidget()
        widget.setLayout(layout)
        return widget

    def _build_bottom_panel(self) -> QHBoxLayout:
        self.autostart_checkbox = QCheckBox("Start with Windows")
        self.autostart_checkbox.setAccessibleName("Autostart")
        self.autostart_checkbox.toggled.connect(self._on_autostart_toggled)
        if self._frozen:
            self.autostart_checkbox.setToolTip("Runs PasteWheel automatically at login.")
        else:
            self.autostart_checkbox.setEnabled(False)
            self.autostart_checkbox.setToolTip(AUTOSTART_DISABLED_NOTE)

        self.autostart_note_label = QLabel("" if self._frozen else AUTOSTART_DISABLED_NOTE)
        self.autostart_note_label.setWordWrap(True)

        self.theme_combo = QComboBox()
        self.theme_combo.setAccessibleName("Theme")
        for value, label in THEME_LABELS.items():
            self.theme_combo.addItem(label, value)
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)

        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self._on_save_clicked)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self._on_cancel_clicked)

        self._load_top_level_settings()

        layout = QHBoxLayout()
        layout.addWidget(self.autostart_checkbox)
        layout.addWidget(self.autostart_note_label)
        layout.addWidget(QLabel("Theme:"))
        layout.addWidget(self.theme_combo)
        layout.addStretch(1)
        layout.addWidget(self.save_button)
        layout.addWidget(self.cancel_button)
        return layout

    def _load_top_level_settings(self) -> None:
        settings = self.data.get("settings", {})
        self.autostart_checkbox.blockSignals(True)
        self.autostart_checkbox.setChecked(bool(settings.get("autostart", False)))
        self.autostart_checkbox.blockSignals(False)
        theme = settings.get("theme", "system")
        index = self.theme_combo.findData(theme)
        self.theme_combo.blockSignals(True)
        self.theme_combo.setCurrentIndex(index if index >= 0 else 0)
        self.theme_combo.blockSignals(False)

    # --- Tree population -------------------------------------------------

    def _populate_tree(self) -> None:
        self.tree.blockSignals(True)
        self.tree.clear()
        for button in self.data["buttons"]:
            self._add_tree_item(self.tree.invisibleRootItem(), button)
        self.tree.blockSignals(False)
        self.tree.expandAll()

    def _add_tree_item(self, parent_item: QTreeWidgetItem, button: dict[str, Any]) -> None:
        item = QTreeWidgetItem(parent_item)
        item.setText(0, self._tree_label(button))
        item.setData(0, BUTTON_ID_ROLE, button.get("id"))
        for child in button.get("children") or []:
            self._add_tree_item(item, child)

    @staticmethod
    def _tree_label(button: dict[str, Any]) -> str:
        label = button.get("label", "")
        kind = TYPE_LABELS.get(button.get("type"), button.get("type", ""))
        return f"{label}  ({kind})"

    def _refresh_tree_item_label(self, button_id: str) -> None:
        item = find_item_by_id(
            [self.tree.topLevelItem(i) for i in range(self.tree.topLevelItemCount())], button_id
        )
        button = find_button_by_id(self.data["buttons"], button_id)
        if item is not None and button is not None:
            item.setText(0, self._tree_label(button))

    def _selected_button(self) -> dict[str, Any] | None:
        if self._selected_id is None:
            return None
        return find_button_by_id(self.data["buttons"], self._selected_id)

    def _selected_level(self) -> int:
        items = self.tree.selectedItems()
        if not items:
            return 1
        return item_level(items[0])

    # --- Selection & editor loading ---------------------------------------

    def _on_tree_selection_changed(self) -> None:
        items = self.tree.selectedItems()
        button_id = items[0].data(0, BUTTON_ID_ROLE) if items else None
        level = item_level(items[0]) if items else 1
        self._load_editor_for(button_id, level)
        self._update_add_child_enabled()
        self.delete_button.setEnabled(button_id is not None)

    def _load_editor_for(self, button_id: str | None, level: int) -> None:
        self._selected_id = button_id
        self._loading_editor = True
        button = self._selected_button()
        has_selection = button is not None
        for widget in (self.label_edit, self.tooltip_edit, self.type_combo):
            widget.setEnabled(has_selection)

        if button is None:
            self.label_edit.setText("")
            self.tooltip_edit.setText("")
            self.string_edit.setPlainText("")
            self.string_edit.setVisible(True)
            self.children_info_label.setText("")
            self.error_label.setText("")
            self._loading_editor = False
            return

        self.label_edit.setText(button.get("label", ""))
        self.tooltip_edit.setText(button.get("tooltip", ""))
        button_type = button.get("type", "clipboard")
        self.type_combo.setCurrentIndex(self.type_combo.findData(button_type))
        # FR-5.4: expand disabled as a choice for L3 buttons.
        expand_item_enabled = level < validation.MAX_LEVEL
        self.type_combo.model().item(1).setEnabled(expand_item_enabled)

        is_clipboard = button_type == "clipboard"
        self.string_edit.setVisible(is_clipboard)
        self.string_edit.setPlainText(button.get("string", "") if is_clipboard else "")
        if not is_clipboard:
            children = button.get("children") or []
            self.children_info_label.setText(
                f"{len(children)} child button(s) (edit via the tree on the left)."
            )
        else:
            self.children_info_label.setText("")
        self._loading_editor = False
        self._refresh_errors()

    def _update_add_l1_enabled(self) -> None:
        self.add_l1_button.setEnabled(len(self.data["buttons"]) < validation.MAX_L1_BUTTONS)

    def _update_add_child_enabled(self) -> None:
        button = self._selected_button()
        if button is None or button.get("type") != "expand":
            self.add_child_button.setEnabled(False)
            return
        level = self._selected_level()
        children = button.get("children") or []
        self.add_child_button.setEnabled(len(children) < max_children_for_level(level))

    # --- Field editing -----------------------------------------------------

    def _on_label_changed(self, text: str) -> None:
        if self._loading_editor:
            return
        button = self._selected_button()
        if button is None:
            return
        button["label"] = text
        self._refresh_tree_item_label(button["id"])
        self._refresh_errors()

    def _on_tooltip_changed(self, text: str) -> None:
        if self._loading_editor:
            return
        button = self._selected_button()
        if button is None:
            return
        button["tooltip"] = text
        self._refresh_errors()

    def _on_string_changed(self) -> None:
        if self._loading_editor:
            return
        button = self._selected_button()
        if button is None or button.get("type") != "clipboard":
            return
        button["string"] = self.string_edit.toPlainText()
        self._refresh_errors()

    def _on_type_changed(self, _index: int) -> None:
        if self._loading_editor:
            return
        button = self._selected_button()
        if button is None:
            return
        new_type = self.type_combo.currentData()
        if new_type == button.get("type"):
            return
        button["type"] = new_type
        if new_type == "clipboard":
            button.pop("children", None)
            button.setdefault("string", "")
        else:
            button.pop("string", None)
            button.setdefault("children", [])
        self._populate_tree()
        self._select_tree_item_by_id(button["id"])
        self._load_editor_for(button["id"], self._selected_level())
        self._update_add_child_enabled()

    def _select_tree_item_by_id(self, button_id: str) -> None:
        item = find_item_by_id(
            [self.tree.topLevelItem(i) for i in range(self.tree.topLevelItemCount())], button_id
        )
        if item is not None:
            self.tree.setCurrentItem(item)

    # --- Add / delete -------------------------------------------------------

    def _new_button(self, button_type: str = "clipboard") -> dict[str, Any]:
        button: dict[str, Any] = {
            "id": new_button_id(),
            "type": button_type,
            "label": "",
            "tooltip": "",
        }
        if button_type == "clipboard":
            button["string"] = ""
        else:
            button["children"] = []
        return button

    def _on_add_l1_clicked(self) -> None:
        if len(self.data["buttons"]) >= validation.MAX_L1_BUTTONS:
            return
        button = self._new_button()
        self.data["buttons"].append(button)
        self._populate_tree()
        self._select_tree_item_by_id(button["id"])
        self._update_add_l1_enabled()

    def _on_add_child_clicked(self) -> None:
        parent = self._selected_button()
        if parent is None or parent.get("type") != "expand":
            return
        level = self._selected_level()
        children = parent.setdefault("children", [])
        if len(children) >= max_children_for_level(level):
            return
        child = self._new_button()
        children.append(child)
        self._populate_tree()
        self._select_tree_item_by_id(child["id"])

    def _on_delete_clicked(self) -> None:
        button = self._selected_button()
        if button is None:
            return
        descendants = count_descendants(button)
        if not self._confirm_delete(button.get("label", ""), descendants):
            return
        located = find_parent_list_and_index(self.data["buttons"], button["id"])
        if located is None:
            return
        parent_list, index = located
        del parent_list[index]
        self._selected_id = None
        self._populate_tree()
        self._load_editor_for(None, level=1)
        self._update_add_l1_enabled()
        self.delete_button.setEnabled(False)
        self.add_child_button.setEnabled(False)

    # --- Top-level settings --------------------------------------------------

    def _on_autostart_toggled(self, checked: bool) -> None:
        self.data.setdefault("settings", {})["autostart"] = checked

    def _on_theme_changed(self, _index: int) -> None:
        self.data.setdefault("settings", {})["theme"] = self.theme_combo.currentData()

    # --- Validation / save / cancel -----------------------------------------

    def _refresh_errors(self) -> str | None:
        button = self._selected_button()
        if button is None:
            self.error_label.setText("")
            return None
        level = self._selected_level()
        errors = validation.validate_button(button, level)
        self.error_label.setText("\n".join(errors))
        return "\n".join(errors) if errors else None

    def current_errors(self) -> list[str]:
        """All validation errors for the whole working document (FR-5.5)."""
        return validation.validate_config(self.data)

    def _on_save_clicked(self) -> None:
        errors = self.current_errors()
        if errors:
            self.error_label.setText("\n".join(errors))
            return
        if self._on_save is not None:
            self._on_save(copy.deepcopy(self.data))
        self.close()

    def _on_cancel_clicked(self) -> None:
        """FR-5.7: Cancel discards the working copy without saving."""
        self.close()

