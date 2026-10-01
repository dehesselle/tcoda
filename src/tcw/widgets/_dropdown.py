"""The two modal stages of using the menu bar.

Midnight-Commander style, and staged on purpose: `MenuBarOverlay` highlights
a title without showing its items yet, so a mnemonic letter can never be
ambiguous between "pick a top-level menu" and "pick an item" the way it would
be if a dropdown were already open. `MenuDropdown` is the second stage.

Neither is a dialog: both are transparent, render no chrome of their own, and
exist only to capture the keyboard and mouse while a menu is in use.

Both are internal to `MenuBar`, which is the only thing that pushes them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from textual import events
from textual.app import ComposeResult
from textual.await_complete import AwaitComplete
from textual.binding import Binding, BindingType
from textual.geometry import Offset
from textual.screen import ModalScreen
from textual.widgets import OptionList
from textual.widgets.option_list import Option

from tcw.widgets._menuitem import Menu, MenuItem, MenuSeparator

if TYPE_CHECKING:
    from tcw.widgets._menubar import MenuBar


@dataclass(frozen=True)
class OpenNeighbor:
    """Returned by `MenuDropdown` when Left/Right should switch to the
    adjacent top-level menu instead of selecting an item."""

    direction: int  # -1 or 1


#: A dropdown or the bar-only stage may also be dismissed with a specific
#: `Menu` to jump to -- how the mouse asks for what Left/Right asks for with
#: `OpenNeighbor`, since a click or hover can land on any title, not just a
#: neighbouring one.
MenuDropdownResult = MenuItem | OpenNeighbor | Menu | None


def _menu_at(menus: list[Menu], offset: Offset) -> Menu | None:
    """Which of `menus`, if any, occupies screen position `offset`.

    Both modal screens below sit directly on top of the bar's own screen, so
    a `Menu` title's `region` -- computed by that screen's last layout -- is
    still in the same coordinate space as a mouse event's `screen_offset`.
    """
    for menu in menus:
        if menu.region.contains(*offset):
            return menu
    return None


class _MenuStage[ResultT](ModalScreen[ResultT]):
    """What both stages share: a dismiss that only ever pops itself."""

    def dismiss(self, result: ResultT | None = None) -> AwaitComplete:
        # Events already queued on this screen keep arriving after the first
        # dismiss has popped it -- a fast mouse sweep queues several moves --
        # and Textual's dismiss pops whatever is on top: the base screen
        # (ScreenStackError) or the next stage (orphaning the MenuBar worker's
        # future, so the bar hangs). Guarding here rather than at each call
        # site is what keeps the next handler that dismisses covered too.
        if not self.is_active:
            return AwaitComplete.nothing()
        return super().dismiss(result)


class MenuBarOverlay(_MenuStage[Menu | None]):
    """The bar-only stage: arrow or type a letter to pick a title."""

    DEFAULT_CSS = """
    MenuBarOverlay {
        background: transparent;
    }
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "dismiss_none", "Close menu", show=False),
        Binding("left", "move(-1)", "Previous menu", show=False),
        Binding("right", "move(1)", "Next menu", show=False),
        Binding("enter", "open", "Open menu", show=False),
        Binding("down", "open", "Open menu", show=False),
    ]

    def __init__(self, menu_bar: MenuBar, initial: Menu) -> None:
        # The bar is passed in rather than looked up: `self.app.query_one`
        # only ever searches the app's default screen, and a MenuBar may well
        # live on a screen that was explicitly pushed.
        super().__init__()
        self._menu_bar = menu_bar
        self._armed = initial

    def on_mount(self) -> None:
        self._menu_bar.set_armed(self._armed)

    def action_dismiss_none(self) -> None:
        self.dismiss(None)

    def action_move(self, direction: int) -> None:
        menus = self._menu_bar.menus
        index = menus.index(self._armed)
        self._armed = menus[(index + direction) % len(menus)]
        self._menu_bar.set_armed(self._armed)

    def action_open(self) -> None:
        self.dismiss(self._armed)

    def on_key(self, event: events.Key) -> None:
        character = event.character
        if character is None or not character.isalpha():
            return
        letter = character.lower()
        for menu in self._menu_bar.menus:
            if menu.mnemonic == letter:
                event.stop()
                self.dismiss(menu)
                return

    def on_mouse_move(self, event: events.MouseMove) -> None:
        menu = _menu_at(self._menu_bar.menus, event.screen_offset)
        if menu is not None and menu is not self._armed:
            self._armed = menu
            self._menu_bar.set_armed(menu)

    def on_click(self, event: events.Click) -> None:
        menu = _menu_at(self._menu_bar.menus, event.screen_offset)
        # A click off every title closes the bar, matching Escape -- there is
        # nothing else on this screen a click could sensibly mean.
        self.dismiss(menu)


class MenuDropdown(_MenuStage[MenuDropdownResult]):
    """A single pulldown menu's contents, positioned under its title."""

    DEFAULT_CSS = """
    MenuDropdown {
        background: transparent;
    }
    MenuDropdown > OptionList {
        width: 32;
        height: auto;
        max-height: 15;
        border: round $border;
        background: $surface;
    }
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "dismiss_none", "Close menu", show=False),
        Binding("left", "neighbor(-1)", "Previous menu", show=False),
        Binding("right", "neighbor(1)", "Next menu", show=False),
    ]

    def __init__(self, menu_bar: MenuBar, menu: Menu, *, x_offset: int) -> None:
        # `menu_bar` is passed in for the same reason `MenuBarOverlay` takes
        # it: it is what lets hovering or clicking a *different* title jump
        # straight to it, and a plain `menu.parent` lookup would need a runtime
        # import of `MenuBar` that `_menubar.py` importing this module the
        # other way round rules out.
        super().__init__()
        self._menu_bar = menu_bar
        self._menu = menu
        self._entries = menu.entries
        self._x_offset = x_offset

    def compose(self) -> ComposeResult:
        # `None` is Textual's own way of asking for a divider rule under the
        # previously added option, rather than a selectable row of its own --
        # reusing it is what makes separators skip over for free during
        # cursor navigation, with no extra logic here.
        content = [
            None
            if isinstance(entry, MenuSeparator)
            else Option(entry.prompt(self.app), id=entry.id, disabled=entry.disabled)
            for entry in self._entries
        ]
        option_list = OptionList(*content)
        option_list.styles.offset = (self._x_offset, 1)
        yield option_list

    def on_mount(self) -> None:
        self.query_one(OptionList).focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        item = next(
            (
                entry
                for entry in self._entries
                if isinstance(entry, MenuItem) and entry.id == event.option_id
            ),
            None,
        )
        self.dismiss(item)

    def action_dismiss_none(self) -> None:
        self.dismiss(None)

    def action_neighbor(self, direction: int) -> None:
        self.dismiss(OpenNeighbor(direction))

    def _title_at(self, offset: Offset) -> Menu | None:
        # The OptionList handles its own hover/click; only a title in the bar
        # above it is this screen's business.
        if self.query_one(OptionList).region.contains(*offset):
            return None
        return _menu_at(self._menu_bar.menus, offset)

    def on_mouse_move(self, event: events.MouseMove) -> None:
        menu = self._title_at(event.screen_offset)
        if menu is not None and menu is not self._menu:
            self.dismiss(menu)

    def on_click(self, event: events.Click) -> None:
        if self.query_one(OptionList).region.contains(*event.screen_offset):
            return
        menu = _menu_at(self._menu_bar.menus, event.screen_offset)
        # Clicking the open menu's own title closes it, like clicking an
        # already-pressed toggle button; clicking a different title jumps to
        # it; clicking anywhere else (there is nothing else on this screen)
        # closes it, same as Escape.
        self.dismiss(None if menu is self._menu else menu)

    def on_key(self, event: events.Key) -> None:
        character = event.character
        if character is None or not character.isalpha():
            return
        letter = character.lower()
        for entry in self._entries:
            if (
                isinstance(entry, MenuItem)
                and not entry.disabled
                and entry.mnemonic is not None
                and entry.mnemonic.lower() == letter
            ):
                event.stop()
                self.dismiss(entry)
                return
