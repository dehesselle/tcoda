# Log viewer

A panel that slides down from the top over existing content, showing the
last 30,000 lines a program has written through the stdlib `logging` module
— no logfile, no tailing. A level dropdown (default: info and above) and a
tree of sources with checkboxes (default: all visible) narrow what's shown.

```python
from tcoda.widgets import LogViewer


class MainScreen(Screen):
    def compose(self) -> ComposeResult:
        yield LogViewer()
        ...
```

- **Zero-config by default.** `LogViewer()` creates its own in-memory sink
  (`tcoda.log_sink.InMemoryLogHandler`) and attaches it to the root logger.
  Pass `logger=` (a `logging.Logger` or a name) to attach somewhere else
  instead. Pass an existing `handler=` — typically one attached at process
  startup, before any UI existed — to skip all of that: the viewer then
  only replays and subscribes, on the assumption the caller manages
  attachment themselves. `handler=` and `logger=` together raise
  `ValueError`.
- **The level is the `min_level` reactive**, which the dropdown and the
  code share: `LogViewer(min_level=logging.DEBUG)` starts lower, and setting
  it later moves the dropdown. It must be one of the dropdown's levels.
- **The owned logger's level tracks the level dropdown**, not a fixed
  `DEBUG` — a logger left at `DEBUG` costs measurably more than one at its
  default (every `debug`/`info` call across the whole logger hierarchy
  actually builds a `LogRecord` instead of short-circuiting), so the cost is
  paid only for whatever's currently selected, not unconditionally because a
  `LogViewer` exists. This only applies when `LogViewer` owns the logger —
  an explicitly-passed `handler=` means levels are the caller's business.
- **`LogViewer` installs its own key binding** (`F1` by default) the same
  way [`MenuBar`](MenuBar.md) does — see
  [DESIGN.md](../DESIGN.md#widgets-that-own-a-key-bind-it-on-their-screen).
  Pass `key=` to change it, or `key=None` to bind it yourself (see
  `TOGGLE_ACTION`). A second `LogViewer` on the same screen needs `key=None`
  and is toggled through its own `toggle()`; asking for a key raises at
  mount.
- **Sources are logger names (`record.name`), discovered live** — the tree
  grows as new ones appear, defaulting to visible. Hiding a source stops new
  lines from it reaching the panel, but they stay in the sink's buffer —
  showing it again picks up everything that arrived while it was hidden.
  Lowering the level dropdown has no equivalent: a level suppressed upstream
  before you asked for it is gone for good.
- **The tree follows the dots in the names, as `logging`'s own hierarchy
  does**, so a library's many loggers sit under one row, collapsed at first,
  with the rows of each level sorted by name.
  `space`, `enter` or a click toggles a row and everything beneath it; `right`,
  `left` or a click on the arrow expands and collapses. The trigger's count
  covers sources only, not rows that merely group them. A row whose sources
  disagree shows `-`, and toggling it shows them all.
- **A new source takes the state of its parent row**, so a hidden `urllib3`
  keeps hiding a `urllib3.connectionpool` that first logs later. Unchecking
  every child one by one doesn't count: only a decision about the row itself
  covers what comes later.
- **`set_source_hidden(name, hidden)` does what toggling a row does**, from
  code, and takes any prefix, whether or not anything has logged under it yet.
  A prefix nothing has logged under gets a row of its own, which stays.
  `is_source_hidden(name)` answers the same way for a source yet to appear.
  Both work once the panel is mounted, so a host's `on_mount` is the place to
  hide something from the start.
- **While concealed, it takes no focus**, whether by `Tab`, from code or as the
  screen's first focusable widget, so it can be composed anywhere on a screen.
  Concealing it while one of its controls has the focus leaves nothing focused,
  as Textual does when a focused widget goes out of reach; `Tab` carries on
  from the rest of the screen. Its controls are disabled for as long as it is
  concealed, and keep up with the log all the same. The panel's own `disabled`
  stays yours, and a panel disabled that way stays out of reach once revealed
  too.

## The sink: `tcoda.log_sink`

`InMemoryLogHandler` is a plain `logging.Handler` with no Textual import, so it
can be attached to a logger before any UI exists and tested with nothing but
the stdlib.

```python
import logging

from tcoda.log_sink import InMemoryLogHandler

sink = InMemoryLogHandler()  # capacity=30_000
logging.getLogger().addHandler(sink)
...
yield LogViewer(handler=sink)
```

- **Unfiltered by default (`level=NOTSET`).** Filtering by level or source is a
  subscriber's concern, not the sink's, so one buffer can serve several
  differently-filtered views.
- **Each buffered `LogEntry` keeps `levelno`, `levelname`, `source` and
  `created` as fields** alongside the formatted `line`, so a subscriber can
  filter — or build its own display line — without re-parsing text.
- **`entries()` snapshots the buffer; `subscribe()` / `unsubscribe()` manage
  live fan-out.** Subscribers are called outside the handler's lock, so one may
  subscribe or unsubscribe from inside its own callback without deadlocking.
