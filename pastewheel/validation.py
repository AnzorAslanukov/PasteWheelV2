"""Field & schema validation rules for PasteWheel (SPEC §9.2, FR-5.5).

Pure functions, no I/O and no Qt dependency, so they can be exercised by
both the settings window (inline error messages, FR-5.5) and ``config.py``
(load-time schema enforcement, FR-7.x). Every ``validate_*`` field function
returns ``None`` when the value is valid, otherwise a short human-readable
error string suitable for display inline in the settings UI.
"""

from __future__ import annotations

from typing import Any

import grapheme

# --- Limits from SPEC §6, §7.2, §7.3, §9.2 -------------------------------

MIN_LABEL_GRAPHEMES = 1
MAX_LABEL_GRAPHEMES = 3
MAX_STRING_CHARS = 10_000
MAX_L1_BUTTONS = 8
MAX_L2_BUTTONS = 16
MAX_L3_BUTTONS = 32
# FR-3.5: children of one expand: <=16 (expand is at L1) or <=32 (expand at L2)
MAX_CHILDREN_OF_L1_EXPAND = 16
MAX_CHILDREN_OF_L2_EXPAND = 32

VALID_BUTTON_TYPES = frozenset({"clipboard", "expand"})
VALID_THEMES = frozenset({"system", "dark", "light"})
MAX_LEVEL = 3

CLIPBOARD_BUTTON_KEYS = frozenset({"id", "type", "label", "tooltip", "string"})
EXPAND_BUTTON_KEYS = frozenset({"id", "type", "label", "tooltip", "children"})
SETTINGS_KEYS = frozenset({"autostart", "theme"})
CONFIG_KEYS = frozenset({"schema_version", "settings", "buttons"})


# --- Field-level validators (used by the settings editor, FR-5.5) -------


def validate_label(label: Any) -> str | None:
    """Label must be a single emoji (incl. ZWJ sequences) or 1-3 characters.

    Character counting uses grapheme clusters (the ``grapheme`` library) so
    a multi-codepoint emoji sequence still counts as a single character.
    """
    if not isinstance(label, str) or label == "":
        return "Label is required."
    length = grapheme.length(label)
    if length < MIN_LABEL_GRAPHEMES or length > MAX_LABEL_GRAPHEMES:
        return "Label must be a single emoji or 1-3 characters."
    return None


def validate_string(string: Any) -> str | None:
    """Clipboard string: non-empty after trimming whitespace, <=10,000 chars."""
    if not isinstance(string, str):
        return "String is required."
    trimmed = string.strip()
    if len(trimmed) == 0:
        return "String must not be empty."
    if len(trimmed) > MAX_STRING_CHARS:
        return f"String must be {MAX_STRING_CHARS:,} characters or fewer."
    return None


def validate_children_count(parent_level: int, children: Any) -> str | None:
    """Validate the number of children of an expand button (FR-3.5).

    ``parent_level`` is the level (1 or 2) of the expand button itself;
    its children live one level down (L2 or L3 respectively).
    """
    if not isinstance(children, list) or len(children) == 0:
        return "An expand button requires at least one child."
    if parent_level == 1:
        limit = MAX_CHILDREN_OF_L1_EXPAND
    elif parent_level == 2:
        limit = MAX_CHILDREN_OF_L2_EXPAND
    else:
        return "Expand buttons are not allowed at level 3."
    if len(children) > limit:
        return f"An expand button at this level allows at most {limit} children."
    return None


def validate_button_type(button_type: Any, level: int) -> str | None:
    """Validate the ``type`` field; ``expand`` is forbidden at L3 (FR-3.3)."""
    if button_type not in VALID_BUTTON_TYPES:
        return "Type must be 'clipboard' or 'expand'."
    if button_type == "expand" and level >= MAX_LEVEL:
        return "Level 3 buttons cannot be expand buttons."
    return None


def validate_theme(theme: Any) -> str | None:
    """``settings.theme`` must be one of system/dark/light."""
    if theme not in VALID_THEMES:
        return "Theme must be one of: system, dark, light."
    return None


def validate_l1_count(buttons: Any) -> str | None:
    """The top-level (L1) button array must have at most 8 entries (FR-2.1)."""
    if not isinstance(buttons, list):
        return "buttons must be a list."
    if len(buttons) > MAX_L1_BUTTONS:
        return f"A maximum of {MAX_L1_BUTTONS} top-level buttons is allowed."
    return None


# --- Aggregate / schema validators (used by config.py, FR-7.x) ----------


def validate_button(button: Any, level: int) -> list[str]:
    """Validate a single button object's own fields (not its descendants).

    Returns a list of error messages; an empty list means valid.
    """
    errors: list[str] = []
    if not isinstance(button, dict):
        return ["Button must be an object."]

    button_type = button.get("type")
    type_error = validate_button_type(button_type, level)
    if type_error:
        errors.append(type_error)

    label_error = validate_label(button.get("label"))
    if label_error:
        errors.append(label_error)

    if button_type == "clipboard":
        unknown = set(button.keys()) - CLIPBOARD_BUTTON_KEYS
        if unknown:
            errors.append(f"Unknown field(s): {', '.join(sorted(unknown))}.")
        string_error = validate_string(button.get("string"))
        if string_error:
            errors.append(string_error)
    elif button_type == "expand":
        unknown = set(button.keys()) - EXPAND_BUTTON_KEYS
        if unknown:
            errors.append(f"Unknown field(s): {', '.join(sorted(unknown))}.")
        children_error = validate_children_count(level, button.get("children"))
        if children_error:
            errors.append(children_error)
    else:
        # Unknown type: still flag any keys outside the union of both known
        # shapes so garbage objects are reliably rejected.
        unknown = set(button.keys()) - (CLIPBOARD_BUTTON_KEYS | EXPAND_BUTTON_KEYS)
        if unknown:
            errors.append(f"Unknown field(s): {', '.join(sorted(unknown))}.")

    if not button.get("id"):
        errors.append("id is required.")

    return errors


def validate_button_tree(button: Any, level: int) -> list[str]:
    """Recursively validate a button and (if it is an expand) its children."""
    errors = validate_button(button, level)
    if isinstance(button, dict) and button.get("type") == "expand":
        children = button.get("children")
        if isinstance(children, list):
            for child in children:
                errors.extend(validate_button_tree(child, level + 1))
    return errors


def validate_settings(settings: Any) -> list[str]:
    """Validate the ``settings`` object of the config document."""
    errors: list[str] = []
    if not isinstance(settings, dict):
        return ["settings must be an object."]
    unknown = set(settings.keys()) - SETTINGS_KEYS
    if unknown:
        errors.append(f"Unknown field(s) in settings: {', '.join(sorted(unknown))}.")
    if "autostart" in settings and not isinstance(settings["autostart"], bool):
        errors.append("settings.autostart must be a boolean.")
    theme_error = validate_theme(settings.get("theme"))
    if theme_error:
        errors.append(theme_error)
    return errors


def validate_config(data: Any) -> list[str]:
    """Validate a whole config document as loaded from ``config.json``.

    Returns a list of human-readable error messages; an empty list means
    the document is valid per SPEC §9.2.
    """
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["Config must be a JSON object."]

    unknown = set(data.keys()) - CONFIG_KEYS
    if unknown:
        errors.append(f"Unknown top-level field(s): {', '.join(sorted(unknown))}.")

    if "schema_version" not in data:
        errors.append("schema_version is required.")
    elif not isinstance(data["schema_version"], int):
        errors.append("schema_version must be an integer.")

    errors.extend(validate_settings(data.get("settings", {})))

    buttons = data.get("buttons")
    l1_error = validate_l1_count(buttons)
    if l1_error:
        errors.append(l1_error)
    if isinstance(buttons, list):
        for button in buttons:
            errors.extend(validate_button_tree(button, level=1))

    return errors
