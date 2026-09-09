"""The declarative half of the menu bar: `Menu`, `MenuItem`, `MenuSeparator`.

These are widgets rather than plain dataclasses so a menu can be *composed*
the way the rest of a Textual UI is::

    with MenuBar():
        with Menu("File", id="file"):
            yield MenuItem("Open...", id="open", mnemonic="o")
            yield MenuSeparator()
            yield MenuItem("Quit", id="quit", mnemonic="q", action="app.quit")

`Menu` is the clickable title that shows in the bar. Its children never render
there -- they are `display: none` and exist only as declarations that
`MenuBar` reads when it opens the dropdown. That keeps one obvious place to
look for "what can this menu do", and it means an item is a real DOM node, so
`MenuItem.Pressed` bubbles to the screen and `@on(MenuItem.Pressed, "#open")`
works exactly as it does for a `Button`.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import ClassVar

from rich.console import RenderableType
from rich.table import Table
from rich.text import Text
from textual import events
from textual.app import App
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

from tcw._text import mnemonic_text

#: What a `MenuItem`'s `action` may be: a Textual action string run against
#: the screen ("app.quit", "pick_database"), or a zero-argument callable,
#: which may be async.
MenuAction = str | Callable[[], Awaitable[None] | None]


class MenuSeparator(Widget):
    """A non-selectable dividing line between menu items."""

    DEFAULT_CSS = """
    MenuSeparator { display: none; }
    """


class MenuItem(Widget):
    """One selectable row of a pulldown menu.

    Choosing it posts `MenuItem.Pressed`, which bubbles up through the `Menu`
    and the `MenuBar` to the screen. If `action` is given, `MenuBar` also runs
    it from inside its own worker -- which is what makes `push_screen_wait`
    usable there, unlike in a plain message handler.
    """

    DEFAULT_CSS = """
    MenuItem { display: none; }
    """

    #: Greyed out and unselectable. Reactive so a menu's availability can be
    #: updated at any time; the dropdown reads it when it opens.
    disabled: reactive[bool] = reactive(False)

    class Pressed(Message):
        """A menu item was chosen."""

        ALLOW_SELECTOR_MATCH: ClassVar[set[str]] = {"menu"}

        def __init__(self, item: MenuItem, menu: Menu) -> None:
            self.item = item
            #: The `Menu` the item was declared in. Matchable with
            #: `@on(MenuItem.Pressed, "#copy", menu="#left")`, which is how
            #: one item id can appear in two menus.
            self.menu = menu
            super().__init__()

        @property
        def control(self) -> MenuItem:
            return self.item

    def __init__(
        self,
        label: str,
        *,
        id: str | None = None,
        mnemonic: str | None = None,
        shortcut: str | None = None,
        disabled: bool = False,
        action: MenuAction | None = None,
    ) -> None:
        """
        Args:
            label: The text of the row.
            id: DOM id, and what `@on(MenuItem.Pressed, "#id")` matches.
                Textual only requires it to be unique among the items of one
                `Menu`, but it is also a CSS id: an app stylesheet rule for
                the same name will style this item, so prefer a name the app
                does not already use for something else.
            mnemonic: A letter that selects this item while the menu is open.
                Located in `label` by search, so it need not be the first
                character.
            shortcut: Advertises a key binding that does the same thing,
                shown dimmed and right-aligned. Purely a label -- the binding
                itself lives wherever bindings live.
            disabled: See the `disabled` reactive.
            action: Optionally run this as well as posting `Pressed`.
        """
        super().__init__(id=id)
        self.label = label
        self.mnemonic = mnemonic
        self.shortcut = shortcut
        self.action = action
        self.set_reactive(MenuItem.disabled, disabled)

    @property
    def menu(self) -> Menu:
        parent = self.parent
        assert isinstance(parent, Menu), "a MenuItem must be declared inside a Menu"
        return parent

    def press(self) -> None:
        """Post `Pressed` as though the item had been chosen. `MenuBar` calls
        this; an app may too, to route a key binding through the same path."""
        if self.disabled:
            return
        self.post_message(self.Pressed(self, self.menu))

    # ------------------------------------------------------------ rendering

    def _label_text(self, app: App) -> Text:
        if self.mnemonic is None or self.disabled:
            return Text(self.label)
        return mnemonic_text(
            self.label, self.label.lower().find(self.mnemonic.lower()), app
        )

    def prompt(self, app: App) -> RenderableType:
        """How this item appears in the dropdown: its label, with the shortcut
        right-aligned if it has one."""
        label = self._label_text(app)
        if self.shortcut is None:
            return label
        grid = Table.grid(expand=True)
        grid.add_column()
        grid.add_column(justify="right")
        grid.add_row(label, Text(self.shortcut, style="dim"))
        return grid


#: A thing that can appear in a menu.
MenuEntry = MenuItem | MenuSeparator


class Menu(Static):
    """One pulldown menu: the title shown in the bar, plus its entries.

    A `Static` rather than a container, because what it draws is the title.
    Its entries are hidden children, so `width: auto` cannot be measured from
    the (empty) child arrangement the way Textual would normally do it -- see
    `get_content_width`.
    """

    DEFAULT_CSS = """
    Menu {
        width: auto;
        height: 1;
        padding: 0 2;
        color: $text;
    }
    Menu:hover { background: $boost; }
    Menu.-armed { background: $boost; }
    """

    #: Highlighted as the menu the bar is currently on.
    armed: reactive[bool] = reactive(False)

    class Clicked(Message):
        """The title was clicked. Handled by the enclosing `MenuBar`."""

        def __init__(self, menu: Menu) -> None:
            self.menu = menu
            super().__init__()

    def __init__(self, title: str, *, id: str | None = None) -> None:
        """
        Args:
            title: The text shown in the bar. Its first letter is the
                mnemonic that selects this menu from the bar-only stage.
            id: DOM id, used to open this menu by name. Also a CSS id --
                see the warning on `MenuItem`.
        """
        super().__init__(title, id=id)
        self.title_text = title

    @property
    def mnemonic(self) -> str:
        return self.title_text[:1].lower()

    @property
    def entries(self) -> list[MenuEntry]:
        """The declared entries, in composition order."""
        return [
            child
            for child in self.children
            if isinstance(child, MenuItem | MenuSeparator)
        ]

    def on_mount(self) -> None:
        self._refresh_mnemonic_color()
        self.watch(self.app, "theme", self._refresh_mnemonic_color, init=False)

    def _refresh_mnemonic_color(self, *_: object) -> None:
        self.update(mnemonic_text(self.title_text, 0, self.app))

    def watch_armed(self, armed: bool) -> None:
        self.set_class(armed, "-armed")

    def on_click(self, event: events.Click) -> None:
        event.stop()
        self.post_message(self.Clicked(self))

    # Auto width/height would otherwise be measured from this widget's
    # children, which are all display:none, leaving the title clipped to its
    # padding. The title is what is actually drawn, so it is what to measure.
    def get_content_width(self, container: object, viewport: object) -> int:
        return Text(self.title_text).cell_len

    def get_content_height(
        self, container: object, viewport: object, width: int
    ) -> int:
        return 1
