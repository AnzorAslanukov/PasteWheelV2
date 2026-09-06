"""Wheel FSM + expand-toggle visibility rules (SPEC §5).

Pure state container, no Qt/OS dependency: ``wheel_window.py`` drives this
from real triggers/clicks; tests drive it directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

# Expand buttons exist only at L1 and L2 (FR-3.3: L3 is clipboard-only).
EXPAND_LEVELS = (1, 2)
RING_LEVELS = (1, 2, 3)


class WheelPhase(Enum):
    """The two states of the wheel FSM (SPEC §5)."""

    HIDDEN = "hidden"
    VISIBLE = "visible"


@dataclass
class WheelState:
    """Wheel FSM + expand-toggle visibility rules.

    FSM: ``HIDDEN --(show)--> VISIBLE``; ``VISIBLE --(hide)--> HIDDEN``.
    Only one expand button per ring level (L1, L2) may be ON at a time;
    toggling one ON auto-toggles any other at that level OFF (D1). All
    toggles reset to OFF whenever the wheel hides (FR-3.4).
    """

    phase: WheelPhase = WheelPhase.HIDDEN
    _on_expand: dict[int, str | None] = field(default_factory=lambda: {1: None, 2: None})

    @property
    def is_visible(self) -> bool:
        return self.phase is WheelPhase.VISIBLE

    def show(self) -> None:
        """HIDDEN -> VISIBLE (FR-1.1 middle-click / FR-1.2 Alt+`)."""
        self.phase = WheelPhase.VISIBLE

    def hide(self) -> None:
        """VISIBLE -> HIDDEN; resets all expand toggles (FR-3.4)."""
        self.phase = WheelPhase.HIDDEN
        self._on_expand = {1: None, 2: None}

    def toggle(self) -> None:
        """Toggle HIDDEN<->VISIBLE (FR-1.2 Alt+` when already visible)."""
        if self.is_visible:
            self.hide()
        else:
            self.show()

    def on_expand_id(self, level: int) -> str | None:
        """id of the currently-ON expand button at `level` (1 or 2), else None."""
        self._require_expand_level(level)
        return self._on_expand[level]

    def is_expand_on(self, button_id: str, level: int) -> bool:
        """Whether `button_id` (an expand button at `level`) is currently ON."""
        return self.on_expand_id(level) == button_id

    def toggle_expand(self, button_id: str, level: int) -> bool:
        """Toggle expand button `button_id` at `level` (FR-3.2).

        Turning one ON auto-turns any sibling at that level OFF: only one
        expand button per level may be ON at a time (D1, §5). Clicking the
        currently-ON button turns it OFF. Returns the button's new
        ON (True) / OFF (False) state.
        """
        self._require_expand_level(level)
        if self._on_expand[level] == button_id:
            self._on_expand[level] = None
            return False
        self._on_expand[level] = button_id
        return True

    def is_level_visible(self, level: int) -> bool:
        """Whether ring `level` (1, 2, or 3) is currently shown (§5).

        L1 is visible whenever the wheel is visible (FR-2.2). L2 is
        visible iff some L1 expand is ON. L3 is visible iff some visible
        L2 expand is ON.
        """
        if level not in RING_LEVELS:
            raise ValueError(f"Invalid ring level: {level!r}. Must be 1, 2, or 3.")
        if not self.is_visible:
            return False
        if level == 1:
            return True
        if level == 2:
            return self._on_expand[1] is not None
        return self.is_level_visible(2) and self._on_expand[2] is not None

    @staticmethod
    def _require_expand_level(level: int) -> None:
        if level not in EXPAND_LEVELS:
            raise ValueError(
                f"Invalid expand level: {level!r}. Expand buttons exist only at "
                "levels 1-2 (FR-3.3: L3 is clipboard-only)."
            )
