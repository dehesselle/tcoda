# SPDX-FileCopyrightText: 2026 René de Hesselle <dehesselle@web.de>
#
# SPDX-License-Identifier: 0BSD

"""A log panel that slides down from the top over existing content, showing
whatever the host app writes through the stdlib `logging` module -- no
logfile, no tailing.

`InMemoryLogHandler` (see `tcoda.log_sink`) owns the rolling buffer and is
independent of any widget being mounted, so nothing emitted before a
`LogViewer` exists is lost -- it is replayed on mount. Filtering by level and
source happens here, at render time, against that buffer -- the sink itself
stays unfiltered. Export writes that whole buffer to a file, filters or not:
for an app without a logfile, the panel may be the only record there is.
"""

from __future__ import annotations

import io
import logging
import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Button, RichLog, Select

from tcoda.log_sink import InMemoryLogHandler, LogEntry
from tcoda.widgets._layers import install_layer
from tcoda.widgets._screen_keys import install_screen_key, uninstall_screen_key
from tcoda.widgets._tree_select import TreeSelect

if TYPE_CHECKING:
    from pathlib import Path

    from textual.screen import Screen

#: The action `LogViewer` installs on its screen -- see `OPEN_ACTION` in
#: `tcoda.widgets._menubar` for the identical pattern this mirrors.
TOGGLE_ACTION = "toggle_log_viewer"

#: Reserved layer name this widget self-registers onto its host screen so it
#: reliably paints above ordinary ("default"-layer) content -- see
#: `tcoda.widgets._layers`.
_LAYER = "_tcoda_log_viewer"

_LEVELS: list[tuple[str, int]] = [
    ("Debug", logging.DEBUG),
    ("Info", logging.INFO),
    ("Warning", logging.WARNING),
    ("Error", logging.ERROR),
    ("Critical", logging.CRITICAL),
]

#: Anything outside this set is replaced in the app's name before it becomes
#: part of a filename.
_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._-]")


class LogViewer(Widget, can_focus=False):
    """A rolling, filterable view of the app's own log output, docked to the
    top."""

    DEFAULT_CSS = """
    LogViewer {
        dock: top;
        height: 33%;
        layer: _tcoda_log_viewer;
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
    /* Dressed as the dropdowns' triggers rather than as a button, so the
       toolbar reads as one row of like controls. */
    LogViewer > #log-viewer-toolbar > #log-viewer-export {
        width: auto;
        min-width: 0;
        height: 1;
        margin: 0 0 0 1;
        padding: 0;
        border: none;
        color: $foreground;
        background: $surface;
        text-style: none;
        pointer: pointer;
        &:focus {
            text-style: none;
            background-tint: $foreground 5%;
        }
        &:hover {
            border: none;
            background: $surface;
        }
        &.-active {
            border: none;
            background: $surface;
            tint: transparent;
        }
    }
    LogViewer > #log-viewer-log {
        height: 1fr;
    }
    """

    revealed: reactive[bool] = reactive(False)
    #: Entries below this `logging` level are left out of the panel. One of
    #: the levels the dropdown offers; the dropdown follows it, and it
    #: follows the dropdown.
    min_level: reactive[int] = reactive(logging.INFO, init=False)

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
        min_level: int = logging.INFO,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
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
            min_level: See the `min_level` reactive.
            name: The widget's name.
            id: DOM id.
            classes: CSS classes.
            disabled: Whether the widget starts out disabled.
        """
        if handler is not None and logger is not None:
            raise ValueError("pass either handler= or logger=, not both")
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self._explicit_handler = handler
        self._logger_arg = logger
        self._key = key
        self._key_description = key_description
        self._show_key = show_key
        # set_reactive deliberately bypasses validators, so validate here too.
        self.set_reactive(LogViewer.min_level, self.validate_min_level(min_level))

        self._key_screen: Screen[Any]  # set at mount
        self._handler: InMemoryLogHandler  # set in _attach_handler, at mount
        self._owns_handler = False
        # Derived from the checkboxes, which own the state, because every entry
        # of a re-render asks and walking the tree each time would add up.
        self._hidden_sources: set[str] = set()
        self._known_sources: set[str] = set()
        # Delivery keys of exports still being written, see `_on_app_message`.
        self._pending_exports: set[str] = set()

    def compose(self) -> ComposeResult:
        with Horizontal(id="log-viewer-toolbar", disabled=not self.revealed):
            yield Select[int](
                _LEVELS,
                id="log-viewer-level",
                value=self.min_level,
                allow_blank=False,
                compact=True,
            )
            yield TreeSelect(
                label=self._sources_label(),
                compact=True,
                id="log-viewer-sources",
            )
            yield Button("Export", id="log-viewer-export", compact=True)
        # `wrap=True`: a `Log` widget only ever crops a long line to the
        # viewport width, requiring horizontal scrolling to read the rest --
        # painful for the very thing this exists to show in full, a long log
        # message. `RichLog` reflows onto further screen lines instead.
        yield RichLog(
            id="log-viewer-log",
            wrap=True,
            highlight=False,
            markup=False,
            disabled=not self.revealed,
        )

    # ------------------------------------------------------------- mounting

    def on_mount(self) -> None:
        install_layer(self.screen, _LAYER)
        # On the screen rather than on the panel, which is never focused --
        # see `tcoda.widgets._screen_keys`.
        self._key_screen = install_screen_key(
            self,
            TOGGLE_ACTION,
            self.toggle,
            self._key,
            self._key_description,
            show=self._show_key,
        )
        self._attach_handler()
        self._render_log()
        self._handler.subscribe(self._on_sink_entry)
        # How an export went is only ever told to the app: `DeliveryComplete`
        # and `DeliveryFailed` are sent to it directly and do not bubble.
        # Every message the app processes is published here, though.
        self.app.message_signal.subscribe(self, self._on_app_message)

    def on_unmount(self) -> None:
        self.app.message_signal.unsubscribe(self)
        uninstall_screen_key(self._key_screen, self, TOGGLE_ACTION)
        self._handler.unsubscribe(self._on_sink_entry)
        if self._owns_handler:
            self._logger.removeHandler(self._handler)

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
            self._logger.setLevel(self.min_level)

    # ------------------------------------------------------------------ filter

    def _passes(self, entry: LogEntry) -> bool:
        return (
            entry.levelno >= self.min_level and entry.source not in self._hidden_sources
        )

    @staticmethod
    def _format_line(entry: LogEntry, time_format: str) -> str:
        """Timestamp, level and source in front of the message -- `line`
        itself deliberately carries none of them (see `tcoda.log_sink`), so
        composing the full text is this widget's job, not the sink's.
        `time_format` is a strftime pattern ending in `%f`, which is cut to
        milliseconds."""
        # entry.created is a naive Unix timestamp (record.created); routing
        # it through an explicit UTC-aware instant before converting to the
        # local zone is what satisfies ruff's DTZ006 without changing the
        # displayed wall-clock time at all.
        local_time = datetime.fromtimestamp(entry.created, tz=UTC).astimezone()
        timestamp = local_time.strftime(time_format)[:-3]
        return f"{timestamp} {entry.levelname:<8} {entry.source}: {entry.line}"

    @classmethod
    def _display_line(cls, entry: LogEntry) -> str:
        return cls._format_line(entry, "%H:%M:%S.%f")

    def _render_log(self) -> None:
        log = self.query_one("#log-viewer-log", RichLog)
        log.clear()
        for entry in self._handler.entries():
            # Replayed at mount, or here ahead of its own `_NewEntry`: a source
            # not noted yet would pass, even beneath a hidden row.
            self._note_source(entry.source)
            if self._passes(entry):
                log.write(self._display_line(entry))

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id != "log-viewer-level":
            return
        event.stop()
        assert isinstance(event.value, int)
        self.min_level = event.value

    def validate_min_level(self, level: int) -> int:
        # The dropdown can only show a level it offers, and a `Select` given
        # any other value raises -- better here, where the caller is.
        if level not in dict(_LEVELS).values():
            raise ValueError(
                f"min_level must be one of the dropdown's levels, not {level!r}"
            )
        return level

    def watch_min_level(self, level: int) -> None:
        if not self.is_mounted:
            # Before mount, compose and on_mount pick the level up anyway.
            return
        self.query_one("#log-viewer-level", Select).value = level
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
        self._known_sources.add(source)
        self.query_one("#log-viewer-sources", TreeSelect).add_option(source.split("."))
        self._sync_hidden_sources()

    # --------------------------------------------------------------- sources UI

    def _sources_label(self) -> str:
        total = len(self._known_sources)
        return f"Sources ({total - len(self._hidden_sources)}/{total})"

    def _sync_hidden_sources(self) -> None:
        sources = self.query_one("#log-viewer-sources", TreeSelect)
        self._hidden_sources = {
            source
            for source in self._known_sources
            if not sources.is_checked(source.split("."))
        }
        sources.set_label(self._sources_label())

    def is_source_hidden(self, source: str) -> bool:
        """Whether `source` is hidden, or would be if it appeared now."""
        sources = self.query_one("#log-viewer-sources", TreeSelect)
        return not sources.is_checked(source.split("."))

    def on_tree_select_toggled(self, event: TreeSelect.Toggled) -> None:
        if event.tree_select.id != "log-viewer-sources":
            return
        event.stop()
        self._sync_hidden_sources()
        self._render_log()

    def set_source_hidden(self, source: str, hidden: bool) -> None:
        """Hide or show `source` and everything beneath it in the dotted
        hierarchy, including what appears there later. Takes any prefix, known
        yet or not: `set_source_hidden("urllib3", True)`."""
        self.query_one("#log-viewer-sources", TreeSelect).set_checked(
            source.split("."), not hidden
        )
        self._sync_hidden_sources()
        self._render_log()

    # ----------------------------------------------------------------- export

    def to_text(self) -> str:
        """Everything the buffer holds, one entry per line, whatever the level
        and source filters show. Each line carries the date too, as a file
        outlives the day it was written."""
        return "".join(
            self._format_line(entry, "%Y-%m-%d %H:%M:%S.%f") + "\n"
            for entry in self._handler.entries()
        )

    def export_filename(self) -> str:
        """The name `export` saves under: the app's `TITLE` (or its class name)
        and the local time, as in `my_app_20261113-213045.log`. Override to
        name the file differently."""
        # `TITLE` rather than `title`, which apps reuse for whatever they
        # show at the moment.
        name = self.app.TITLE or type(self.app).__name__
        stem = _UNSAFE_FILENAME_CHARS.sub("_", name)
        # No colons, which Windows does not allow in a filename.
        return f"{stem}_{datetime.now().astimezone():%Y%m%d-%H%M%S}.log"

    def export(self, *, save_directory: str | Path | None = None) -> str:
        """Save `to_text()` through `App.deliver_text`: to `save_directory`,
        by default the user's downloads directory, or as a download in the
        browser when served on the web. A notification tells how it went.
        Returns the delivery key."""
        key = self.app.deliver_text(
            io.StringIO(self.to_text()),
            save_directory=save_directory,
            save_filename=self.export_filename(),
            encoding="utf-8",
            mime_type="text/plain",
        )
        self._pending_exports.add(key)
        return key

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "log-viewer-export":
            return
        event.stop()
        self.export()

    def _on_app_message(self, message: Message) -> None:
        if isinstance(message, events.DeliveryComplete):
            if message.key not in self._pending_exports:
                return
            self._pending_exports.discard(message.key)
            saved = (
                "Saved log" if message.path is None else f"Saved log to {message.path}"
            )
            self.notify(saved, title="Log", markup=False)
        elif isinstance(message, events.DeliveryFailed):
            if message.key not in self._pending_exports:
                return
            self._pending_exports.discard(message.key)
            self.notify(
                f"Failed to save log: {message.exception}",
                title="Log",
                severity="error",
                markup=False,
            )

    # ---------------------------------------------------------------- drive

    def watch_revealed(self) -> None:
        self.set_class(self.revealed, "-revealed")
        # Concealed means off-canvas (see the `offset` transition in
        # DEFAULT_CSS, not `display`, so the slide animation still plays), which
        # Textual cannot tell from on-screen: the controls would still take the
        # focus, by Tab, from code and as a screen's first focusable widget.
        # Disabled, they cannot, and any that has it loses it.
        # The children rather than `self`, whose `disabled` is the host's.
        for child in self.children:
            child.disabled = not self.revealed

    def reveal(self) -> None:
        self.revealed = True

    def conceal(self) -> None:
        self.revealed = False

    def toggle(self) -> None:
        self.revealed = not self.revealed
