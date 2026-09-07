# PasteWheel — Manual Checklist (dev build, before packaging)

Run: activate .venv, then `python -m pastewheel`. Mark Pass/Fail with a note.
All must pass before milestone M6 (MC-16 re-runs these on the .exe).

- [ ] MC-01 Tray icon appears at startup
- [ ] MC-02 Middle-click shows wheel at pointer; no browser autoscroll/new tab
- [ ] MC-03 `Alt+\`` toggles wheel; `Esc` closes it and is NOT received by the focused app
- [ ] MC-04 Left-click on empty space inside or outside the wheel closes it
- [ ] MC-05 Clipboard button copies its string; paste into Notepad shows exact text incl. emoji
- [ ] MC-06 Expand toggle shows/hides children; sibling exclusivity; all toggles reset after hide
- [ ] MC-07 Power button exits fully; tray icon disappears
- [ ] MC-08 Gear, center "+", tray menu all open settings; Save persists across restart
- [ ] MC-09 Deleting an expand warns with descendant count and removes subtree
- [ ] MC-10 Autostart toggle adds/removes Startup entry (verify only with packaged .exe)
- [ ] MC-11 Wheel appears on the monitor holding the pointer (multi-monitor)
- [ ] MC-12 High-DPI: buttons crisp and correctly placed
- [ ] MC-13 Second launch: "PasteWheel is already running." tray balloon, no second tray icon
- [ ] MC-14 Garbage config.json → defaults recreated + config.json.bad-<timestamp> created
- [ ] MC-15 Windows dark/light switch: wheel follows; Settings override works immediately
- [ ] MC-16 (after M6) packaged .exe passes spot checks of MC-01–MC-15

## Packaging (M6)

Build the onedir executable (from the activated `.venv`, repo root):

```
pyinstaller PasteWheel.spec
```

(equivalent to, and reproducing, the one-shot command:
`pyinstaller --windowed --icon assets/icon.ico --name PasteWheel --add-data "assets;assets" pastewheel/__main__.py`)

Output: `dist/PasteWheel/PasteWheel.exe` plus its `dist/PasteWheel/_internal/`
support folder — copy/zip the whole `dist/PasteWheel/` folder to distribute,
never just the `.exe` alone.

Run `dist/PasteWheel/PasteWheel.exe` directly (double-click, or from a
terminal with no arguments) and re-run MC-01–MC-15 above against it for
MC-16. Notes specific to the packaged build:

- MC-10 (autostart): only meaningfully testable against the packaged `.exe`,
  since `autostart.py`'s registry `Run` value stores `sys.executable`, which
  is `python.exe` (not `PasteWheel.exe`) when running from source. Toggle
  the autostart checkbox in Settings, then check
  `HKCU\Software\Microsoft\Windows\CurrentVersion\Run\PasteWheel` (or
  Task Manager → Startup apps) for a `PasteWheel.exe` entry.
- `build/` and `dist/` are gitignored (build output only); `PasteWheel.spec`
  is committed so the build is reproducible without retyping flags.
- Implementer-verified (M6, technical smoke test — NOT a substitute for the
  user's MC-01–MC-16 pass): the packaged exe launches, the tray icon renders
  from the bundled `assets/icon.ico`, `config.json` is created under the
  real `%APPDATA%\PasteWheel\`, and the process exits cleanly.