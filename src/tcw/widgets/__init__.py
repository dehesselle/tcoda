"""Composable widgets.

The menu bar is declared inline in `compose()`::

    with MenuBar(trailing="myapp 1.0"):
        with Menu("File", id="file"):
            yield MenuItem("Open...", id="open", mnemonic="o")
            yield MenuSeparator()
            yield SettingsMenuItem()
            yield MenuItem("Quit", id="quit", mnemonic="q", action="app.quit")

and choosing an item posts `MenuItem.Pressed`, so handlers read like any
other Textual widget's::

    @on(MenuItem.Pressed, "#open")
    def _open(self) -> None:
        ...
"""

from tcw.widgets._about_item import AboutMenuItem
from tcw.widgets._countdown import Countdown
from tcw.widgets._datatable import DataTable
from tcw.widgets._footer import (
    Footer,
    FooterBinding,
    FooterEntry,
    FooterStatus,
    sort_by_key,
)
from tcw.widgets._header import Header, HeaderArea
from tcw.widgets._log_viewer import TOGGLE_ACTION, LogViewer
from tcw.widgets._menubar import OPEN_ACTION, MenuBar
from tcw.widgets._menuitem import Menu, MenuAction, MenuEntry, MenuItem, MenuSeparator
from tcw.widgets._resizable import Resizable
from tcw.widgets._settings_item import SettingsMenuItem

__all__ = [
    "OPEN_ACTION",
    "TOGGLE_ACTION",
    "AboutMenuItem",
    "Countdown",
    "DataTable",
    "Footer",
    "FooterBinding",
    "FooterEntry",
    "FooterStatus",
    "Header",
    "HeaderArea",
    "LogViewer",
    "Menu",
    "MenuAction",
    "MenuBar",
    "MenuEntry",
    "MenuItem",
    "MenuSeparator",
    "Resizable",
    "SettingsMenuItem",
    "sort_by_key",
]
