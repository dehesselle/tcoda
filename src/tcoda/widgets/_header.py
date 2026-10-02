"""A single-line header with independently clickable left/middle/right areas.

Styled like Textual's own `Header` (same colors, and the same centered,
ellipsized title in the middle), but without an icon or a clock. The middle
area tracks the app/screen title live, exactly as Textual's `Header` does,
until `show_title` is turned off::

    def compose(self) -> ComposeResult:
        yield Header(left="MyApp", right="v1.0")

    @on(HeaderArea.Clicked, "#header-left")
    def _left_clicked(self) -> None:
        ...

Ongoing updates to the left/right text go through the area widgets
themselves -- `header.left.update("Connected")` -- rather than through
bespoke setters on `Header`.
"""

from __future__ import annotations

from textual import events
from textual.app import ComposeResult
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static


class HeaderArea(Static):
    """One clickable, plain-text region of a `Header`."""

    # Static's own default is `height: auto`, which collapses to 0 rows when
    # the area holds no text -- leaving nothing for a click (or docking) to
    # land on. A header area is always exactly one row.
    DEFAULT_CSS = """
    HeaderArea {
        height: 1;
    }
    """

    class Clicked(Message):
        """This area was clicked."""

        def __init__(self, area: HeaderArea) -> None:
            self.area = area
            super().__init__()

        @property
        def control(self) -> HeaderArea:
            return self.area

    def on_click(self, event: events.Click) -> None:
        event.stop()
        self.post_message(self.Clicked(self))


class Header(Widget, can_focus=False):
    """A single-line header, docked to the top of its screen."""

    # The three areas are equal 1fr columns rather than dock-to-content-width,
    # so the middle stays centered on the screen no matter how much text is
    # in left/right (a wide right area -- e.g. version + commit + timestamp --
    # would otherwise shove the "centered" middle text off-center, since it'd
    # only be centered in whatever space docking left it). The trade-off:
    # left/right are now capped at a third of the width each and ellipsize
    # like the middle already did, instead of always showing in full.
    DEFAULT_CSS = """
    Header {
        dock: top;
        width: 100%;
        height: 1;
        background: $panel;
        color: $foreground;
        layout: horizontal;
    }
    Header > #header-left {
        width: 1fr;
        padding: 0 1;
        content-align: left middle;
        text-wrap: nowrap;
        text-overflow: ellipsis;
    }
    Header > #header-right {
        width: 1fr;
        padding: 0 1;
        content-align: right middle;
        text-wrap: nowrap;
        text-overflow: ellipsis;
    }
    Header > #header-middle {
        width: 1fr;
        content-align: center middle;
        text-wrap: nowrap;
        text-overflow: ellipsis;
    }
    """

    #: Track the app/screen title in the middle area. Off means the middle
    #: area is left alone -- set its text yourself via `header.middle.update`.
    show_title: reactive[bool] = reactive(True)

    def __init__(
        self,
        *,
        left: str = "",
        right: str = "",
        show_title: bool = True,
        id: str | None = None,
    ) -> None:
        """
        Args:
            left: Initial text of the left area, docked to the screen edge.
            right: Initial text of the right area, docked to the screen edge.
            show_title: See the `show_title` reactive.
            id: DOM id.
        """
        super().__init__(id=id)
        self._left = left
        self._right = right
        self.set_reactive(Header.show_title, show_title)

    def compose(self) -> ComposeResult:
        yield HeaderArea(self._left, id="header-left")
        yield HeaderArea("", id="header-middle")
        yield HeaderArea(self._right, id="header-right")

    @property
    def left(self) -> HeaderArea:
        """The left area. Call `.update(text)` on it to change its text."""
        return self.query_one("#header-left", HeaderArea)

    @property
    def middle(self) -> HeaderArea:
        """The middle area. Shows the live title while `show_title` is on."""
        return self.query_one("#header-middle", HeaderArea)

    @property
    def right(self) -> HeaderArea:
        """The right area. Call `.update(text)` on it to change its text."""
        return self.query_one("#header-right", HeaderArea)

    # ------------------------------------------------------------ title sync

    def on_mount(self) -> None:
        self._sync_title()
        # Mirrors Textual's own Header: a screen may set its own title/
        # sub_title, overriding the app's, so both are watched.
        self.watch(self.app, "title", self._sync_title, init=False)
        self.watch(self.app, "sub_title", self._sync_title, init=False)
        self.watch(self.screen, "title", self._sync_title, init=False)
        self.watch(self.screen, "sub_title", self._sync_title, init=False)

    def watch_show_title(self, show_title: bool) -> None:
        if show_title:
            self._sync_title()

    def _sync_title(self) -> None:
        if not self.show_title:
            return
        title = self.screen.title if self.screen.title else self.app.title
        sub_title = (
            self.screen.sub_title if self.screen.sub_title else self.app.sub_title
        )
        self.middle.update(self.app.format_title(title, sub_title))
