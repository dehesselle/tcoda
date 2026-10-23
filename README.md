# tcoda — Textual coda

> _A coda is a final part that brings something to a close, completing what came before it._

tcoda is a widget library to extend Textual with things I regularly use in my projects.

Consumed as an editable path dependency while it is still being tracked from
source:

```toml
dependencies = ["tcoda>=0.1"]

[tool.uv.sources]
tcoda = { path = "../tcoda", editable = true }
```

## Demo

`python -m tcoda` runs a demo app that uses every widget and dialog, the way
`python -m textual` runs Textual's own. See [docs/demo.md](docs/demo.md) for
where each component appears in it.

## Widgets — `tcoda.widgets`

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

## Dialogs — `tcoda.dialogs`

| Dialog | Description |
| --- | --- |
| [Dialog](docs/dialogs/Dialog.md) | Shared chrome for centered modal dialogs |
| [ConfirmDialog](docs/dialogs/ConfirmDialog.md) | Generic yes/no question |
| [AboutDialog](docs/dialogs/AboutDialog.md) | About box read from a text file, with `AboutMenuItem` |
| [SettingsDialog](docs/dialogs/SettingsDialog.md) | Editor for every declared setting, with `SettingsMenuItem` |

## Modules

| Module | Description |
| --- | --- |
| [tcoda.chords](docs/chords.md) | VSCode-style multi-key bindings (`ctrl+k ctrl+s`) via an App mixin |
| [tcoda.terminal_title](docs/terminal_title.md) | Sets the terminal's window title and restores it on exit, via an App mixin |
| [tcoda.settings](docs/settings.md) | Self-registering typed settings, persisted only when overridden |
| [tcoda.log_sink](docs/widgets/LogViewer.md#the-sink-tcodalog_sink) | In-memory `logging` handler behind `LogViewer` |
| [tcoda.demo](docs/demo.md) | The demo app behind `python -m tcoda` |

The conventions every component follows, and why, are in
[docs/DESIGN.md](docs/DESIGN.md).

## AI disclosure

Substantial parts of this code were generated with Sonnet 5.x/Opus 5.x. Generated code was tested, but not every line was reviewed in detail.

## License

[0BSD](LICENSES/0BSD.txt)
