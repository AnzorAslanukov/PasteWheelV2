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
| Uncommitted working-tree changes | ⚠️ Yes — see §2 |
| Decision log items still open (SPEC §14) | D3 (radial spacing reading) awaiting user OK; D6 (label rule) provisional |

## 2. Uncommitted changes

As of the last update, the working tree has **unstaged, uncommitted**
changes relative to the `M6: PyInstaller packaging + MC-16 instructions`
commit:

- `pastewheel/wheel_window.py` — expand-vs-clipboard visual distinction
  (dashed border + "+" corner glyph). See §3, 2026-09-14 entry, for details.
- `tests/test_fr_wheel_window.py` — new tests covering the above.

This work is **not tied to a SPEC.md FR** (it's a user-requested UX
enhancement layered on top of the finished v1.0 milestones), so per
`.clinerules` rule 7 ("commit after each green milestone") it does not map
cleanly to a milestone commit. It is currently only reflected in the
packaged `.exe` build, not in git history. **Recommend a manual commit**
(e.g. `git add -A && git commit -m "Feature: dashed border + corner glyph
for expand buttons"`) once the user is happy with it, so the packaged build
and the repo history stay in sync.

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

**Status:** implemented and packaged; **not yet committed to git** (see §2).

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
