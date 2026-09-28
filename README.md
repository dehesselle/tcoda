# tcw — Textual Common Widgets

Widgets shared between several Textual apps (`snowcone`, `snakecam`, `vc`),
extracted so a fix is made once rather than three times.

Consumed as an editable path dependency while it is still being tracked from
source:

```toml
dependencies = ["tcw>=0.1"]

[tool.uv.sources]
tcw = { path = "../tcw", editable = true }
```

## Demo

`python -m tcw` runs a demo app that uses every widget and dialog, the way
`python -m textual` runs Textual's own. See [docs/demo.md](docs/demo.md) for
where each component appears in it.

## Widgets — `tcw.widgets`

| Widget | Description |
| --- | --- |
| [Header](docs/widgets/Header.md) | One-line header with clickable left, middle and right areas |
| [Footer](docs/widgets/Footer.md) | Key bar with pinned keys, sorting, and a status corner that holds widgets |
| [Countdown](docs/widgets/Countdown.md) | Seconds counter with a spinner for work in flight |
| [MenuBar](docs/widgets/MenuBar.md) | Midnight-Commander style pulldown menu bar, declared inline |
| [LogViewer](docs/widgets/LogViewer.md) | Slide-down panel showing the app's `logging` output, filterable by level and source |
| [ChordViewer](docs/widgets/ChordViewer.md) | which-key style panel listing what can follow a pending chord |
| [DataTable](docs/widgets/DataTable.md) | Textual's `DataTable` plus clickable sorting and per-cell tooltips |
| [Resizable](docs/widgets/Resizable.md) | Mixin that makes a pane resizable by dragging its border |

## Dialogs — `tcw.dialogs`

| Dialog | Description |
| --- | --- |
| [Dialog](docs/dialogs/Dialog.md) | Shared chrome for centered modal dialogs |
| [ConfirmDialog](docs/dialogs/ConfirmDialog.md) | Generic yes/no question |
| [AboutDialog](docs/dialogs/AboutDialog.md) | About box read from a text file, with `AboutMenuItem` |
| [SettingsDialog](docs/dialogs/SettingsDialog.md) | Editor for every declared setting, with `SettingsMenuItem` |

## Modules

| Module | Description |
| --- | --- |
| [tcw.chords](docs/chords.md) | VSCode-style multi-key bindings (`ctrl+k ctrl+s`) via an App mixin |
| [tcw.settings](docs/settings.md) | Self-registering typed settings, persisted only when overridden |
| [tcw.log_sink](docs/widgets/LogViewer.md#the-sink-tcwlog_sink) | In-memory `logging` handler behind `LogViewer` |
| [tcw.demo](docs/demo.md) | The demo app behind `python -m tcw` |

The conventions every component follows, and why, are in
[docs/DESIGN.md](docs/DESIGN.md).
