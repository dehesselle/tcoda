"""Small Rich-text helpers shared by the menu bar and the settings dialog.

Neither hardcodes a colour: `mnemonic_text` reads the running app's theme
accent, and `marker_text` takes whatever style the caller resolved. `tcoda`
ships no palette of its own.
"""

from __future__ import annotations

from rich.cells import cell_len
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


def marker_text(glyph: str, style: str, *, present: bool) -> Text:
    """A row marker, or a blank of the same width when the row has none.

    The blank is measured from the glyph rather than assumed to be one cell,
    so a two-cell marker (an emoji, say) still leaves unmarked rows aligned
    with marked ones.
    """
    if not present:
        return Text(" " * cell_len(glyph))
    return Text(glyph, style=style)
