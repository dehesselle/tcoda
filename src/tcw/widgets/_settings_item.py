"""A menu item that opens the settings dialog."""

from __future__ import annotations

from tcw.widgets._menuitem import MenuItem


class SettingsMenuItem(MenuItem):
    """Drop into any menu and the settings dialog is wired up.

    The dialog is a modal screen, so it is never composed anywhere -- it has
    to be pushed by something. This is that something, so the app is spared
    both the menu entry and the handler behind it.
    """

    def __init__(
        self,
        label: str = "Settings ...",
        *,
        id: str = "settings",
        mnemonic: str | None = "s",
        shortcut: str | None = None,
    ) -> None:
        super().__init__(
            label, id=id, mnemonic=mnemonic, shortcut=shortcut, action=self._open
        )

    async def _open(self) -> None:
        # Imported here rather than at module scope: tcw.dialogs imports the
        # settings machinery, and tcw.widgets must stay importable without it.
        from tcw.dialogs import SettingsDialog

        await self.app.push_screen_wait(SettingsDialog())
