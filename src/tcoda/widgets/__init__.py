# SPDX-FileCopyrightText: 2026 René de Hesselle <dehesselle@web.de>
#
# SPDX-License-Identifier: 0BSD

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

from tcoda.widgets._about_item import AboutMenuItem
from tcoda.widgets._chord_viewer import ChordViewer
from tcoda.widgets._countdown import Countdown
from tcoda.widgets._datatable import DataTable
from tcoda.widgets._footer import (
    Footer,
    FooterBinding,
    FooterEntry,
    FooterGroup,
    FooterGroupLabel,
    FooterStatus,
    sort_by_key,
)
from tcoda.widgets._header import Header, HeaderArea
from tcoda.widgets._log_viewer import TOGGLE_ACTION, LogViewer
from tcoda.widgets._menubar import OPEN_ACTION, MenuBar
from tcoda.widgets._menuitem import Menu, MenuAction, MenuEntry, MenuItem, MenuSeparator
from tcoda.widgets._resizable import Resizable
from tcoda.widgets._settings_item import SettingsMenuItem

__all__ = [
    "OPEN_ACTION",
    "TOGGLE_ACTION",
    "AboutMenuItem",
    "ChordViewer",
    "Countdown",
    "DataTable",
    "Footer",
    "FooterBinding",
    "FooterEntry",
    "FooterGroup",
    "FooterGroupLabel",
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
