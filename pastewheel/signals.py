"""Qt signal bridge for cross-thread hook communication (SPEC §4).

``pynput``'s mouse/keyboard listeners each run on their own background
thread. Qt widgets must only ever be touched from the main (GUI) thread.
This module defines the single :class:`~PySide6.QtCore.QObject` through
which :mod:`pastewheel.hooks` communicates wheel-trigger events to the main
thread: signals emitted from a hook thread are delivered to connected
slots via Qt's automatic queued cross-thread connection, so hook callbacks
never touch any widget directly (SPEC §4: "hook threads never touch Qt
widgets directly").
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class HookSignals(QObject):
    """Signals emitted by :class:`pastewheel.hooks.HookManager`.

    - ``toggle_wheel``: emitted on a middle-click-down (FR-1.1/FR-1.3) or
      the ``Alt+\\``` chord (FR-1.2). The main-thread slot shows the wheel
      at the pointer if hidden, or hides it if visible — both triggers
      share identical toggle semantics (SPEC §5).
    - ``esc_pressed``: emitted on ``Esc`` while the wheel is visible
      (FR-1.4); the hook only suppresses/emits this while visible, so the
      focused app receives ``Esc`` normally whenever the wheel is hidden.
    """

    toggle_wheel = Signal()
    esc_pressed = Signal()
