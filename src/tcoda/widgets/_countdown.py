# SPDX-FileCopyrightText: 2026 René de Hesselle <dehesselle@web.de>
#
# SPDX-License-Identifier: 0BSD

"""A seconds counter, with a spinner for while something is actually in flight.

Two apps grew their own copy of this before it landed here. Neither the
counter nor the spinner is tied to a footer -- put one wherever a wait needs a
number::

    yield Countdown(id="footer-countdown")

    ...
    countdown.remaining = 30      # counts down
    countdown.refreshing = True   # spins until cleared
    countdown.display = False     # gone entirely

`display` is deliberately the only way to hide it: an empty render would mean
"nothing to say", which is not the same thing as a genuine zero, and a widget
that conflates the two cannot express either.
"""

from __future__ import annotations

from typing import ClassVar

from textual.reactive import reactive
from textual.timer import Timer
from textual.widgets import Static


class Countdown(Static):
    """Seconds remaining, with a braille spinner while `refreshing`."""

    DEFAULT_CSS = """
    Countdown {
        width: auto;
        height: 1;
    }
    """

    #: The counter is three digits wide; a wait longer than this is not being
    #: read precisely anyway, so anything above it shows as the cap.
    MAX_SECONDS: ClassVar[int] = 999
    #: Frames cycled through while `refreshing`.
    SPINNER: ClassVar[str] = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    #: Seconds between spinner frames.
    SPINNER_INTERVAL: ClassVar[float] = 0.1

    # layout=True on both: the widget is `width: auto`, and a plain reactive
    # only repaints in place -- "100" going to "99", or a number giving way to
    # a one-cell spinner, would render clipped or leave a stale trailing
    # column until something else (a terminal resize, say) forced a relayout.
    remaining: reactive[int] = reactive(0, layout=True)
    refreshing: reactive[bool] = reactive(False, layout=True)

    def __init__(self, *, remaining: int = 0, id: str | None = None) -> None:
        """
        Args:
            remaining: Initial seconds remaining.
            id: DOM id.
        """
        super().__init__(id=id)
        self.set_reactive(Countdown.remaining, remaining)
        self._frame = 0
        self._spinner: Timer | None = None

    def render(self) -> str:
        if self.refreshing:
            return self.SPINNER[self._frame % len(self.SPINNER)]
        # Zero renders "0", not "". Reaching zero is a real state, and the
        # caller hides the widget with `display` when it has nothing to show.
        return str(min(self.remaining, self.MAX_SECONDS))

    # ------------------------------------------------------------- spinner

    def on_mount(self) -> None:
        self._sync_spinner()

    def watch_refreshing(self) -> None:
        self._sync_spinner()

    def _sync_spinner(self) -> None:
        # The widget owns its own clock, so a caller only says whether
        # something is in flight -- there is no frame counter to drive from
        # outside, and therefore no second timer to keep in step with this one.
        if not self.is_running:
            # Set before mount; on_mount runs this again once there is a pump
            # to hang a timer on.
            return
        if self.refreshing and self._spinner is None:
            self._frame = 0
            self._spinner = self.set_interval(self.SPINNER_INTERVAL, self._advance)
        elif not self.refreshing and self._spinner is not None:
            self._spinner.stop()
            self._spinner = None

    def _advance(self) -> None:
        self._frame += 1
        self.refresh()
