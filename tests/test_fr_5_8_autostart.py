"""Tests for pastewheel.autostart — FR-5.8 (SPEC §7.5).

Patches ``pastewheel.autostart.winreg`` with a small in-memory fake so no
test ever touches the real
``HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run`` key, per
``.clinerules`` #6.
"""

from __future__ import annotations

import pytest

from pastewheel import autostart


class FakeKey:
    def __init__(self, store: dict[str, str]):
        self.store = store

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeWinReg:
    """Fakes just enough of the ``winreg`` API for autostart.py."""

    HKEY_CURRENT_USER = object()
    KEY_READ = 1
    KEY_SET_VALUE = 2
    REG_SZ = 1

    def __init__(self):
        self.values: dict[str, str] = {}

    def OpenKey(self, hive, path, reserved, access):  # noqa: N802 (mimics winreg API)
        assert hive is self.HKEY_CURRENT_USER
        assert path == autostart.RUN_KEY_PATH
        return FakeKey(self.values)

    def QueryValueEx(self, key, name):  # noqa: N802
        if name not in key.store:
            raise OSError("not found")
        return (key.store[name], self.REG_SZ)

    def SetValueEx(self, key, name, reserved, value_type, value):  # noqa: N802
        key.store[name] = value

    def DeleteValue(self, key, name):  # noqa: N802
        if name not in key.store:
            raise OSError("not found")
        del key.store[name]


@pytest.fixture
def fake_registry(monkeypatch):
    fake = FakeWinReg()
    monkeypatch.setattr(autostart, "winreg", fake)
    return fake


def test_fr_5_8_enable_creates_run_key_value(fake_registry):
    autostart.enable(r"C:\Program Files\PasteWheel\PasteWheel.exe")

    assert fake_registry.values[autostart.VALUE_NAME] == (
        r"C:\Program Files\PasteWheel\PasteWheel.exe"
    )
    assert autostart.is_enabled() is True


def test_fr_5_8_disable_removes_run_key_value(fake_registry):
    autostart.enable(r"C:\PasteWheel.exe")
    autostart.disable()

    assert autostart.VALUE_NAME not in fake_registry.values
    assert autostart.is_enabled() is False


def test_fr_5_8_disable_is_a_no_op_when_absent(fake_registry):
    autostart.disable()  # must not raise

    assert autostart.is_enabled() is False


def test_fr_5_8_is_enabled_false_when_never_set(fake_registry):
    assert autostart.is_enabled() is False


def test_fr_5_8_apply_true_enables_and_false_disables(fake_registry):
    autostart.apply(True, r"C:\PasteWheel.exe")
    assert autostart.is_enabled() is True

    autostart.apply(False, r"C:\PasteWheel.exe")
    assert autostart.is_enabled() is False
