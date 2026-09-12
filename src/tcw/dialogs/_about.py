"""A small about dialog: a fixed header and scrollable body, both read from
a text file.

The first five lines of the file are the header -- always visible, never
scrolled -- typically a logo or tagline. Everything after that is the body,
shown in a scrollable area capped at ten lines so the dialog itself never
grows past fifteen lines.
"""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Static

from tcw.dialogs._dialog import Dialog

_HEADER_LINES = 5


class AboutDialog(Dialog[None]):
    DEFAULT_CSS = """
    AboutDialog > #dialog {
        width: 57;
        max-width: 100%;
    }
    AboutDialog #about-header {
        height: auto;
    }
    AboutDialog #about-body {
        height: auto;
        max-height: 10;
    }
    """

    def __init__(self, path: str | Path | None = None) -> None:
        """
        Args:
            path: A text file to read the about-text from. Defaults to a
                bundled placeholder when omitted.
        """
        super().__init__()
        self._path = Path(path) if path is not None else None

    def compose(self) -> ComposeResult:
        lines = self._read_lines()
        with Vertical(id="dialog"):
            yield Static("\n".join(lines[:_HEADER_LINES]), id="about-header")
            with VerticalScroll(id="about-body"):
                yield Static("\n".join(lines[_HEADER_LINES:]))

    def _read_lines(self) -> list[str]:
        if self._path is not None:
            text = self._path.read_text(encoding="utf-8")
        else:
            text = (
                files("tcw.dialogs")
                .joinpath("about_default.txt")
                .read_text(encoding="utf-8")
            )
        return text.splitlines()
