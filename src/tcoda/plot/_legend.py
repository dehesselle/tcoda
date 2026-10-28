# SPDX-FileCopyrightText: 2025 David Fokkema
# SPDX-FileCopyrightText: 2026 René de Hesselle <dehesselle@web.de>
#
# SPDX-License-Identifier: MIT

"""The legend: one line per labelled dataset, kept in a corner of the plot.

The corner is the plot's CSS business (it aligns the legend's layer), and a
drag is just an `offset` on top. Letting go re-anchors the legend to whichever
corner it ended up nearest, so a resize keeps it where it was put relative to
that corner.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Literal

from textual.content import Content
from textual.geometry import Offset, Region
from textual.style import Style
from textual.widgets import Static

#: The corner of the data area the legend is kept in.
type LegendLocation = Literal["top-left", "top-right", "bottom-left", "bottom-right"]


class Legend(Static):
    ALLOW_SELECT = False

    def show(self, entries: Iterable[tuple[str, Style, str]]) -> None:
        """Show (marker, marker style, label) entries, one per line."""
        self.update(
            Content("\n").join(
                Content.assemble((marker, style), " ", label)
                for marker, style, label in entries
            )
        )

    def nearest_corner(self, area: Region) -> tuple[LegendLocation, Offset]:
        """The corner of `area` the legend is nearest, and its offset from
        where that corner would put it."""
        region = self.region
        margin = self.styles.margin
        left = region.x - (area.x + margin.left)
        right = region.right - (area.right - margin.right)
        top = region.y - (area.y + margin.top)
        bottom = region.bottom - (area.bottom - margin.bottom)
        horizontal, dx = ("left", left) if abs(left) <= abs(right) else ("right", right)
        vertical, dy = ("top", top) if abs(top) <= abs(bottom) else ("bottom", bottom)
        location: LegendLocation = f"{vertical}-{horizontal}"  # type: ignore[assignment]
        return location, Offset(dx, dy)
