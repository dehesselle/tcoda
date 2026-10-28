# SPDX-FileCopyrightText: 2026 René de Hesselle <dehesselle@web.de>
#
# SPDX-License-Identifier: 0BSD

"""Every public widget and dialog takes Textual's standard constructor
arguments, so it can be named, styled and disabled like Textual's own."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from textual.dom import DOMNode
from textual.widget import Widget

from tcoda.dialogs import AboutDialog, ConfirmDialog, SettingsDialog
from tcoda.plot import Plot
from tcoda.widgets import (
    AboutMenuItem,
    ChordViewer,
    Countdown,
    DataTable,
    Footer,
    Header,
    LogViewer,
    Menu,
    MenuBar,
    MenuItem,
    MenuSeparator,
    SettingsMenuItem,
    TabbedContent,
    TabPane,
)
from tcoda.widgets._multi_select import MultiSelect

WIDGETS: list[Callable[..., Widget]] = [
    MenuBar,
    lambda **kwargs: Menu("File", **kwargs),
    lambda **kwargs: MenuItem("Open", **kwargs),
    MenuSeparator,
    AboutMenuItem,
    SettingsMenuItem,
    Header,
    Footer,
    Countdown,
    LogViewer,
    ChordViewer,
    MultiSelect,
    DataTable,
    TabbedContent,
    lambda **kwargs: TabPane("Tab", **kwargs),
    Plot,
]

DIALOGS: list[Callable[..., DOMNode]] = [
    lambda **kwargs: ConfirmDialog("Sure?", **kwargs),
    AboutDialog,
    SettingsDialog,
]


def _standard(**extra: Any) -> dict[str, Any]:
    return {"name": "the-name", "id": "the-id", "classes": "one two", **extra}


@pytest.mark.parametrize("factory", WIDGETS)
def test_a_widget_takes_the_standard_arguments(factory: Callable[..., Widget]) -> None:
    widget = factory(**_standard(disabled=True))
    assert widget.name == "the-name"
    assert widget.id == "the-id"
    assert widget.has_class("one", "two")
    assert widget.disabled


@pytest.mark.parametrize("factory", DIALOGS)
def test_a_dialog_takes_the_standard_arguments(
    factory: Callable[..., DOMNode],
) -> None:
    dialog = factory(**_standard())
    assert dialog.name == "the-name"
    assert dialog.id == "the-id"
    assert dialog.has_class("one", "two")
