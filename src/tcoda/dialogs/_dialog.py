# SPDX-FileCopyrightText: 2026 René de Hesselle <dehesselle@web.de>
#
# SPDX-License-Identifier: 0BSD

"""Shared chrome for centered modal dialogs.

Subclasses still set their own `#dialog` width/height -- those genuinely
differ between a form and a picker -- this only hoists what every dialog
shares: a bordered box, a bold centered title, a right-aligned button row,
and escape-to-cancel.

Escape dismisses with `CANCEL_RESULT`. A dialog that must not be escapable
overrides `check_action` to disable the binding rather than dropping it:
Textual merges BINDINGS across a class hierarchy, so a subclass cannot remove
one it inherited.
"""

from __future__ import annotations

from typing import Any, ClassVar, TypeVar

from textual.binding import Binding, BindingType
from textual.screen import ModalScreen

ResultT = TypeVar("ResultT")


class Dialog(ModalScreen[ResultT]):
    """A centered modal that asks something and dismisses with a result."""

    DEFAULT_CSS = """
    Dialog {
        align: center middle;
    }
    Dialog > #dialog {
        height: auto;
        border: thick $background 80%;
        background: $surface;
        padding: 1 2;
    }
    Dialog > #dialog > #title {
        text-style: bold;
        width: 100%;
        content-align: center middle;
    }
    Dialog > #dialog > #buttons {
        height: auto;
        align-horizontal: right;
    }
    Dialog > #dialog > #buttons Button {
        margin: 0 0 0 1;
    }
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    CANCEL_RESULT: ClassVar[Any] = None

    def action_cancel(self) -> None:
        self.dismiss(self.CANCEL_RESULT)
