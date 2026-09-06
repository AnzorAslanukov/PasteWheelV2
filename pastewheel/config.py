"""Config persistence for PasteWheel (SPEC §7.7, §9).

Handles the on-disk ``config.json`` document: default creation (FR-7.2),
atomic writes (FR-7.4), and corruption recovery (FR-7.3). Schema validation
itself lives in :mod:`pastewheel.validation` and is reused here on load.

Callers (e.g. ``main.py``, tests) pass an explicit config *path*; this
module never guesses at ``%APPDATA%`` unless :func:`default_config_path`
is invoked explicitly, keeping tests confined to ``tmp_path`` (per
``.clinerules`` #6).
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pastewheel.validation import validate_config

SCHEMA_VERSION = 1
CONFIG_DIR_NAME = "PasteWheel"
CONFIG_FILE_NAME = "config.json"


def default_config() -> dict:
    """Return the default config document (FR-7.2: zero L1 buttons)."""
    return {
        "schema_version": SCHEMA_VERSION,
        "settings": {"autostart": False, "theme": "system"},
        "buttons": [],
    }


def default_config_dir() -> Path:
    """Return ``%APPDATA%\\PasteWheel`` (FR-7.1). Not used by tests directly."""
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise RuntimeError("APPDATA environment variable is not set.")
    return Path(appdata) / CONFIG_DIR_NAME


def default_config_path() -> Path:
    """Return ``%APPDATA%\\PasteWheel\\config.json`` (FR-7.1)."""
    return default_config_dir() / CONFIG_FILE_NAME


@dataclass
class ConfigLoadResult:
    """Result of :func:`load_config`.

    ``recovered`` is True when the on-disk file was missing, unreadable, or
    failed schema validation and a default config was written in its place
    (FR-7.2/FR-7.3). ``bad_file_path`` is set only when an existing corrupt
    file was renamed aside (FR-7.3); it is ``None`` on a clean first run.
    """

    data: dict
    recovered: bool
    bad_file_path: Path | None


def _atomic_write_json(path: Path, data: dict) -> None:
    """Write ``data`` as pretty-printed UTF-8 JSON atomically (FR-7.4).

    Writes to a temp file in the same directory, then replaces the target
    so a crash mid-write never leaves a half-written config.json.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=CONFIG_FILE_NAME + ".", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp_name, path)
    except Exception:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def save_config(path: Path, data: dict) -> None:
    """Persist ``data`` to ``path`` atomically (FR-7.4)."""
    _atomic_write_json(Path(path), data)


def _bad_file_path(path: Path) -> Path:
    """Build the ``config.json.bad-<timestamp>`` sibling path (FR-7.3)."""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    return path.with_name(f"{path.name}.bad-{timestamp}")


def load_config(path: Path) -> ConfigLoadResult:
    """Load, validate, and (if needed) recover the config at ``path``.

    - Missing file: write and return the default (FR-7.2), not "recovered".
    - Unreadable/invalid JSON or schema violation: rename the bad file
      aside as ``config.json.bad-<timestamp>``, write a fresh default, and
      report ``recovered=True`` with the bad file's path (FR-7.3).
    - Otherwise: return the parsed, validated document as-is.
    """
    path = Path(path)

    if not path.exists():
        data = default_config()
        save_config(path, data)
        return ConfigLoadResult(data=data, recovered=False, bad_file_path=None)

    try:
        raw_text = path.read_text(encoding="utf-8")
        data = json.loads(raw_text)
        errors = validate_config(data)
        if errors:
            raise ValueError("; ".join(errors))
    except (OSError, ValueError) as exc:
        bad_path = _bad_file_path(path)
        try:
            path.replace(bad_path)
        except OSError:
            bad_path = None
        default = default_config()
        save_config(path, default)
        _ = exc  # error text not surfaced here; caller may log/notify.
        return ConfigLoadResult(data=default, recovered=True, bad_file_path=bad_path)

    return ConfigLoadResult(data=data, recovered=False, bad_file_path=None)
