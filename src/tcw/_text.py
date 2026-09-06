"""Small Rich-text helpers shared by the menu bar and the settings dialog."""

from __future__ import annotations

from rich.style import Style
from rich.text import Text
from textual.app import App


def mnemonic_text(label: str, index: int, app: App) -> Text:
    """Render `label` with the character at `index` colored in the current
    theme's accent, rather than underlined -- underlines render inconsistently
    across terminals.

    A negative `index` (what `str.find` returns for a mnemonic letter that is
    not in the label at all) colors nothing rather than styling from the end.
    """
    text = Text(label)
    if index >= 0:
        text.stylize(Style(color=app.theme_variables["accent"]), index, index + 1)
    return text


def instance_glyph(is_instance: bool) -> Text:
    """Marks a settings row as scoped to the active instance, with a blank
    placeholder of equal width so global rows stay aligned with it."""
    if not is_instance:
        return Text(" ", style="dim")
    return Text("◐", style="cyan")
