"""The terminal's window title, set while the app runs and restored after.

    class MyApp(TerminalTitleMixin, App[None]):
        TERMINAL_TITLE = "myapp"

Textual never touches the terminal's title itself -- `App.title` only feeds
the in-app header -- so nothing fights over it. The title is an OSC 0 escape
sequence, which draws nothing and moves no cursor, written through the driver
the way Textual writes its own OSC 52 in `App.copy_to_clipboard`.

The previous title is saved on the terminal's title stack (XTPUSHTITLE) on
mount and popped (XTPOPTITLE) on unmount. The app's `Unmount` is dispatched
before the driver leaves application mode, so the pop still reaches the
terminal. A terminal without a title stack ignores both, and keeps the app's
title until something else sets one.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, ClassVar

from textual.reactive import reactive

if TYPE_CHECKING:
    from textual import events
    from textual.app import App

    _Base = App[Any]
else:
    _Base = object

PUSH_TITLE = "\x1b[22;0t"
POP_TITLE = "\x1b[23;0t"

# C0 and C1 controls: a BEL or ESC inside the title would end the sequence
# early and let the rest of it through as output.
_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f]")


def set_title_sequence(title: str) -> str:
    """The OSC 0 sequence that sets the window (and icon) title."""
    return f"\x1b]0;{_CONTROL.sub('', title)}\x07"


class TerminalTitleMixin(_Base):
    """Sets the terminal's title: `class MyApp(TerminalTitleMixin, App[None])`.

    Its handlers are the private `_on_mount`/`_on_unmount`, which Textual
    calls alongside the app's own, so an `on_mount` that does not call super
    does not switch it off.
    """

    #: The title to set on mount, or None to leave the terminal's title alone.
    TERMINAL_TITLE: ClassVar[str | None] = None

    #: The title currently set. Assign to change it while the app runs.
    terminal_title: reactive[str | None] = reactive(None, init=False)

    _title_pushed: bool = False

    def _on_mount(self, event: events.Mount) -> None:
        self.terminal_title = self.TERMINAL_TITLE

    def _on_unmount(self, event: events.Unmount) -> None:
        if self._title_pushed:
            self._write_terminal(POP_TITLE)
            self._title_pushed = False

    def watch_terminal_title(self, title: str | None) -> None:
        if title is None:
            return
        # Saved on the first title rather than on mount, so an app that only
        # sets one later still gets the terminal's own title back.
        if not self._title_pushed:
            self._write_terminal(PUSH_TITLE)
            self._title_pushed = True
        self._write_terminal(set_title_sequence(title))

    def _write_terminal(self, sequence: str) -> None:
        # `_driver` is private, but it is what Textual itself writes OSC 52
        # through; there is no public way to send raw bytes to the terminal.
        if self._driver is not None:
            self._driver.write(sequence)
