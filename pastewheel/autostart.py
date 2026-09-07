"""Windows autostart registry management (SPEC §7.5, FR-5.8).

Manages the per-user Run key
``HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run\\PasteWheel``. Only
meaningful for a packaged (frozen) build — running from source has no
stable, double-clickable executable path to register, so
``settings_window.py`` disables the toggle in that case (FR-5.8) and this
module is exercised only when frozen.

``winreg`` is Windows-only (SPEC §3: Windows 10/11 x64 is the only target
platform), so it is imported unconditionally at module scope; tests patch
``pastewheel.autostart.winreg`` with a fake registry (an in-memory stand-in
exposing ``HKEY_CURRENT_USER``/``OpenKey``/``SetValueEx``/etc.) rather than
touching the real registry, per ``.clinerules`` #6 (tests never write to
real machine state — ``tmp_path`` is for the filesystem; the registry
equivalent is "never touch the real key").
"""

from __future__ import annotations

import winreg

RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "PasteWheel"


def _open_run_key(access: int):
    return winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, access)


def is_enabled() -> bool:
    """Whether the ``PasteWheel`` autostart value currently exists."""
    try:
        with _open_run_key(winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, VALUE_NAME)
            return True
    except OSError:
        return False


def enable(executable_path: str) -> None:
    """Create/overwrite the autostart registry value (FR-5.8: `on`).

    `executable_path` should be the quoted, absolute path to the packaged
    ``PasteWheel.exe`` (the caller is responsible for quoting if the path
    contains spaces).
    """
    with _open_run_key(winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, executable_path)


def disable() -> None:
    """Remove the autostart registry value (FR-5.8: `off`); a no-op if absent."""
    try:
        with _open_run_key(winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, VALUE_NAME)
    except OSError:
        pass


def apply(enabled: bool, executable_path: str) -> None:
    """Reconcile the registry with the desired `enabled` state (FR-5.8)."""
    if enabled:
        enable(executable_path)
    else:
        disable()
