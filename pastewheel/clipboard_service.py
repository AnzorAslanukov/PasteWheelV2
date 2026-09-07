"""Clipboard copy service (SPEC §7.4, FR-4.1).

A thin wrapper around ``pyperclip`` so ``wheel_window.py`` (and tests) never
import ``pyperclip`` directly. On Windows, ``pyperclip``'s backend writes
via ``SetClipboardData(CF_UNICODETEXT, ...)`` — genuine UTF-16 text, so
full Unicode (incl. multi-codepoint emoji) round-trips correctly and is
readable by any other app (FR-4.1, NFR-4).
"""

from __future__ import annotations


def copy_to_clipboard(text: str) -> None:
    """Copy `text` to the system clipboard as Unicode text (FR-4.1)."""
    import pyperclip

    pyperclip.copy(text)
