# SPDX-FileCopyrightText: 2026 René de Hesselle <dehesselle@web.de>
#
# SPDX-License-Identifier: 0BSD

"""A chart of where the bytes are: the browsed directory's files, totalled by
extension, on a `tcoda.plot.Plot` inside a demo dialog."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Label

from tcoda.demo._browser import FileInfo
from tcoda.dialogs import Dialog
from tcoda.plot import Plot


def sizes_by_extension(files: Iterable[FileInfo]) -> dict[str, float]:
    """KiB per extension, largest first; files without one count as "(none)"."""
    totals: Counter[str] = Counter()
    for info in files:
        totals[info.path.suffix or "(none)"] += info.size / 1024
    return dict(totals.most_common())


class SizesDialog(Dialog[None]):
    """Bars of the KiB taken by each extension, with the mean marked."""

    DEFAULT_CSS = """
    SizesDialog > #dialog {
        width: 72;
        max-width: 100%;
    }
    SizesDialog Plot {
        height: 18;
        margin: 1 0;
    }
    """

    def __init__(self, title: str, files: Iterable[FileInfo]) -> None:
        """
        Args:
            title: What the files are, for the dialog's title.
            files: The files to total up.
        """
        super().__init__()
        self._title = title
        self._sizes = sizes_by_extension(files)

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label(f"Sizes in {self._title}", id="title")
            # Filled in before it is mounted, like any other widget's content.
            plot = Plot(x_label="extension", y_label="KiB", legend="top-right")
            if self._sizes:
                plot.bar(list(self._sizes), list(self._sizes.values()), label="KiB")
                # The mean, as a flat line across every bar.
                mean = sum(self._sizes.values()) / len(self._sizes)
                plot.plot(
                    [0.5, len(self._sizes) + 0.5],
                    [mean, mean],
                    style="$warning",
                    hires_mode="braille",
                    label="mean",
                )
            plot.y_limits = (0, None)
            yield plot
            with Horizontal(id="buttons"):
                yield Button("Close", variant="primary", id="sizes-close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        self.dismiss(None)
