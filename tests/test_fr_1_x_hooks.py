"""Tests for pastewheel.hooks — FR-1.1-1.4, FR-4.2 (SPEC §4, §7.1).

Exercises the pure event-classification helpers directly, and drives
``HookManager``'s ``win32_event_filter`` callbacks with fake listeners so
no real OS-level hook is installed (impossible in a headless CI box, and
excluded from coverage "by design" per SPEC §10 — but the classification
logic itself is still fully testable).
"""

from __future__ import annotations

from types import SimpleNamespace

from pastewheel.hooks import (
    VK_ESCAPE,
    VK_OEM_3,
    WM_KEYDOWN,
    WM_KEYUP,
    WM_MBUTTONDOWN,
    WM_MBUTTONUP,
    WM_SYSKEYDOWN,
    WM_SYSKEYUP,
    HookManager,
    is_escape_down,
    is_escape_event,
    is_middle_click_down,
    is_middle_click_event,
    is_toggle_hotkey_down,
    is_toggle_hotkey_event,
)
from pastewheel.signals import HookSignals


class FakeListener:
    """A stand-in for a pynput Listener exposing start/stop/suppress_event."""

    def __init__(self, win32_event_filter=None, **_kwargs):
        self.filter = win32_event_filter
        self.started = False
        self.stopped = False
        self.suppressed_count = 0

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True

    def suppress_event(self):
        self.suppressed_count += 1


def _make_manager(qtbot=None, is_wheel_visible=None):
    signals = HookSignals()
    mice = []
    keyboards = []

    def mouse_factory(**kwargs):
        listener = FakeListener(**kwargs)
        mice.append(listener)
        return listener

    def keyboard_factory(**kwargs):
        listener = FakeListener(**kwargs)
        keyboards.append(listener)
        return listener

    manager = HookManager(
        signals,
        is_wheel_visible=is_wheel_visible,
        mouse_listener_factory=mouse_factory,
        keyboard_listener_factory=keyboard_factory,
    )
    return manager, mice, keyboards


def _kb_data(vk_code: int):
    return SimpleNamespace(vkCode=vk_code)


# --- Pure classification helpers ----------------------------------------


def test_fr_1_1_is_middle_click_down_and_event():
    assert is_middle_click_down(WM_MBUTTONDOWN) is True
    assert is_middle_click_down(WM_MBUTTONUP) is False
    assert is_middle_click_event(WM_MBUTTONDOWN) is True
    assert is_middle_click_event(WM_MBUTTONUP) is True
    assert is_middle_click_event(WM_KEYDOWN) is False


def test_fr_1_2_is_toggle_hotkey_down_requires_syskeydown_and_backtick_vk():
    assert is_toggle_hotkey_down(WM_SYSKEYDOWN, VK_OEM_3) is True
    assert is_toggle_hotkey_down(WM_KEYDOWN, VK_OEM_3) is False  # no Alt held
    assert is_toggle_hotkey_down(WM_SYSKEYDOWN, VK_ESCAPE) is False
    assert is_toggle_hotkey_event(WM_SYSKEYUP, VK_OEM_3) is True


def test_fr_1_4_is_escape_down_and_event():
    assert is_escape_down(WM_KEYDOWN, VK_ESCAPE) is True
    assert is_escape_down(WM_SYSKEYDOWN, VK_ESCAPE) is True
    assert is_escape_down(WM_KEYDOWN, VK_OEM_3) is False
    assert is_escape_event(WM_KEYUP, VK_ESCAPE) is True
    assert is_escape_event(WM_SYSKEYUP, VK_ESCAPE) is True


# --- HookManager wiring (FR-1.1/1.2/1.3, FR-4.2) -------------------------


def test_fr_1_1_middle_click_down_emits_toggle_and_is_always_suppressed():
    manager, mice, _ = _make_manager()
    manager.start()
    received = []
    manager.signals.toggle_wheel.connect(lambda: received.append(True))

    manager._mouse_filter(WM_MBUTTONDOWN, SimpleNamespace())

    assert len(received) == 1
    assert mice[0].suppressed_count == 1


def test_fr_1_1_middle_click_up_is_suppressed_but_does_not_toggle():
    """FR-1.1: middle-click is swallowed system-wide at all times."""
    manager, mice, _ = _make_manager()
    manager.start()
    received = []
    manager.signals.toggle_wheel.connect(lambda: received.append(True))

    manager._mouse_filter(WM_MBUTTONUP, SimpleNamespace())

    assert received == []
    assert mice[0].suppressed_count == 1


def test_fr_1_2_alt_backtick_down_emits_toggle_and_is_suppressed():
    manager, _, keyboards = _make_manager()
    manager.start()
    received = []
    manager.signals.toggle_wheel.connect(lambda: received.append(True))

    manager._keyboard_filter(WM_SYSKEYDOWN, _kb_data(VK_OEM_3))

    assert len(received) == 1
    assert keyboards[0].suppressed_count == 1


def test_fr_4_2_unrelated_keys_are_not_suppressed():
    """FR-4.2: v1 intercepts no keyboard input other than the triggers/Esc."""
    manager, _, keyboards = _make_manager(is_wheel_visible=lambda: True)
    manager.start()

    manager._keyboard_filter(WM_KEYDOWN, _kb_data(0x43))  # the 'C' key

    assert keyboards[0].suppressed_count == 0


def test_fr_1_4_esc_suppressed_only_while_wheel_visible():
    visible = {"value": False}
    manager, _, keyboards = _make_manager(is_wheel_visible=lambda: visible["value"])
    manager.start()
    received = []
    manager.signals.esc_pressed.connect(lambda: received.append(True))

    manager._keyboard_filter(WM_KEYDOWN, _kb_data(VK_ESCAPE))
    assert received == []
    assert keyboards[0].suppressed_count == 0

    visible["value"] = True
    manager._keyboard_filter(WM_KEYDOWN, _kb_data(VK_ESCAPE))
    assert len(received) == 1
    assert keyboards[0].suppressed_count == 1


def test_fr_6_3_stop_unhooks_both_listeners():
    manager, mice, keyboards = _make_manager()
    manager.start()

    manager.stop()

    assert mice[0].stopped is True
    assert keyboards[0].stopped is True
    assert manager._mouse_listener is None
    assert manager._keyboard_listener is None


def test_hook_manager_start_installs_both_listeners():
    manager, mice, keyboards = _make_manager()

    manager.start()

    assert mice[0].started is True
    assert keyboards[0].started is True
