"""A log panel that slides down from the top over existing content, showing
whatever the host app writes through the stdlib `logging` module -- no
logfile, no tailing.

`InMemoryLogHandler` (see `tcw.log_sink`) owns the rolling buffer and is
independent of any widget being mounted, so nothing emitted before a
`LogViewer` exists is lost -- it is replayed on mount. Filtering by level and
source happens here, at render time, against that buffer -- the sink itself
stays unfiltered.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import RichLog, Select
from textual.widgets.selection_list import Selection

from tcw.log_sink import InMemoryLogHandler, LogEntry
from tcw.widgets._multi_select import MultiSelect

#: The action `LogViewer` installs on its screen -- see `MenuBar.OPEN_ACTION`
#: for the identical pattern this mirrors.
TOGGLE_ACTION = "toggle_log_viewer"

#: Reserved layer name this widget self-registers onto its host screen so it
#: reliably paints above ordinary ("default"-layer) content -- mirrors how
#: Textual's own LoadingIndicator/Toast/Tooltip use `_loading`/`_toastrack`/
#: `_tooltips`, except those are hardcoded into Screen.layers and this one
#: can't be, so it installs itself the same way MenuBar installs a binding.
_LAYER = "_tcw_log_viewer"

_LEVELS: list[tuple[str, int]] = [
    ("Debug", logging.DEBUG),
    ("Info", logging.INFO),
    ("Warning", logging.WARNING),
    ("Error", logging.ERROR),
    ("Critical", logging.CRITICAL),
]


class LogViewer(Widget, can_focus=False):
    """A rolling, filterable view of the app's own log output, docked to the
    top."""

    DEFAULT_CSS = """
    LogViewer {
        dock: top;
        height: 33%;
        layer: _tcw_log_viewer;
        background: $surface;
        offset: 0 -100%;
        transition: offset 400ms in_out_cubic;
    }
    LogViewer.-revealed {
        offset: 0 0;
    }
    LogViewer > #log-viewer-toolbar {
        height: 1;
        layout: horizontal;
        background: $panel;
    }
    LogViewer > #log-viewer-toolbar > #log-viewer-level {
        width: 20;
    }
    LogViewer > #log-viewer-toolbar > #log-viewer-sources {
        width: 24;
        margin: 0 0 0 1;
    }
    LogViewer > #log-viewer-log {
        height: 1fr;
    }
    """

    revealed: reactive[bool] = reactive(False)

    class _NewEntry(Message):
        """Internal: an entry reached the buffer, possibly from another
        thread. Not for host apps to handle -- it never leaves this widget."""

        bubble = False

        def __init__(self, entry: LogEntry) -> None:
            self.entry = entry
            super().__init__()

    def __init__(
        self,
        *,
        handler: InMemoryLogHandler | None = None,
        logger: str | logging.Logger | None = None,
        key: str | None = "f1",
        key_description: str = "Log",
        show_key: bool = True,
        id: str | None = None,
    ) -> None:
        """
        Args:
            handler: Reuse an existing sink instead of creating one --
                typically one attached at process startup, before any UI
                existed. When given, LogViewer never touches any logger's
                handlers or level: attachment is assumed to be the caller's
                responsibility.
            logger: Which logger an owned handler attaches to (a
                `logging.Logger` or a name). Only consulted when `handler`
                is None; defaults to the root logger. Mutually exclusive
                with `handler`.
            key: The key that toggles the panel, or None to bind it
                yourself (see `TOGGLE_ACTION`).
            key_description: How that key is described in the footer.
            show_key: Whether that key appears in the footer at all.
            id: DOM id.
        """
        if handler is not None and logger is not None:
            raise ValueError("pass either handler= or logger=, not both")
        super().__init__(id=id)
        self._explicit_handler = handler
        self._logger_arg = logger
        self._key = key
        self._key_description = key_description
        self._show_key = show_key

        self._handler: InMemoryLogHandler  # set in _attach_handler, at mount
        self._owns_handler = False
        self._min_level: int = logging.INFO
        self._hidden_sources: set[str] = set()
        self._known_sources: dict[str, None] = {}  # insertion-ordered set

    def compose(self) -> ComposeResult:
        with Horizontal(id="log-viewer-toolbar"):
            yield Select[int](
                _LEVELS,
                id="log-viewer-level",
                value=self._min_level,
                allow_blank=False,
                compact=True,
            )
            yield MultiSelect[str](
                label=self._sources_label(),
                compact=True,
                id="log-viewer-sources",
            )
        # `wrap=True`: a `Log` widget only ever crops a long line to the
        # viewport width, requiring horizontal scrolling to read the rest --
        # painful for the very thing this exists to show in full, a long SQL
        # statement. `RichLog` reflows onto further screen lines instead.
        yield RichLog(id="log-viewer-log", wrap=True, highlight=False, markup=False)

    # ------------------------------------------------------------- mounting

    def on_mount(self) -> None:
        self._install_layer()
        if self._key is not None:
            self._install_binding()
        self._attach_handler()
        sources = self.query_one("#log-viewer-sources", MultiSelect)
        for entry in self._handler.entries():
            if entry.source not in self._known_sources:
                self._known_sources[entry.source] = None
                sources.add_option(
                    Selection(
                        entry.source,
                        entry.source,
                        not self.is_source_hidden(entry.source),
                    )
                )
        self._sync_sources_label()
        self._render_log()
        self._handler.subscribe(self._on_sink_entry)

    def on_unmount(self) -> None:
        self._handler.unsubscribe(self._on_sink_entry)
        if self._owns_handler:
            self._logger.removeHandler(self._handler)

    def _install_layer(self) -> None:
        # `screen.styles.layers` (the raw CSS rule) is empty until something
        # sets it -- it does not include "default", the name ordinary
        # content resolves to. Omitting that would put both this panel and
        # ordinary content at the same paint-order index, defeating the
        # overlay -- so an unset rule is treated as `("default",)`, not `()`.
        existing = self.screen.styles.layers
        if _LAYER in existing:
            return
        base = existing if existing else ("default",)
        self.screen.styles.layers = (*base, _LAYER)

    def _install_binding(self) -> None:
        # A key binding cannot live on this widget: Textual only consults
        # the focus chain plus the screen and the app. So it installs
        # itself onto whichever screen it was mounted on, mirroring
        # MenuBar.on_mount (src/tcw/widgets/_menubar.py).
        screen = self.screen
        if not hasattr(screen, f"action_{TOGGLE_ACTION}"):
            setattr(screen, f"action_{TOGGLE_ACTION}", self.toggle)
        bindings = screen._bindings
        if any(
            binding.action == TOGGLE_ACTION
            for binding in bindings.key_to_bindings.get(self._key, ())
        ):
            # Already installed: on_mount runs again if the panel is
            # remounted, and a second binding would put a duplicate in the
            # footer.
            return
        bindings.bind(
            self._key,
            TOGGLE_ACTION,
            self._key_description,
            show=self._show_key,
        )
        # Ordering is the app's call, via `Footer(pinned=(TOGGLE_ACTION,))` --
        # see MenuBar.on_mount.
        screen.refresh_bindings()

    def _attach_handler(self) -> None:
        if self._explicit_handler is not None:
            self._handler = self._explicit_handler
            self._owns_handler = False
            return
        self._handler = InMemoryLogHandler()
        self._owns_handler = True
        logger = (
            logging.getLogger(self._logger_arg)
            if isinstance(self._logger_arg, str) or self._logger_arg is None
            else self._logger_arg
        )
        self._logger = logger
        logger.addHandler(self._handler)
        self._sync_logger_level()

    def _sync_logger_level(self) -> None:
        # Only when this LogViewer owns the logger: a level below the
        # logger's own is dropped before any handler -- including this
        # one -- ever sees it (`logging.Logger.isEnabledFor`), so without
        # this the dropdown's lower options would silently show nothing.
        # Kept in sync with the *current* selection rather than forced to
        # DEBUG unconditionally: a logger left at DEBUG costs measurably
        # more than one at its default (every debug/info call across the
        # whole logger hierarchy actually builds a LogRecord instead of
        # short-circuiting), and that cost would be paid regardless of
        # whether the panel is even revealed. Lowering the threshold later
        # cannot recover entries already suppressed before that point.
        if self._owns_handler:
            self._logger.setLevel(self._min_level)

    # ------------------------------------------------------------------ filter

    def _passes(self, entry: LogEntry) -> bool:
        return (
            entry.levelno >= self._min_level
            and entry.source not in self._hidden_sources
        )

    @staticmethod
    def _display_line(entry: LogEntry) -> str:
        """Timestamp, level and source in front of the message -- `line`
        itself deliberately carries none of them (see `tcw.log_sink`), so
        composing the full display text is this widget's job, not the
        sink's."""
        # entry.created is a naive Unix timestamp (record.created); routing
        # it through an explicit UTC-aware instant before converting to the
        # local zone is what satisfies ruff's DTZ006 without changing the
        # displayed wall-clock time at all.
        local_time = datetime.fromtimestamp(entry.created, tz=UTC).astimezone()
        timestamp = local_time.strftime("%H:%M:%S.%f")[:-3]
        return f"{timestamp} {entry.levelname:<8} {entry.source}: {entry.line}"

    def _render_log(self) -> None:
        log = self.query_one("#log-viewer-log", RichLog)
        log.clear()
        for entry in self._handler.entries():
            if self._passes(entry):
                log.write(self._display_line(entry))

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id != "log-viewer-level":
            return
        event.stop()
        assert isinstance(event.value, int)
        self._min_level = event.value
        self._sync_logger_level()
        self._render_log()

    # ------------------------------------------------------------------- live

    def _on_sink_entry(self, entry: LogEntry) -> None:
        # May run on any thread -- this is InMemoryLogHandler.subscribe's
        # callback. post_message is thread-safe from any thread including
        # the app's own, unlike RichLog.write() directly and unlike
        # app.call_from_thread (which raises if called from the app's own
        # thread).
        self.post_message(self._NewEntry(entry))

    def on_log_viewer__new_entry(self, message: _NewEntry) -> None:
        entry = message.entry
        self._note_source(entry.source)
        if self._passes(entry):
            self.query_one("#log-viewer-log", RichLog).write(self._display_line(entry))

    def _note_source(self, source: str) -> None:
        if source in self._known_sources:
            return
        self._known_sources[source] = None
        self._sync_sources_label()
        self.query_one("#log-viewer-sources", MultiSelect).add_option(
            Selection(source, source, True)
        )

    # --------------------------------------------------------------- sources UI

    def _sources_label(self) -> str:
        total = len(self._known_sources)
        hidden = len(self._hidden_sources & self._known_sources.keys())
        return f"Sources ({total - hidden}/{total})"

    def _sync_sources_label(self) -> None:
        self.query_one("#log-viewer-sources", MultiSelect).set_label(
            self._sources_label()
        )

    def is_source_hidden(self, source: str) -> bool:
        return source in self._hidden_sources

    def on_multi_select_option_toggled(self, event: MultiSelect.OptionToggled) -> None:
        if event.multi_select.id != "log-viewer-sources":
            return
        event.stop()
        source = event.value
        self.set_source_hidden(source, not event.multi_select.is_selected(source))

    def set_source_hidden(self, source: str, hidden: bool) -> None:
        if hidden:
            self._hidden_sources.add(source)
        else:
            self._hidden_sources.discard(source)
        self._sync_sources_label()
        self._render_log()
        # Keeps the checkbox in sync with a *programmatic* call too (as used
        # by several tests, and available to host apps) -- safe against
        # feedback loops because `select`/`deselect` never re-fire
        # `SelectionToggled`, only explicit user toggles do.
        sources = self.query_one("#log-viewer-sources", MultiSelect)
        if hidden:
            sources.deselect(source)
        else:
            sources.select(source)

    # ---------------------------------------------------------------- drive

    def allow_focus_children(self) -> bool:
        # Concealed means off-canvas (see the `offset` transition in
        # DEFAULT_CSS, not `display`, so the slide animation still plays) --
        # without this override Textual's focus chain doesn't know that and
        # happily Tabs through the toolbar/log with nothing visible to show
        # for it.
        return self.revealed

    def watch_revealed(self) -> None:
        self.set_class(self.revealed, "-revealed")
        if not self.revealed and self.screen.focused in self.query("*"):
            # Concealing just made the focused widget unreachable by Tab and
            # invisible -- leaving it focused would strand arrow/type keys on
            # a widget the user can no longer see.
            self.screen.set_focus(None)

    def reveal(self) -> None:
        self.revealed = True

    def conceal(self) -> None:
        self.revealed = False

    def toggle(self) -> None:
        self.revealed = not self.revealed
