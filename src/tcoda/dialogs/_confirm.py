"""A generic yes/no question.

Kept free of any particular question's vocabulary, so the next confirmation
need not invent its own dialog.
"""

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Label, Static

from tcoda.dialogs._dialog import Dialog


class ConfirmDialog(Dialog[bool]):
    """Ask a yes/no question. Dismisses `True` for the confirm button,
    `False` for the cancel button or escape."""

    DEFAULT_CSS = """
    ConfirmDialog > #dialog {
        width: 60;
        max-width: 100%;
    }
    ConfirmDialog #confirm-message {
        margin: 1 0;
    }
    """

    CANCEL_RESULT: ClassVar[bool] = False

    def __init__(
        self,
        message: str,
        *,
        title: str = "Confirm",
        confirm_label: str = "Yes",
        cancel_label: str = "No",
        danger: bool = False,
        focus_cancel: bool = False,
    ) -> None:
        """
        Args:
            message: The question.
            title: The dialog's heading.
            confirm_label: Text of the affirmative button.
            cancel_label: Text of the negative button.
            danger: Style the confirm button as destructive.
            focus_cancel: Focus the cancel button instead of the confirm one,
                so a stray Enter cannot go through with something costly.
        """
        super().__init__()
        self._message = message
        self._title = title
        self._confirm_label = confirm_label
        self._cancel_label = cancel_label
        self._danger = danger
        self._focus_cancel = focus_cancel

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label(self._title, id="title")
            yield Static(self._message, id="confirm-message")
            with Horizontal(id="buttons"):
                yield Button(
                    self._confirm_label,
                    variant="error" if self._danger else "primary",
                    id="confirm-yes",
                )
                yield Button(self._cancel_label, id="confirm-no")

    def on_mount(self) -> None:
        target = "#confirm-no" if self._focus_cancel else "#confirm-yes"
        self.query_one(target, Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        self.dismiss(event.button.id == "confirm-yes")
