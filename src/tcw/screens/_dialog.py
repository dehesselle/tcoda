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


class DialogScreen(ModalScreen[ResultT]):
    DEFAULT_CSS = """
    DialogScreen {
        align: center middle;
    }
    DialogScreen > #dialog {
        height: auto;
        border: round $primary;
        background: $surface;
        padding: 1 2;
    }
    DialogScreen > #dialog > #title {
        text-style: bold;
        width: 100%;
        content-align: center middle;
    }
    DialogScreen > #dialog > #buttons {
        height: auto;
        align-horizontal: right;
    }
    DialogScreen > #dialog > #buttons Button {
        margin: 0 0 0 1;
    }

    /* The unstyled (default) variant defaults to $surface, which sits so
       close to the screen background and to $panel that it visually
       disappears next to a -primary sibling. Bump it up the existing gray
       ramp instead of introducing a new color.
       Marked explicitly with a "button-gray" class from the call site rather
       than matched by variant: a "default" variant Button's `variant`
       reactive is declared with "default" as its initial value, and Textual
       only calls watch_variant() on an actual change, so a button that is
       never given another variant never gets a "-default" class added at all
       -- there is no selector meaning "whichever variant this is, it isn't
       -primary/-success/-warning/-error", since Textual's CSS has no :not().
       Background only, no border override: a compact button forces
       `border: none !important` in its own DEFAULT_CSS, so a border rule
       here would put a border back specifically on compact gray buttons
       while their compact -primary sibling stays borderless. */
    DialogScreen Button.button-gray {
        background: $surface-lighten-3;

        &:hover {
            background: $surface-lighten-1;
        }
    }
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    CANCEL_RESULT: ClassVar[Any] = None

    def action_cancel(self) -> None:
        self.dismiss(self.CANCEL_RESULT)
