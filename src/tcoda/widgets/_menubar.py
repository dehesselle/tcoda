# SPDX-FileCopyrightText: 2026 René de Hesselle <dehesselle@web.de>
#
# SPDX-License-Identifier: 0BSD

"""The menu bar: a row of pulldown menu titles plus an optional trailing label.

Composed declaratively -- see `tcoda.widgets._menuitem` -- and self-driving:
yield one, and its key (F9 by default) opens it. All the staging lives here
rather than on the host screen, so adopting the bar is one `yield` and a
handful of `@on(MenuItem.Pressed, ...)` handlers.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from textual import work
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

from tcoda.widgets._dropdown import MenuBarOverlay, MenuDropdown, OpenNeighbor
from tcoda.widgets._menuitem import Menu, MenuItem
from tcoda.widgets._screen_keys import install_screen_key, uninstall_screen_key

if TYPE_CHECKING:
    from textual.screen import Screen

#: The action `MenuBar` installs on its screen, and therefore the name to use
#: when something other than the key binding wants to open the bar --
#: `run_action("screen.open_menubar")`.
OPEN_ACTION = "open_menubar"


class MenuBar(Widget, can_focus=False):
    """The pulldown menu bar, docked to the top of its screen."""

    DEFAULT_CSS = """
    MenuBar {
        dock: top;
        height: 1;
        layout: horizontal;
        background: $panel;
        /* One row, never scrolled. Without this, a child mis-sized by an app
           stylesheet (an id clash, say) draws a scrollbar across the bar
           instead of just looking slightly wrong. */
        overflow: hidden hidden;
    }
    MenuBar > #menubar-trailing {
        width: 1fr;
        padding: 0 2;
        color: $text-disabled;
        content-align: right middle;
    }
    """

    # auto_hide keeps the bar display:none except while a menu is actually in
    # use, so the rest of the screen reclaims its row the remainder of the
    # time. Off means permanently visible.
    auto_hide: reactive[bool] = reactive(True)
    revealed: reactive[bool] = reactive(False)

    def __init__(
        self,
        *,
        trailing: str = "",
        auto_hide: bool = True,
        key: str | None = "f9",
        key_description: str = "Menu",
        show_key: bool = True,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        """
        Args:
            trailing: Right-aligned text filling the rest of the bar, e.g.
                an app name and version.
            auto_hide: Hide the bar except while a menu is in use.
            key: The key that opens the bar, or None to bind it yourself
                (see `OPEN_ACTION`).
            key_description: How that key is described in the footer.
            show_key: Whether that key appears in the footer at all.
            name: The widget's name.
            id: DOM id.
            classes: CSS classes.
            disabled: Whether the widget starts out disabled.
        """
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self._trailing = trailing
        self._key = key
        self._key_description = key_description
        self._show_key = show_key
        self.set_reactive(MenuBar.auto_hide, auto_hide)
        self.set_reactive(MenuBar.revealed, not auto_hide)
        self._key_screen: Screen[Any]  # set at mount

    # No compose(): children arrive through the `with MenuBar():` protocol,
    # and Textual mounts those *before* anything compose() yields. Extending
    # the list here is what puts the trailing label after the titles.
    def _extend_compose(self, widgets: list[Widget]) -> None:
        widgets.append(Static(self._trailing, id="menubar-trailing"))

    @property
    def menus(self) -> list[Menu]:
        """The declared menus, left to right."""
        return [child for child in self.children if isinstance(child, Menu)]

    @property
    def enabled_menus(self) -> list[Menu]:
        """The menus that can be opened, left to right: a disabled one, or
        any in a disabled bar, is passed over by keys and mouse alike."""
        return [menu for menu in self.menus if not menu.is_disabled]

    def menu(self, menu_id: str) -> Menu:
        """The menu with this id."""
        for menu in self.menus:
            if menu.id == menu_id:
                return menu
        raise ValueError(f"unknown menu: {menu_id!r}")

    # ------------------------------------------------------------- key setup

    def on_mount(self) -> None:
        self._sync_display()
        # On the screen rather than on the bar, which is never focused -- see
        # `tcoda.widgets._screen_keys`. That is also why this works whether
        # the bar sits on the app's default screen or on one that was pushed.
        self._key_screen = install_screen_key(
            self,
            OPEN_ACTION,
            self.open,
            self._key,
            self._key_description,
            show=self._show_key,
        )

    def on_unmount(self) -> None:
        uninstall_screen_key(self._key_screen, self, OPEN_ACTION)

    # -------------------------------------------------------------- display

    def watch_auto_hide(self) -> None:
        self._sync_display()

    def watch_revealed(self) -> None:
        self._sync_display()

    def _sync_display(self) -> None:
        self.display = not self.auto_hide or self.revealed

    def reveal(self) -> None:
        self.revealed = True

    def conceal(self) -> None:
        # Unconditional, even when auto_hide is off: `revealed` means "a menu
        # is in use right now", and `_sync_display` keeps a non-auto-hiding
        # bar on screen regardless. Leaving it set would strand the bar
        # visible if auto_hide were switched on afterwards -- which is exactly
        # what a settings dialog opened *from* the menu does.
        self.revealed = False

    def set_armed(self, menu: Menu | None) -> None:
        for candidate in self.menus:
            candidate.armed = candidate is menu

    # ----------------------------------------------------------------- drive

    def on_menu_clicked(self, event: Menu.Clicked) -> None:
        event.stop()
        self.open(event.menu)

    @work
    async def open(self, menu: Menu | str | None = None) -> None:
        """Open the bar, at `menu` if given or in its bar-only stage if not.

        A worker, because the whole flow is a sequence of `push_screen_wait`
        calls -- and because that is what lets an item's `action` run
        somewhere `push_screen_wait` is legal.
        """
        menus = self.enabled_menus
        if not menus:
            return
        if isinstance(menu, str):
            menu = self.menu(menu)
        if menu is not None and menu not in menus:
            return
        self.reveal()
        if self.auto_hide:
            # Reappearing changes layout (the rest of the screen gives back
            # its row), so a title's region -- needed to position the dropdown
            # under it -- isn't valid again until after that reflow happens.
            await self._wait_for_layout()
        try:
            if menu is None:
                menu = await self.app.push_screen_wait(MenuBarOverlay(self, menus[0]))
                if menu is None:
                    return
            await self._run(menu)
        finally:
            self.set_armed(None)
            self.conceal()

    async def _run(self, menu: Menu) -> None:
        """Show `menu`, walking sideways for as long as Left/Right is used."""
        while True:
            self.set_armed(menu)
            result = await self.app.push_screen_wait(
                MenuDropdown(self, menu, x_offset=menu.region.x)
            )
            if isinstance(result, OpenNeighbor):
                menus = self.enabled_menus
                index = menus.index(menu) if menu in menus else 0
                menu = menus[(index + result.direction) % len(menus)]
                continue
            if isinstance(result, Menu):
                menu = result
                continue
            if isinstance(result, MenuItem) and not result.is_disabled:
                await self._chose(result)
            return

    async def _chose(self, item: MenuItem) -> None:
        item.press()
        if item.action is not None:
            await self.app.run_action(item.action, default_namespace=self.screen)

    async def _wait_for_layout(self) -> None:
        layout_done = asyncio.Event()
        self.call_after_refresh(layout_done.set)
        await layout_done.wait()
