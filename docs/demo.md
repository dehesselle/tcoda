# Demo

```sh
python -m tcoda          # wherever tcoda is installed
uv run python -m tcoda   # from this repository
```

This is the same idea as `python -m textual`. The demo is a small browser
over tcoda's own installed source files, with every widget and dialog in its
natural place. All of it is ordinary consumer code, so
[`src/tcoda/demo/`](../src/tcoda/demo/) doubles as a worked example.

| Component | Where to find it |
| --- | --- |
| [Header](widgets/Header.md) | Top row. The middle tracks the screen title, which is the directory being browsed. Click the left area for About, the right one for versions. |
| [MenuBar](widgets/MenuBar.md) | F9, or click where it appears. Items use `@on(MenuItem.Pressed)` (File, Dialogs) and `action=` strings (View). View has one disabled item. |
| [Resizable](widgets/Resizable.md) | The directory tree on the left. Drag its right border. |
| [DataTable](widgets/DataTable.md) | The file list. Click a header to sort. Size and Modified show rounded values but rank by the exact bytes and mtime. Hover a cell for its tooltip. |
| [Footer](widgets/Footer.md) | Bottom row: `F9`, `F1` and `^q` pinned, the other keys sorted, and a countdown plus a file count in the status corner. |
| [Countdown](widgets/Countdown.md) | Footer status corner. It spins during an auto-refresh. Turning auto-refresh off in the settings hides it. |
| [LogViewer](widgets/LogViewer.md) | F1. Four `tcoda.demo.*` loggers write to it, so the source filter has something to filter. |
| [Chords](chords.md) and [ChordViewer](widgets/ChordViewer.md) | `ctrl+k` then a pause lists every chord: `s …` sorts, `d …` opens each dialog, `r` refreshes, `t` changes theme. |
| [Terminal title](terminal_title.md) | The terminal's window or tab title reads "tcoda demo" while the demo runs, and goes back to what it was on exit. |
| [ConfirmDialog](dialogs/ConfirmDialog.md) | Dialogs → Confirm, and Delete files (the `danger=True, focus_cancel=True` variant, which deletes nothing). |
| [Dialog](dialogs/Dialog.md) | Dialogs → Filter (F2): `FilterDialog`, the demo's own dialog on the shared chrome. |
| [AboutDialog](dialogs/AboutDialog.md) | Help → About: the demo's own about-text, with `$version` filled in through `variables=`. |
| [SettingsDialog](dialogs/SettingsDialog.md) and [settings](settings.md) | File → Settings. The dotted `Demo.Refresh` and `Demo.Table` groups include a `choices=` setting and a `SettingAction`. Changes apply when the dialog closes. |

- **Settings persist.** They go to the per-user settings file of an app named
  `tcoda-demo`, and only overridden values are written.
- **`tcoda.demo` is an app, not a library module.** Importing it declares the
  demo's settings and points `tcoda.settings.config` at that file, so nothing
  else should import it.
