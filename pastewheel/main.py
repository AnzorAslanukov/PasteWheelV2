"""Application wiring: bootstraps Qt, hooks, tray, and windows (SPEC §4).

Design notes (implementer decisions within SPEC's constraints):

- :class:`PasteWheelController` holds all the cross-module wiring logic
  (what happens when a trigger fires, Save is clicked, etc.) as plain,
  injectable, unit-testable Python — mirroring the callback-injection
  pattern used throughout ``wheel_window.py``/``settings_window.py``. Real
  ``WheelWindow``/``TrayIcon``/``HookManager`` instances are attached via
  :meth:`PasteWheelController.attach` rather than passed to ``__init__``,
  because ``WheelWindow``'s and ``TrayIcon``'s own constructors need
  bound methods on the controller (``open_settings``, ``quit``) as their
  click callbacks — attaching after construction breaks that circular
  dependency cleanly.
- :func:`main` (and :func:`build_controller`) are thin bootstrap/glue code
  that creates a real ``QApplication`` and real OS-backed objects; per
  SPEC §10 ("hooks/OS layer excluded [from coverage] by design") these are
  not unit tested directly — the interesting logic they call
  (``PasteWheelController``, :func:`acquire_single_instance_lock`,
  :func:`apply_theme`) is tested in isolation instead.
- FR-6.2 single instance: :func:`acquire_single_instance_lock` probes for
  an existing ``QLocalServer`` by attempting to *connect* to its name
  (reliable: a successful connect proves a live listener exists) rather
  than by calling ``listen()`` and checking its return value — on Windows,
  named pipes support multiple simultaneous listener instances under the
  same name by default, so a second ``listen()`` call can spuriously
  succeed even while a first instance is already running. There remains
  an unavoidable small race window between the probe and this process's
  own ``listen()`` call if two instances launch simultaneously; SPEC does
  not require perfect atomicity here and this is an accepted v1 limitation.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCursor, QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication

from pastewheel import autostart, clipboard_service, config
from pastewheel.hooks import HookManager
from pastewheel.settings_window import SettingsWindow, is_frozen
from pastewheel.signals import HookSignals
from pastewheel.tray import TrayIcon
from pastewheel.wheel_window import WheelWindow

SINGLE_INSTANCE_SERVER_NAME = "PasteWheel-SingleInstance"
ALREADY_RUNNING_EXIT_DELAY_MS = 3000  # give the tray balloon time to render (FR-6.2)

_THEME_TO_QT_SCHEME = {
    "dark": Qt.ColorScheme.Dark,
    "light": Qt.ColorScheme.Light,
}


def icon_path() -> Path:
    """Location of the app/tray icon (SPEC §3: `assets/icon.ico`).

    Resolves relative to the PyInstaller bundle root when frozen (M6), or
    the repo root when running from source.
    """
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    else:
        base = Path(__file__).resolve().parent.parent
    return base / "assets" / "icon.ico"


def apply_theme(app: QApplication, theme: str) -> None:
    """Apply the `theme` setting (system/dark/light) app-wide (FR-5.10)."""
    style_hints = app.styleHints()
    if theme in _THEME_TO_QT_SCHEME:
        style_hints.setColorScheme(_THEME_TO_QT_SCHEME[theme])
    else:
        style_hints.unsetColorScheme()


def acquire_single_instance_lock(
    server_name: str = SINGLE_INSTANCE_SERVER_NAME,
    socket_factory: Callable[[], Any] = QLocalSocket,
    server_factory: Callable[[], Any] = QLocalServer,
    probe_timeout_ms: int = 200,
) -> Any | None:
    """Return a listening server if no other instance is running, else None.

    FR-6.2: the caller should show the "already running" balloon and exit
    when this returns ``None``.
    """
    probe = socket_factory()
    probe.connectToServer(server_name)
    already_running = probe.waitForConnected(probe_timeout_ms)
    probe.abort()
    if already_running:
        return None
    QLocalServer.removeServer(server_name)
    server = server_factory()
    server.listen(server_name)
    return server


class PasteWheelController:
    """Owns config state + wires triggers/tray/settings together (SPEC §4).

    Real windows/tray/hooks are attached post-construction via
    :meth:`attach` (see module docstring for why). ``config_path``,
    ``save_config``, ``copy_to_clipboard``, and ``apply_theme_fn`` are all
    injectable so this class is fully unit-testable without real file I/O,
    a real clipboard, or a real ``QApplication`` theme change.
    """

    def __init__(
        self,
        config_path: Path,
        initial_data: dict[str, Any],
        save_config: Callable[[Path, dict[str, Any]], None] = config.save_config,
        copy_to_clipboard: Callable[[str], None] = clipboard_service.copy_to_clipboard,
        apply_theme_fn: Callable[[str], None] | None = None,
        quit_app: Callable[[], None] | None = None,
    ) -> None:
        self.config_path = config_path
        self.data = initial_data
        self._save_config = save_config
        self._copy_to_clipboard = copy_to_clipboard
        self._apply_theme_fn = apply_theme_fn or (lambda _theme: None)
        self._quit_app = quit_app or (lambda: None)

        self.wheel: WheelWindow | None = None
        self.settings_window: SettingsWindow | None = None
        self.tray: TrayIcon | None = None
        self.hooks: HookManager | None = None

    def attach(
        self,
        wheel: WheelWindow,
        tray: TrayIcon,
        hooks: HookManager,
    ) -> None:
        """Attach the real Qt/OS objects once they exist (see class docstring)."""
        self.wheel = wheel
        self.tray = tray
        self.hooks = hooks
        self.wheel.set_buttons(self.data.get("buttons", []))
        self._apply_theme_fn(self.data.get("settings", {}).get("theme", "system"))

    # --- Trigger handling (FR-1.1-1.3) -----------------------------------

    def toggle_wheel(self) -> None:
        """Show the wheel at the pointer if hidden, else hide it (FR-1.1/1.2/1.3)."""
        if self.wheel is None:
            return
        if self.wheel.state.is_visible:
            self.wheel.hide_wheel()
        else:
            self.wheel.show_at(QCursor.pos())

    def handle_esc(self) -> None:
        """Hide the wheel on Esc while visible (FR-1.4)."""
        if self.wheel is not None and self.wheel.state.is_visible:
            self.wheel.hide_wheel()

    # --- Clipboard / settings / quit (FR-3.1, FR-5.1, FR-6.x) ------------

    def copy_and_notify(self, text: str) -> None:
        """The wheel's ``on_copy`` callback (FR-3.1/FR-4.1)."""
        self._copy_to_clipboard(text)

    def open_settings(self) -> None:
        """Open (or refocus) the single settings window instance (FR-5.1)."""
        if self.settings_window is None:
            self.settings_window = SettingsWindow(self.data, on_save=self._on_settings_saved)
        else:
            self.settings_window.load(self.data)
        self.settings_window.show()
        self.settings_window.raise_()
        self.settings_window.activateWindow()

    def quit(self) -> None:
        """Exit fully: unhook, drop the tray icon, terminate (FR-1.4, FR-6.3)."""
        if self.hooks is not None:
            self.hooks.stop()
        if self.tray is not None:
            self.tray.hide()
        self._quit_app()

    # --- Save handling (FR-5.7, FR-5.8, FR-5.10) -------------------------

    def _on_settings_saved(self, new_data: dict[str, Any]) -> None:
        self.data = new_data
        self._save_config(self.config_path, self.data)
        if self.wheel is not None:
            self.wheel.set_buttons(self.data.get("buttons", []))
        settings = self.data.get("settings", {})
        self._apply_theme_fn(settings.get("theme", "system"))
        if is_frozen():
            autostart.apply(bool(settings.get("autostart", False)), sys.executable)


def main() -> int:
    """Real entry point (SPEC §11: `python -m pastewheel`); not unit tested."""
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    server = acquire_single_instance_lock()
    if server is None:
        icon = QIcon(str(icon_path()))
        tray = TrayIcon(icon)
        tray.show()
        tray.notify_already_running()
        QTimer.singleShot(ALREADY_RUNNING_EXIT_DELAY_MS, app.quit)
        return app.exec()

    cfg_path = config.default_config_path()
    result = config.load_config(cfg_path)

    controller = PasteWheelController(
        config_path=cfg_path,
        initial_data=result.data,
        apply_theme_fn=lambda theme: apply_theme(app, theme),
        quit_app=app.quit,
    )

    wheel = WheelWindow(
        on_copy=controller.copy_and_notify,
        on_open_settings=controller.open_settings,
        on_quit=controller.quit,
    )
    icon = QIcon(str(icon_path()))
    tray = TrayIcon(icon, on_open_settings=controller.open_settings, on_quit=controller.quit)
    signals = HookSignals()
    hooks = HookManager(signals, is_wheel_visible=lambda: wheel.state.is_visible)

    controller.attach(wheel, tray, hooks)

    signals.toggle_wheel.connect(controller.toggle_wheel)
    signals.esc_pressed.connect(controller.handle_esc)

    if result.recovered:
        tray.notify(
            "PasteWheel",
            "Your configuration file was corrupted and has been reset to defaults.",
        )

    tray.show()
    hooks.start()
    app.aboutToQuit.connect(hooks.stop)

    exit_code = app.exec()
    server.close()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
