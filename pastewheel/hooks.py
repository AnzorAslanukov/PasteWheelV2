"""Global mouse/keyboard hooks (SPEC §4, §7.1; FR-1.1-1.4, FR-4.2).

Design notes (implementer decisions within SPEC's constraints):

- ``pynput`` listeners each run on their own OS thread. Per SPEC §4 ("hook
  threads never touch Qt widgets directly") this module only ever reaches
  the GUI thread via :class:`pastewheel.signals.HookSignals`; ``Signal.emit``
  is safe to call from any thread — Qt automatically marshals the connected
  slot call onto the receiver's thread (a queued connection, the default
  whenever emitter and receiver live on different threads).
- On Windows, ``win32_event_filter`` is the only mechanism pynput exposes
  for suppressing *specific* events system-wide (see pynput's FAQ). Calling
  ``listener.suppress_event()`` from inside the filter raises an internal
  exception pynput uses to block the hook chain (``CallNextHookEx``) for
  that one event — this is what actually keeps a swallowed keystroke/click
  from reaching the focused app. Passing ``suppress=True`` to the
  ``Listener`` constructor would instead suppress *all* events
  unconditionally, which would violate FR-4.2 (normal Ctrl+C/Ctrl+V must
  stay untouched).
- The Win32 message/virtual-key constants below are hardcoded rather than
  imported from ``pynput._util`` (a private, undocumented package) because
  they are stable, publicly documented values (see
  https://learn.microsoft.com/windows/win32/inputdev/virtual-key-codes and
  the ``WM_*`` constants in ``winuser.h``).
- All "which raw (msg, vkCode) pairs count as the middle-click trigger /
  the `Alt+\\`` chord / Esc-while-visible" logic is factored into small pure
  functions so it is fully unit-testable without installing a real OS-level
  hook (SPEC §10 excludes the hooks/OS layer from *coverage* "by design",
  but this classification logic is still worth testing headlessly).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pastewheel.signals import HookSignals

# --- Win32 message / virtual-key constants (stable, documented by MS) ---

WM_MBUTTONDOWN = 0x0207
WM_MBUTTONUP = 0x0208
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105

VK_ESCAPE = 0x1B
VK_OEM_3 = 0xC0  # the '`'/'~' key on a US keyboard layout (FR-1.2: Alt+`)


# --- Pure event classification (unit-testable without a real OS hook) ---


def is_middle_click_down(msg: int) -> bool:
    """Whether `msg` is a middle-button press (shows/hides the wheel, FR-1.1/1.3)."""
    return msg == WM_MBUTTONDOWN


def is_middle_click_event(msg: int) -> bool:
    """Whether `msg` is any middle-button event (always swallowed, FR-1.1)."""
    return msg in (WM_MBUTTONDOWN, WM_MBUTTONUP)


def is_toggle_hotkey_down(msg: int, vk_code: int) -> bool:
    """Whether (msg, vk_code) is the `Alt+\\`` chord being pressed (FR-1.2).

    Windows delivers a non-modifier keypress as ``WM_SYSKEYDOWN`` (instead
    of the plain ``WM_KEYDOWN``) precisely when Alt is currently held, so
    checking for ``WM_SYSKEYDOWN`` + the backtick vk code is sufficient to
    detect the chord without separately tracking Alt's up/down state.
    """
    return msg == WM_SYSKEYDOWN and vk_code == VK_OEM_3


def is_toggle_hotkey_event(msg: int, vk_code: int) -> bool:
    """Whether (msg, vk_code) is either half of the `Alt+\\`` chord (FR-1.2)."""
    return msg in (WM_SYSKEYDOWN, WM_SYSKEYUP) and vk_code == VK_OEM_3


def is_escape_down(msg: int, vk_code: int) -> bool:
    """Whether (msg, vk_code) is an Esc keypress (FR-1.4)."""
    return msg in (WM_KEYDOWN, WM_SYSKEYDOWN) and vk_code == VK_ESCAPE


def is_escape_event(msg: int, vk_code: int) -> bool:
    """Whether (msg, vk_code) is any half of an Esc keystroke (FR-1.4)."""
    return msg in (WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP) and vk_code == VK_ESCAPE


def _default_mouse_listener_factory(**kwargs: Any) -> Any:
    from pynput import mouse

    return mouse.Listener(**kwargs)


def _default_keyboard_listener_factory(**kwargs: Any) -> Any:
    from pynput import keyboard

    return keyboard.Listener(**kwargs)


class HookManager:
    """Owns the global mouse/keyboard hooks and drives `HookSignals`.

    Real ``pynput`` listeners are created lazily in :meth:`start` via
    injectable factories, so tests can substitute fakes exposing just
    ``start()``/``stop()``/``suppress_event()`` and exercise the filter
    callbacks directly — without installing a real OS-level hook (which
    requires a live interactive desktop session).
    """

    def __init__(
        self,
        signals: HookSignals,
        is_wheel_visible: Callable[[], bool] | None = None,
        mouse_listener_factory: Callable[..., Any] | None = None,
        keyboard_listener_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.signals = signals
        # FR-1.4: Esc is swallowed only while the wheel is visible. Polling
        # a callback (rather than a settable flag main.py must remember to
        # flip on every hide path) means this stays correct even though
        # WheelWindow can hide itself via several internal paths (gear,
        # power, a clipboard click, empty-space click) that never route
        # back through main.py's toggle handler. Reading ``wheel.state
        # .is_visible`` from the hook thread is safe under CPython's GIL.
        self._is_wheel_visible = is_wheel_visible or (lambda: False)
        self._mouse_listener_factory = mouse_listener_factory or _default_mouse_listener_factory
        self._keyboard_listener_factory = (
            keyboard_listener_factory or _default_keyboard_listener_factory
        )
        self._mouse_listener: Any = None
        self._keyboard_listener: Any = None

    def start(self) -> None:
        """Install both global hooks (FR-1.1-1.4)."""
        self._mouse_listener = self._mouse_listener_factory(win32_event_filter=self._mouse_filter)
        self._mouse_listener.start()
        self._keyboard_listener = self._keyboard_listener_factory(
            win32_event_filter=self._keyboard_filter
        )
        self._keyboard_listener.start()

    def stop(self) -> None:
        """Uninstall both global hooks (FR-6.3: every exit path unhooks)."""
        if self._mouse_listener is not None:
            self._mouse_listener.stop()
            self._mouse_listener = None
        if self._keyboard_listener is not None:
            self._keyboard_listener.stop()
            self._keyboard_listener = None

    # --- win32_event_filter callbacks (run on the hook thread) ----------

    def _mouse_filter(self, msg: int, data: Any) -> bool:
        if is_middle_click_event(msg):
            if is_middle_click_down(msg):
                self.signals.toggle_wheel.emit()
            self._mouse_listener.suppress_event()
        return True

    def _keyboard_filter(self, msg: int, data: Any) -> bool:
        vk_code = data.vkCode
        if is_toggle_hotkey_event(msg, vk_code):
            if is_toggle_hotkey_down(msg, vk_code):
                self.signals.toggle_wheel.emit()
            self._keyboard_listener.suppress_event()
        elif self._is_wheel_visible() and is_escape_event(msg, vk_code):
            if is_escape_down(msg, vk_code):
                self.signals.esc_pressed.emit()
            self._keyboard_listener.suppress_event()
        return True
