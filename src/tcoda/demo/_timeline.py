# SPDX-FileCopyrightText: 2026 René de Hesselle <dehesselle@web.de>
#
# SPDX-License-Identifier: 0BSD

"""When the browsed directory's files last changed, and how big they are, on
a `tcoda.plot.Plot` with a time axis that zooms and pans on its own."""

from __future__ import annotations

import time
from collections.abc import Iterable

from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Label

from tcoda.demo._browser import FileInfo
from tcoda.dialogs import Dialog
from tcoda.plot import DateTimeFormatter, Plot

#: The narrowest stretch of time zooming in goes to, in seconds.
SHORTEST_SPAN = 60


class TimelineDialog(Dialog[None]):
    """A dot per file: when it last changed, against its size.

    Only the time axis zooms and pans, never back before 1970 nor on into
    the future, and the sizes fit whatever stretch of time is shown.
    """

    DEFAULT_CSS = """
    TimelineDialog > #dialog {
        width: 80;
        max-width: 100%;
    }
    TimelineDialog Plot {
        height: 18;
        margin: 1 0 0 0;
    }
    TimelineDialog #timeline-status {
        width: 1fr;
        color: $text-muted;
    }
    """

    def __init__(self, title: str, files: Iterable[FileInfo]) -> None:
        """
        Args:
            title: What the files are, for the dialog's title.
            files: The files to show.
        """
        super().__init__()
        self._title = title
        self._files = list(files)

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label(f"Timeline of {self._title}", id="title")
            plot = Plot(y_label="KiB", pan_and_zoom="x")
            plot.x_formatter = DateTimeFormatter()
            plot.x_bounds = (0, time.time())
            plot.x_span = (SHORTEST_SPAN, None)
            plot.y_limits = (0, None)
            plot.scatter(
                [info.modified for info in self._files],
                [info.size / 1024 for info in self._files],
                hires_mode="braille",
                label="file",
            )
            yield plot
            yield Label(self._in_view(plot), id="timeline-status")
            with Horizontal(id="buttons"):
                yield Button("Close", variant="primary", id="timeline-close")

    def _in_view(self, plot: Plot) -> str:
        low, high = plot.x_range
        count = sum(low <= info.modified <= high for info in self._files)
        return f"{count} of {len(self._files)} files in view"

    def _show_status(self, pointer: str = "") -> None:
        status = self._in_view(self.query_one(Plot))
        self.query_one("#timeline-status", Label).update(
            f"{status} · {pointer}" if pointer else status
        )

    def on_plot_range_settled(self) -> None:
        # Counted once zooming stops, as an app would fetch data for the
        # range it came to.
        self._show_status()

    def on_mouse_move(self, event: events.MouseMove) -> None:
        plot = self.query_one(Plot)
        if (point := plot.data_at(event.screen_offset)) is None:
            self._show_status()
            return
        moment, kib = point
        # The axis's own formatter, which takes any time without raising.
        (stamp,) = plot.x_formatter.get_labels([moment])
        self._show_status(f"{stamp}, {kib:.1f} KiB")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        self.dismiss(None)
