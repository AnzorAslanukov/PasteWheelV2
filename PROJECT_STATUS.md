# PasteWheel — Project Status

**This is a living document.** It tracks the current build/test state of the
project and a chronological log of changes made during agent-assisted work
sessions, in addition to (not instead of) `SPEC.md` §13's milestone tracker.
`SPEC.md` remains the single source of truth for requirements; this file is
the working "what's actually been done, and when" record. Update it after
every meaningful change: new feature, bug fix, refactor, or build/package
action.

Last updated: 2026-09-14.

---

## 1. Current status snapshot

| Area | Status |
|---|---|
| Milestones M0–M6 (SPEC §12) | ✅ All complete and committed (see §3 history) |
| Automated test suite | ✅ 189 / 189 passing (`pytest -q`) |
| Lint | ✅ `ruff check .` clean |
| Manual checklist MC-01…MC-16 (SPEC §10) | ☐ Not yet run by the user |
| Packaged `.exe` (`dist/PasteWheel/PasteWheel.exe`) | ✅ Built and smoke-tested; reflects all changes through 2026-09-14 (see §3) |
| Uncommitted working-tree changes | ✅ None — working tree clean as of commit `bdcf0c2` |
| Remote | `https://github.com/AnzorAslanukov/PasteWheelV2.git` (linked 2026-09-14) |
| Decision log items still open (SPEC §14) | D3 (radial spacing reading) awaiting user OK; D6 (label rule) provisional |

## 2. Uncommitted changes

None currently. The expand-button visual-distinction work (§3, 2026-09-14
entry) was committed as `bdcf0c2` ("Feature: dashed border + corner glyph
for expand buttons; add PROJECT_STATUS.md"), which also added this file to
version control. This section will be repopulated if/when future work is
left uncommitted between sessions.

## 3. Change log (reverse chronological)

### 2026-09-14 — Expand-button visual distinction (dashed border + "+" glyph)

**Requested by user:** expand-type buttons should be visually distinct from
clipboard-type buttons on the wheel.

**Decision:** clipboard buttons keep a **solid** border; expand buttons get
a **dashed** border plus a small circular **"+" badge** in the top-right
corner of the button.

**Implementation** (`pastewheel/wheel_window.py`):
- `WheelButton.__init__` gained an `is_expand: bool = False` parameter.
  - QSS `border` style switches between `1px solid` and `1px dashed` based
    on `is_expand`.
  - When `is_expand=True`, a small `QLabel` badge (`EXPAND_GLYPH_DIAMETER =
    16px`, text `"+"`, `objectName="expand_glyph"`) is created as a child
    widget anchored to the button's top-right corner. It is
    `Qt.WA_TransparentForMouseEvents` and `Qt.NoFocus` so it never
    intercepts clicks meant for the button beneath it.
  - Non-expand buttons store `self._expand_glyph = None`.
- `_make_ring_button` now passes `is_expand=(button_type == "expand")` when
  constructing L1/L2 ring buttons. L3 buttons (clipboard-only, FR-3.3) and
  the fixed power/gear/center-"+" buttons are unaffected (always solid, no
  glyph) since they're never constructed with `is_expand=True`.

**Tests** (`tests/test_fr_wheel_window.py`), none tied to a specific FR id
since this is outside SPEC.md's FR list:
- `test_clipboard_button_has_solid_border_and_no_glyph`
- `test_expand_button_has_dashed_border_and_plus_glyph`
- `test_expand_glyph_is_transparent_for_mouse_events`
- `test_expand_button_click_still_works_with_glyph_present`
- `test_power_gear_and_plus_buttons_have_solid_border_and_no_glyph`
- `test_l3_clipboard_only_children_have_solid_border_and_no_glyph`

**Validation:** `pytest -q` → 189 passed (32 in this file, up from 26).
`ruff check .` → clean (one line-length fix applied during review).

**Build:** rebuilt `dist/PasteWheel/PasteWheel.exe` via
`pyinstaller PasteWheel.spec --noconfirm`; PyInstaller confirmed it rebuilt
because `wheel_window.py` had changed. Smoke-tested: launched, stayed
running, `%APPDATA%\PasteWheel\config.json` present and valid, process
terminated cleanly on request. Full MC-01–MC-16 spot-check remains the
user's to run (SPEC §11.4/§16).

**Status:** implemented, packaged, and committed as `bdcf0c2`.

---

### 2026-09-14 — Linked GitHub remote

Added the remote `origin` pointing at
`https://github.com/AnzorAslanukov/PasteWheelV2.git` and pushed `master`.

Before linking, audited the working tree for anything that needed a new
`.gitignore` rule. Conclusion: **no changes to `.gitignore` were needed** —
the existing rules (`.venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`,
`.ruff_cache/`, `build/`, `dist/`, `.coverage`) already correctly exclude
every generated/local artifact present on disk (verified via
`git status --ignored` and `git check-ignore -v`), including the 723 MB
`.venv/`, the 118 MB `dist/` packaged build, and the 7 MB `build/`
intermediate directory. No stray IDE folders, logs, or OS cruft
(`.vscode/`, `.idea/`, `*.egg-info`, `.env`, `Thumbs.db`, `desktop.ini`)
were found in the project directory.

The pending uncommitted changes from the prior entry (expand-button
glyph feature + this file) were committed first (`bdcf0c2`) so the pushed
history matches the built `.exe`.

---

### 2026-09-07 — M0–M6: initial v1.0 build (prior session)

All six milestones from SPEC §12 were implemented and committed in order,
each gated by a green `pytest -q` + clean `ruff check`:

| Commit | Milestone | Summary |
|---|---|---|
| `f7cf888` | M0+M1 | Scaffold (venv, deps, ruff config) + `config.py` + `validation.py` |
| `1ec2ec7` | M2 | `state.py` (wheel FSM + expand-toggle rules) + `geometry.py` (ring layout/clamping) |
| `156624e` | M3 | `wheel_window.py` (frameless/translucent/no-focus radial popup) |
| `c4526ea` | M4 | `settings_window.py` (button tree editor, validation, autostart/theme UI) |
| `f4458b8` | M5 | `hooks.py`, `tray.py`, `clipboard_service.py`, `autostart.py`, `main.py` wiring |
| `d0b08ca` | M6 | PyInstaller packaging (`PasteWheel.spec`) + `MANUAL_CHECKLIST.md` MC-16 instructions |

At the end of this session: all FRs in SPEC §7 implemented, `SPEC.md` §13
progress tracker marked all milestones ✅, and only the user-run manual
checklist (MC-01…MC-16) remained outstanding — which is still the case
today (see §1).

---

## 4. How to keep this document current

When making further changes to the project, append a new dated entry to
§3 (most recent on top) covering:
- What was requested and the decision made (if any judgment call was
  involved).
- Which files were touched and a summary of the implementation.
- Which tests were added/changed and the validation gate result
  (`pytest -q`, `ruff check .`).
- Whether `dist/PasteWheel/PasteWheel.exe` was rebuilt, and the smoke-test
  result if so.
- Update §1's snapshot table and §2's uncommitted-changes note to match.
