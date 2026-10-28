# SPDX-FileCopyrightText: 2026 René de Hesselle <dehesselle@web.de>
#
# SPDX-License-Identifier: 0BSD

"""A menu item that opens the about dialog."""

from __future__ import annotations

from pathlib import Path

from tcoda.widgets._menuitem import MenuItem


class AboutMenuItem(MenuItem):
    """Drop into any menu and the about dialog is wired up.

    The dialog is a modal screen, so it is never composed anywhere -- it has
    to be pushed by something. This is that something, so the app is spared
    both the menu entry and the handler behind it.
    """

    def __init__(
        self,
        label: str = "About ...",
        *,
        id: str = "about",
        mnemonic: str | None = "a",
        shortcut: str | None = None,
        path: str | Path | None = None,
        variables: dict[str, str] | None = None,
        disabled: bool = False,
        name: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(
            label,
            id=id,
            mnemonic=mnemonic,
            shortcut=shortcut,
            disabled=disabled,
            name=name,
            classes=classes,
        )
        self._path = path
        self._variables = variables

    def on_menu_item_pressed(self, event: MenuItem.Pressed) -> None:
        # Not stopped: the app may be listening for it too.
        #
        # Imported here rather than at module scope: tcoda.dialogs pulls in
        # machinery that tcoda.widgets must stay importable without.
        from tcoda.dialogs import AboutDialog

        self.app.push_screen(AboutDialog(self._path, variables=self._variables))
