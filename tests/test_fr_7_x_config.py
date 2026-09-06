"""Tests for pastewheel.config — FR-7.1 through FR-7.4 (SPEC §7.7, §9)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pastewheel import config


def test_fr_7_2_first_run_creates_default_config_with_zero_l1_buttons(tmp_path: Path):
    """FR-7.2: first run creates a default config (zero L1 buttons)."""
    cfg_path = tmp_path / "config.json"

    result = config.load_config(cfg_path)

    assert cfg_path.exists()
    assert result.recovered is False
    assert result.bad_file_path is None
    assert result.data["buttons"] == []
    assert result.data["schema_version"] == config.SCHEMA_VERSION
    assert result.data["settings"] == {"autostart": False, "theme": "system"}


def test_fr_7_1_config_is_utf8_pretty_printed_with_schema_version(tmp_path: Path):
    """FR-7.1: UTF-8, pretty-printed, includes schema_version."""
    cfg_path = tmp_path / "config.json"
    config.load_config(cfg_path)

    raw = cfg_path.read_text(encoding="utf-8")
    assert "\n" in raw  # pretty-printed, not a single line
    assert '"schema_version"' in raw
    parsed = json.loads(raw)
    assert parsed["schema_version"] == 1


def test_fr_7_1_default_path_is_under_appdata_pastewheel(monkeypatch, tmp_path: Path):
    """FR-7.1: config lives at %APPDATA%\\PasteWheel\\config.json."""
    monkeypatch.setenv("APPDATA", str(tmp_path))
    path = config.default_config_path()
    assert path == tmp_path / "PasteWheel" / "config.json"


def test_fr_7_3_corrupt_json_is_renamed_and_default_recreated(tmp_path: Path):
    """FR-7.3: corrupt config renamed to config.json.bad-<timestamp>."""
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text("{ this is not valid json", encoding="utf-8")

    result = config.load_config(cfg_path)

    assert result.recovered is True
    assert result.bad_file_path is not None
    assert result.bad_file_path.exists()
    assert result.bad_file_path.name.startswith("config.json.bad-")
    assert cfg_path.exists()
    assert json.loads(cfg_path.read_text(encoding="utf-8"))["buttons"] == []


def test_fr_7_3_schema_invalid_config_is_renamed_and_default_recreated(tmp_path: Path):
    """FR-7.3: a config that fails schema validation is also recovered."""
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(
        json.dumps({"schema_version": 1, "settings": {"theme": "purple"}, "buttons": []}),
        encoding="utf-8",
    )

    result = config.load_config(cfg_path)

    assert result.recovered is True
    assert result.bad_file_path is not None
    assert result.bad_file_path.exists()
    assert result.data["settings"]["theme"] == "system"


def test_fr_7_3_unknown_top_level_field_triggers_recovery(tmp_path: Path):
    """FR-7.3 / §9.2: unknown fields are rejected on load."""
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "settings": {"autostart": False, "theme": "system"},
                "buttons": [],
                "extra_unknown_field": True,
            }
        ),
        encoding="utf-8",
    )

    result = config.load_config(cfg_path)

    assert result.recovered is True


def test_fr_7_4_writes_are_atomic_no_leftover_temp_files(tmp_path: Path):
    """FR-7.4: writes are atomic (temp file + replace); no temp file remains."""
    cfg_path = tmp_path / "config.json"
    config.save_config(cfg_path, config.default_config())

    assert cfg_path.exists()
    leftover_tmp_files = [p for p in tmp_path.iterdir() if p.suffix == ".tmp"]
    assert leftover_tmp_files == []


def test_fr_7_4_save_config_round_trips_valid_data(tmp_path: Path):
    """FR-7.4: saved data can be loaded back unchanged."""
    cfg_path = tmp_path / "config.json"
    data = config.default_config()
    data["buttons"] = [
        {"id": "abc123", "type": "clipboard", "label": "TST", "tooltip": "", "string": "hi"}
    ]

    config.save_config(cfg_path, data)
    result = config.load_config(cfg_path)

    assert result.recovered is False
    assert result.data == data


def test_fr_7_1_load_config_valid_existing_file_is_untouched(tmp_path: Path):
    """A valid pre-existing config.json is parsed as-is, not recreated."""
    cfg_path = tmp_path / "config.json"
    data = config.default_config()
    cfg_path.write_text(json.dumps(data), encoding="utf-8")

    result = config.load_config(cfg_path)

    assert result.recovered is False
    assert result.bad_file_path is None
    assert result.data == data


@pytest.mark.parametrize("missing_dir_depth", [1, 2])
def test_fr_7_2_creates_missing_parent_directories(tmp_path: Path, missing_dir_depth: int):
    """First run also creates missing parent directories (e.g. %APPDATA%\\PasteWheel)."""
    nested = tmp_path
    for i in range(missing_dir_depth):
        nested = nested / f"level{i}"
    cfg_path = nested / "config.json"

    result = config.load_config(cfg_path)

    assert cfg_path.exists()
    assert result.recovered is False
