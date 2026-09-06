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
- [ ] MC-13 Second launch: "PasteWheel is already running." dialog, no second tray icon
- [ ] MC-14 Garbage config.json → defaults recreated + config.json.bad-<timestamp> created
- [ ] MC-15 Windows dark/light switch: wheel follows; Settings override works immediately
- [ ] MC-16 (after M6) packaged .exe passes spot checks of MC-01–MC-15