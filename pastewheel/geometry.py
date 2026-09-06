"""Wheel geometry: ring positions, screen clamping (SPEC §6, §7.2).

Pure math, no Qt/OS dependency, so it is fully unit-testable without a
display. Positions are returned in the same coordinate system as the
caller's center point (typically screen pixels, y increasing downward,
matching Qt's convention) so ``wheel_window.py`` can place buttons
directly.
"""

from __future__ import annotations

import math

from pastewheel.validation import MAX_L1_BUTTONS, MAX_L2_BUTTONS, MAX_L3_BUTTONS

# --- Constants from SPEC §6 ------------------------------------------------

BUTTON_DIAMETER = 56
BUTTON_RADIUS = BUTTON_DIAMETER / 2

L1_RADIUS = 110
L2_RADIUS = 195
L3_RADIUS = 280

_LEVEL_RADII = {1: L1_RADIUS, 2: L2_RADIUS, 3: L3_RADIUS}
_LEVEL_CAPS = {1: MAX_L1_BUTTONS, 2: MAX_L2_BUTTONS, 3: MAX_L3_BUTTONS}

Point = tuple[float, float]
Rect = tuple[float, float, float, float]  # left, top, right, bottom


def evenly_spaced_angles_deg(count: int) -> list[float]:
    """Return `count` angles (degrees), 360/N apart, starting at 0.

    0 degrees corresponds to 12 o'clock; angles increase clockwise (SPEC
    §6 D3: radial equidistant symmetry).
    """
    if count <= 0:
        return []
    step = 360.0 / count
    return [i * step for i in range(count)]


def _point_on_circle(center: Point, radius: float, angle_deg: float) -> Point:
    """A point `radius` from `center`, `angle_deg` clockwise from 12 o'clock.

    Uses screen/Qt coordinates (y increases downward): at angle 0 the point
    is directly above center (12 o'clock); at 90 it is directly to the
    right (3 o'clock).
    """
    theta = math.radians(angle_deg)
    cx, cy = center
    x = cx + radius * math.sin(theta)
    y = cy - radius * math.cos(theta)
    return (x, y)


def ring_positions(level: int, center: Point, count: int) -> list[Point]:
    """Evenly-spaced button center points for ring `level` (FR-2.1, §6 D3).

    `level` selects the ring radius (1, 2, or 3). Raises ``ValueError`` if
    `level` is not 1-3, `count` is negative, or `count` exceeds that ring's
    capacity (FR-2.1: L1 max 8, L2 max 16, L3 max 32).
    """
    if level not in _LEVEL_RADII:
        raise ValueError(f"Invalid ring level: {level!r}. Must be 1, 2, or 3.")
    if count < 0:
        raise ValueError("count must be >= 0.")
    cap = _LEVEL_CAPS[level]
    if count > cap:
        raise ValueError(f"Ring level {level} supports at most {cap} buttons, got {count}.")
    radius = _LEVEL_RADII[level]
    angles = evenly_spaced_angles_deg(count)
    return [_point_on_circle(center, radius, angle) for angle in angles]


def wheel_outer_radius(max_visible_level: int) -> float:
    """Outer extent (ring radius + button radius) of the visible wheel.

    `max_visible_level` is the highest ring level currently shown (1, 2, or
    3); used for screen-clamping (FR-2.5) so the whole wheel, not just its
    center, stays on-screen.
    """
    if max_visible_level not in _LEVEL_RADII:
        raise ValueError(f"Invalid ring level: {max_visible_level!r}. Must be 1, 2, or 3.")
    return _LEVEL_RADII[max_visible_level] + BUTTON_RADIUS


def clamp_center_to_screen(center: Point, outer_radius: float, screen_rect: Rect) -> Point:
    """Clamp `center` so a wheel of `outer_radius` stays on `screen_rect` (FR-2.5).

    If the screen is smaller than the wheel along an axis, center on that
    axis instead of forcing an impossible clamp.
    """
    cx, cy = center
    left, top, right, bottom = screen_rect

    min_x, max_x = left + outer_radius, right - outer_radius
    cx = (left + right) / 2 if min_x > max_x else min(max(cx, min_x), max_x)

    min_y, max_y = top + outer_radius, bottom - outer_radius
    cy = (top + bottom) / 2 if min_y > max_y else min(max(cy, min_y), max_y)

    return (cx, cy)


def power_button_position(center: Point) -> Point:
    """Power button position: upper-left corner of the L1 ring's bounding
    box, fixed regardless of L2/L3 visibility (§6 Q2)."""
    cx, cy = center
    offset = L1_RADIUS + BUTTON_RADIUS
    return (cx - offset, cy - offset)


def gear_button_position(center: Point) -> Point:
    """Gear button position: upper-right corner of the L1 ring's bounding
    box, fixed regardless of L2/L3 visibility (§6 Q2)."""
    cx, cy = center
    offset = L1_RADIUS + BUTTON_RADIUS
    return (cx + offset, cy - offset)
