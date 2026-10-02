"""A dialog of the demo's own, built on tcoda's `Dialog` chrome the way a
consuming app would build one."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, Label, Static

from tcoda.dialogs import Dialog


class FilterDialog(Dialog[str | None]):
    """Ask for a glob pattern. Dismisses with the pattern, `""` to clear the
    filter, or None (escape) to leave it as it was."""

    DEFAULT_CSS = """
    FilterDialog > #dialog {
        width: 50;
        max-width: 100%;
    }
    FilterDialog #filter-hint {
        margin: 1 0 0 0;
        color: $text-muted;
    }
    FilterDialog #filter-pattern {
        margin: 1 0;
    }
    """

    def __init__(self, pattern: str = "") -> None:
        """
        Args:
            pattern: The filter currently applied, to edit.
        """
        super().__init__()
        self._pattern = pattern

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label("Filter", id="title")
            yield Static(
                "Show only the files whose name matches a glob pattern.",
                id="filter-hint",
            )
            yield Input(self._pattern, placeholder="e.g. *.md", id="filter-pattern")
            with Horizontal(id="buttons"):
                yield Button("OK", variant="primary", id="filter-ok")
                yield Button("Clear", id="filter-clear")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        self.dismiss(event.value.strip())

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.id == "filter-ok":
            self.dismiss(self.query_one("#filter-pattern", Input).value.strip())
        else:
            self.dismiss("")
