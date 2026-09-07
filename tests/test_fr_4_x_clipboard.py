"""Tests for pastewheel.clipboard_service — FR-4.1 (SPEC §7.4).

Patches ``pyperclip.copy`` rather than touching the real system clipboard,
per ``.clinerules`` #6 (tests never touch real machine state).
"""

from __future__ import annotations

import pyperclip

from pastewheel.clipboard_service import copy_to_clipboard


def test_fr_4_1_copy_to_clipboard_delegates_to_pyperclip_copy(monkeypatch):
    calls = []
    monkeypatch.setattr(pyperclip, "copy", calls.append)

    copy_to_clipboard("Hello, 🌍!")

    assert calls == ["Hello, 🌍!"]


def test_fr_4_1_copy_to_clipboard_preserves_unicode_text(monkeypatch):
    """FR-4.1/NFR-4: full Unicode (incl. emoji) is passed through unmodified."""
    calls = []
    monkeypatch.setattr(pyperclip, "copy", calls.append)
    text = "Test café 🎯 ZWJ-emoji 👨‍👩‍👧‍👦"

    copy_to_clipboard(text)

    assert calls == [text]
