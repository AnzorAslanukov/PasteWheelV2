"""Tests for pastewheel.geometry — FR-2.1, FR-2.5 and §6 D3 spacing rules."""

from __future__ import annotations

import math

import pytest

from pastewheel import geometry

# --- FR-2.1: ring capacities L1<=8, L2<=16, L3<=32 -----------------------


def test_fr_2_1_l1_ring_accepts_up_to_8_buttons():
    positions = geometry.ring_positions(1, (0, 0), 8)
    assert len(positions) == 8


def test_fr_2_1_l1_ring_rejects_more_than_8_buttons():
    with pytest.raises(ValueError):
        geometry.ring_positions(1, (0, 0), 9)


def test_fr_2_1_l2_ring_accepts_up_to_16_buttons():
    positions = geometry.ring_positions(2, (0, 0), 16)
    assert len(positions) == 16


def test_fr_2_1_l2_ring_rejects_more_than_16_buttons():
    with pytest.raises(ValueError):
        geometry.ring_positions(2, (0, 0), 17)


def test_fr_2_1_l3_ring_accepts_up_to_32_buttons():
    positions = geometry.ring_positions(3, (0, 0), 32)
    assert len(positions) == 32


def test_fr_2_1_l3_ring_rejects_more_than_32_buttons():
    with pytest.raises(ValueError):
        geometry.ring_positions(3, (0, 0), 33)


def test_fr_2_1_invalid_level_is_rejected():
    with pytest.raises(ValueError):
        geometry.ring_positions(4, (0, 0), 1)


def test_fr_2_1_negative_count_is_rejected():
    with pytest.raises(ValueError):
        geometry.ring_positions(1, (0, 0), -1)


def test_fr_2_1_zero_count_returns_empty_list():
    assert geometry.ring_positions(1, (0, 0), 0) == []


# --- §6 D3: radial equidistant symmetry: 360/N spacing, 12 o'clock first -


def test_fr_2_1_even_spacing_angles_are_360_over_n_apart():
    angles = geometry.evenly_spaced_angles_deg(4)
    assert angles == [0, 90, 180, 270]


def test_fr_2_1_even_spacing_first_button_at_12_oclock():
    center = (100.0, 100.0)
    positions = geometry.ring_positions(1, center, 1)
    x, y = positions[0]
    # 12 o'clock: directly above center (smaller y, same x) in screen coords.
    assert math.isclose(x, center[0], abs_tol=1e-9)
    assert y < center[1]


def test_fr_2_1_even_spacing_second_of_two_is_at_6_oclock():
    center = (100.0, 100.0)
    positions = geometry.ring_positions(1, center, 2)
    _, y0 = positions[0]
    x1, y1 = positions[1]
    assert math.isclose(x1, center[0], abs_tol=1e-9)
    assert y1 > center[1]
    assert math.isclose(y1 - center[1], center[1] - y0, abs_tol=1e-9)


def test_fr_2_1_positions_are_radius_away_from_center():
    center = (50.0, 50.0)
    positions = geometry.ring_positions(1, center, 5)
    for x, y in positions:
        dist = math.hypot(x - center[0], y - center[1])
        assert math.isclose(dist, geometry.L1_RADIUS, abs_tol=1e-9)


# --- FR-2.5: wheel geometry is clamped to the pointer's monitor ---------


def test_fr_2_5_clamp_keeps_wheel_fully_on_screen_near_edge():
    screen = (0, 0, 1920, 1080)
    outer_radius = geometry.wheel_outer_radius(1)
    center = (5, 5)  # near top-left corner

    cx, cy = geometry.clamp_center_to_screen(center, outer_radius, screen)

    assert cx >= screen[0] + outer_radius
    assert cy >= screen[1] + outer_radius
    assert cx <= screen[2] - outer_radius
    assert cy <= screen[3] - outer_radius


def test_fr_2_5_clamp_is_noop_when_wheel_fits_comfortably():
    screen = (0, 0, 1920, 1080)
    outer_radius = geometry.wheel_outer_radius(1)
    center = (960, 540)

    clamped = geometry.clamp_center_to_screen(center, outer_radius, screen)

    assert clamped == center


def test_fr_2_5_clamp_centers_when_screen_smaller_than_wheel():
    outer_radius = geometry.wheel_outer_radius(3)
    tiny_screen = (0, 0, 100, 100)
    center = (10, 10)

    cx, cy = geometry.clamp_center_to_screen(center, outer_radius, tiny_screen)

    assert cx == 50
    assert cy == 50


def test_fr_2_5_outer_radius_grows_with_visible_level():
    r1 = geometry.wheel_outer_radius(1)
    r2 = geometry.wheel_outer_radius(2)
    r3 = geometry.wheel_outer_radius(3)
    assert r1 < r2 < r3


def test_fr_2_5_outer_radius_invalid_level_is_rejected():
    with pytest.raises(ValueError):
        geometry.wheel_outer_radius(0)


# --- §6 Q2: power/gear fixed relative to the L1 ring's bounding box -----


def test_power_gear_positions_are_symmetric_about_center():
    center = (200.0, 150.0)
    power = geometry.power_button_position(center)
    gear = geometry.gear_button_position(center)

    assert power[1] == gear[1]  # same y (both upper corners)
    assert power[0] < center[0] < gear[0]  # power left, gear right
