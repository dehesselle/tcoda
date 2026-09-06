"""The two modal stages of using the menu bar.

Midnight-Commander style, and staged on purpose: `MenuBarSelectScreen`
highlights a title without showing its items yet, so a mnemonic letter can
never be ambiguous between "pick a top-level menu" and "pick an item" the way
it would be if a dropdown were already open. `MenuDropdown` is the second
stage.

Both are internal to `MenuBar`, which is the only thing that pushes them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
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


MenuDropdownResult = MenuItem | OpenNeighbor | None


class MenuBarSelectScreen(ModalScreen[Menu | None]):
    """The bar-only stage: arrow or type a letter to pick a title."""

    DEFAULT_CSS = """
    MenuBarSelectScreen {
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


class MenuDropdown(ModalScreen[MenuDropdownResult]):
    """A single pulldown menu's contents, positioned under its title."""

    DEFAULT_CSS = """
    MenuDropdown {
        background: transparent;
    }
    MenuDropdown > OptionList {
        width: 32;
        height: auto;
        max-height: 15;
        border: round $primary;
        background: $surface;
    }
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "dismiss_none", "Close menu", show=False),
        Binding("left", "neighbor(-1)", "Previous menu", show=False),
        Binding("right", "neighbor(1)", "Next menu", show=False),
    ]

    def __init__(self, menu: Menu, *, x_offset: int) -> None:
        super().__init__()
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
