"""pytest-qt tests for pastewheel.main — wiring (SPEC §4; FR-1.x, FR-5.x, FR-6.x).

Runs headless via QT_QPA_PLATFORM=offscreen (tests/conftest.py, §10). Real
``WheelWindow``/``TrayIcon`` widgets are used (they are cheap and already
exercised elsewhere); the OS-facing bits (clipboard, save, theme, quit,
autostart, single-instance socket) are injected fakes.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint
from PySide6.QtGui import QIcon

from pastewheel import main as main_module
from pastewheel.config import default_config
from pastewheel.hooks import HookManager
from pastewheel.main import PasteWheelController, acquire_single_instance_lock
from pastewheel.signals import HookSignals
from pastewheel.tray import TrayIcon
from pastewheel.wheel_window import WheelWindow


def _clipboard_button(button_id="c1", label="TST", string="Test"):
    return {"id": button_id, "type": "clipboard", "label": label, "tooltip": "", "string": string}


def _make_controller(qtbot, data=None, **kwargs):
    data = data if data is not None else default_config()
    saved = []
    copied = []
    themed = []
    quit_calls = []
    controller = PasteWheelController(
        config_path="unused",
        initial_data=data,
        save_config=lambda path, d: saved.append((path, d)),
        copy_to_clipboard=copied.append,
        apply_theme_fn=themed.append,
        quit_app=lambda: quit_calls.append(True),
        **kwargs,
    )
    wheel = WheelWindow(
        on_copy=controller.copy_and_notify,
        on_open_settings=controller.open_settings,
        on_quit=controller.quit,
    )
    qtbot.addWidget(wheel)
    tray = TrayIcon(QIcon())
    signals = HookSignals()
    hooks = HookManager(signals)
    controller.attach(wheel, tray, hooks)
    return controller, wheel, saved, copied, themed, quit_calls


# --- Trigger wiring (FR-1.1-1.3) ------------------------------------------


def test_fr_1_1_toggle_wheel_shows_when_hidden(qtbot, monkeypatch):
    controller, wheel, *_ = _make_controller(qtbot, data={**default_config(), "buttons": []})
    monkeypatch.setattr(main_module.QCursor, "pos", staticmethod(lambda: QPoint(100, 100)))

    controller.toggle_wheel()

    assert wheel.state.is_visible is True


def test_fr_1_3_toggle_wheel_hides_when_visible(qtbot, monkeypatch):
    controller, wheel, *_ = _make_controller(qtbot)
    monkeypatch.setattr(main_module.QCursor, "pos", staticmethod(lambda: QPoint(100, 100)))
    controller.toggle_wheel()
    assert wheel.state.is_visible is True

    controller.toggle_wheel()

    assert wheel.state.is_visible is False


def test_fr_1_4_handle_esc_hides_visible_wheel(qtbot, monkeypatch):
    controller, wheel, *_ = _make_controller(qtbot)
    monkeypatch.setattr(main_module.QCursor, "pos", staticmethod(lambda: QPoint(100, 100)))
    controller.toggle_wheel()

    controller.handle_esc()

    assert wheel.state.is_visible is False


def test_fr_1_4_handle_esc_is_a_no_op_when_already_hidden(qtbot):
    controller, wheel, *_ = _make_controller(qtbot)

    controller.handle_esc()  # must not raise

    assert wheel.state.is_visible is False


# --- Clipboard wiring (FR-3.1, FR-4.1) ------------------------------------


def test_fr_3_1_copy_and_notify_delegates_to_injected_clipboard(qtbot):
    controller, _wheel, _saved, copied, *_ = _make_controller(qtbot)

    controller.copy_and_notify("hello")

    assert copied == ["hello"]


# --- Settings wiring (FR-5.1, FR-5.7) -------------------------------------


def test_fr_5_1_open_settings_creates_a_single_reused_instance(qtbot):
    controller, *_ = _make_controller(qtbot)

    controller.open_settings()
    first = controller.settings_window
    controller.open_settings()
    second = controller.settings_window

    assert first is second


def test_fr_5_7_saving_settings_persists_and_updates_wheel_buttons(qtbot):
    controller, wheel, saved, _copied, themed, _quit = _make_controller(qtbot)
    controller.open_settings()
    new_data = default_config()
    new_data["buttons"] = [_clipboard_button()]
    new_data["settings"]["theme"] = "dark"

    controller._on_settings_saved(new_data)

    assert saved[-1][1] == new_data
    assert wheel.buttons == [_clipboard_button()]
    assert themed[-1] == "dark"


# --- Quit wiring (FR-1.4, FR-6.3) ------------------------------------------


def test_fr_6_3_quit_stops_hooks_hides_tray_and_calls_quit_app(qtbot):
    controller, _wheel, *_ = _make_controller(qtbot)
    stop_calls = []
    controller.hooks.stop = lambda: stop_calls.append(True)

    controller.quit()

    assert stop_calls == [True]


def test_fr_6_3_quit_calls_injected_quit_app(qtbot):
    controller, *_rest, quit_calls = _make_controller(qtbot)
    controller.hooks.stop = lambda: None

    controller.quit()

    assert quit_calls == [True]


# --- Single-instance lock (FR-6.2) ----------------------------------------


def test_fr_6_2_acquire_lock_returns_server_when_none_is_listening():
    server = acquire_single_instance_lock(server_name="pw-test-lock-unique-1")
    try:
        assert server is not None
        assert server.isListening()
    finally:
        server.close()


def test_fr_6_2_acquire_lock_returns_none_when_already_listening():
    first = acquire_single_instance_lock(server_name="pw-test-lock-unique-2")
    try:
        second = acquire_single_instance_lock(server_name="pw-test-lock-unique-2")
        assert second is None
    finally:
        first.close()


# --- Theme application (FR-5.10) ------------------------------------------


def test_fr_5_10_apply_theme_system_unsets_color_scheme(qtbot):
    calls = []

    class FakeStyleHints:
        def setColorScheme(self, scheme):
            calls.append(("set", scheme))

        def unsetColorScheme(self):
            calls.append(("unset", None))

    class FakeApp:
        def styleHints(self):
            return FakeStyleHints()

    main_module.apply_theme(FakeApp(), "system")

    assert calls == [("unset", None)]


def test_fr_5_10_apply_theme_dark_sets_dark_color_scheme(qtbot):
    calls = []

    class FakeStyleHints:
        def setColorScheme(self, scheme):
            calls.append(scheme)

        def unsetColorScheme(self):
            calls.append(None)

    class FakeApp:
        def styleHints(self):
            return FakeStyleHints()

    main_module.apply_theme(FakeApp(), "dark")

    assert calls == [main_module._THEME_TO_QT_SCHEME["dark"]]
