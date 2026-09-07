"""pytest-qt tests for pastewheel.tray — FR-6.1, FR-6.2 (SPEC §7.6).

Runs headless via QT_QPA_PLATFORM=offscreen (tests/conftest.py, §10).
``QSystemTrayIcon.isSystemTrayAvailable()`` is False under offscreen, so
these tests only assert on wiring/calls, never on real tray visibility.
"""

from __future__ import annotations

from PySide6.QtGui import QIcon

from pastewheel.tray import ALREADY_RUNNING_MESSAGE, ALREADY_RUNNING_TITLE, TrayIcon


def _make_tray(qtbot, on_open_settings=None, on_quit=None):
    tray = TrayIcon(QIcon(), on_open_settings=on_open_settings, on_quit=on_quit)
    return tray


# --- FR-6.1: tray menu (Settings / Exit) ---------------------------------


def test_fr_6_1_menu_has_settings_and_exit_actions(qtbot):
    tray = _make_tray(qtbot)

    actions = tray.menu.actions()
    assert [a.text() for a in actions] == ["Settings", "Exit"]


def test_fr_6_1_settings_action_triggers_callback(qtbot):
    calls = []
    tray = _make_tray(qtbot, on_open_settings=lambda: calls.append(True))

    tray.settings_action.trigger()

    assert calls == [True]


def test_fr_6_1_exit_action_triggers_callback(qtbot):
    calls = []
    tray = _make_tray(qtbot, on_quit=lambda: calls.append(True))

    tray.exit_action.trigger()

    assert calls == [True]


def test_fr_6_1_missing_callbacks_do_not_raise(qtbot):
    tray = _make_tray(qtbot)

    tray.settings_action.trigger()
    tray.exit_action.trigger()  # neither should raise


# --- FR-6.2: "already running" notification (D5) -------------------------


def test_fr_6_2_notify_already_running_calls_show_message(qtbot, monkeypatch):
    tray = _make_tray(qtbot)
    calls = []
    monkeypatch.setattr(tray, "showMessage", lambda *args: calls.append(args))

    tray.notify_already_running()

    assert calls == [(ALREADY_RUNNING_TITLE, ALREADY_RUNNING_MESSAGE, calls[0][2])]


def test_fr_6_2_already_running_message_text():
    assert ALREADY_RUNNING_MESSAGE == "PasteWheel is already running."
