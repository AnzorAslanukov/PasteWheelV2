"""The system tray icon (SPEC §7.6, FR-6.1-6.2).

Design notes (implementer decisions within SPEC's constraints):

- Actions (opening settings, quitting) are delegated to injected callbacks
  so this module has no direct dependency on ``settings_window.py`` or the
  hooks/app-quit sequence, mirroring the callback-injection pattern used
  throughout ``wheel_window.py``/``settings_window.py``.
- FR-6.2 (single instance): the *detection* of "already running" lives in
  ``main.py`` (a ``QLocalServer``/``QLocalSocket`` single-instance lock —
  see its module docstring), not here; this module only exposes
  :meth:`TrayIcon.notify_already_running` so the balloon message text is
  defined in one place and is easy to unit test without any real tray
  backend (``QSystemTrayIcon.isSystemTrayAvailable()`` is ``False`` in the
  headless/offscreen CI environment, SPEC §10, so tests never assert on a
  real visible tray icon — only on the calls made to it).
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QWidget

ALREADY_RUNNING_TITLE = "PasteWheel"
ALREADY_RUNNING_MESSAGE = "PasteWheel is already running."


class TrayIcon(QSystemTrayIcon):
    """Tray icon with a Settings/Exit menu (FR-6.1).

    Always present while the app is running (FR-6.1); a normal
    ``QSystemTrayIcon`` already satisfies this by staying alive for the
    process's lifetime once shown.
    """

    def __init__(
        self,
        icon: QIcon,
        on_open_settings: Callable[[], None] | None = None,
        on_quit: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(icon, parent)
        self.setToolTip("PasteWheel")
        self._on_open_settings = on_open_settings
        self._on_quit = on_quit

        self.menu = QMenu()
        self.settings_action = QAction("Settings", self.menu)
        self.settings_action.triggered.connect(self._handle_open_settings)
        self.exit_action = QAction("Exit", self.menu)
        self.exit_action.triggered.connect(self._handle_quit)
        self.menu.addAction(self.settings_action)
        self.menu.addAction(self.exit_action)
        self.setContextMenu(self.menu)

    def notify_already_running(self) -> None:
        """Show the "already running" balloon (FR-6.2, D5)."""
        self.notify(ALREADY_RUNNING_TITLE, ALREADY_RUNNING_MESSAGE)

    def notify(self, title: str, message: str) -> None:
        """Show a generic tray balloon (e.g. FR-7.3 corrupt-config recovery)."""
        self.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information)

    def _handle_open_settings(self) -> None:
        if self._on_open_settings is not None:
            self._on_open_settings()

    def _handle_quit(self) -> None:
        if self._on_quit is not None:
            self._on_quit()
