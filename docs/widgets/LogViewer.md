# Log viewer

A panel that slides down from the top over existing content, showing the
last 30,000 lines a program has written through the stdlib `logging` module
-- no logfile, no tailing. A level dropdown (default: info and above) and a
per-source checklist (default: all sources visible) narrow what's shown.

```python
from tcw.widgets import LogViewer


class MainScreen(Screen):
    def compose(self) -> ComposeResult:
        yield LogViewer()
        ...
```

- **Zero-config by default.** `LogViewer()` creates its own in-memory sink
  (`tcw.log_sink.InMemoryLogHandler`) and attaches it to the root logger.
  Pass `logger=` (a `logging.Logger` or a name) to attach somewhere else
  instead. Pass an existing `handler=` -- typically one attached at process
  startup, before any UI existed -- to skip all of that: the viewer then
  only replays and subscribes, on the assumption the caller manages
  attachment themselves. `handler=` and `logger=` together raise
  `ValueError`.
- **The owned logger's level tracks the level dropdown**, not a fixed
  `DEBUG` -- a logger left at `DEBUG` costs measurably more than one at its
  default (every `debug`/`info` call across the whole logger hierarchy
  actually builds a `LogRecord` instead of short-circuiting), so the cost is
  paid only for whatever's currently selected, not unconditionally because a
  `LogViewer` exists. This only applies when `LogViewer` owns the logger --
  an explicitly-passed `handler=` means levels are the caller's business.
- **`LogViewer` installs its own key binding** (`F1` by default) the same
  way [`MenuBar`](MenuBar.md) does — see
  [DESIGN.md](../DESIGN.md#widgets-that-own-a-key-bind-it-on-their-screen).
  Pass `key=` to change it, or `key=None` to bind it yourself (see
  `TOGGLE_ACTION`).
- **Sources are logger names (`record.name`), discovered live** -- the
  checklist grows as new ones appear, defaulting to visible. Hiding a
  source stops new lines from it reaching the panel, but they stay in the
  sink's buffer -- showing it again picks up everything that arrived while
  it was hidden. Lowering the level dropdown has no equivalent: a level
  suppressed upstream before you asked for it is gone for good.

## The sink: `tcw.log_sink`

`InMemoryLogHandler` is a plain `logging.Handler` with no Textual import, so it
can be attached to a logger before any UI exists and tested with nothing but
the stdlib.

```python
import logging

from tcw.log_sink import InMemoryLogHandler

sink = InMemoryLogHandler()          # capacity=30_000
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
