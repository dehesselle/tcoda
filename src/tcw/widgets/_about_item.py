"""A menu item that opens the about dialog."""

from __future__ import annotations

from pathlib import Path

from tcw.widgets._menuitem import MenuItem


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
    ) -> None:
        super().__init__(
            label, id=id, mnemonic=mnemonic, shortcut=shortcut, action=self._open
        )
        self._path = path

    async def _open(self) -> None:
        # Imported here rather than at module scope: tcw.dialogs imports the
        # about-dialog machinery, and tcw.widgets must stay importable
        # without it (same reasoning as SettingsMenuItem).
        from tcw.dialogs import AboutDialog

        await self.app.push_screen_wait(AboutDialog(self._path))
