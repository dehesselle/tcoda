# SPDX-FileCopyrightText: 2025 David Fokkema
# SPDX-FileCopyrightText: 2026 René de Hesselle <dehesselle@web.de>
#
# SPDX-License-Identifier: MIT

"""Drawing with more than one dot per cell.

Each mode splits a cell into a grid of sub-cells and has a glyph for every
combination of them being lit. A combination is a bitmask: bit
``row * columns + column`` is set when that sub-cell is lit, so the glyph
tables below are indexed by it directly.
"""

from __future__ import annotations

from typing import Literal

#: How a dataset is drawn when it is not drawn with full cells.
type HiResMode = Literal["halfblock", "quadrant", "braille"]

#: Sub-cells per cell, as (columns, rows).
CELL_GRID: dict[HiResMode, tuple[int, int]] = {
    "halfblock": (1, 2),
    "quadrant": (2, 2),
    "braille": (2, 4),
}

# Braille numbers its dots down the left column, then down the right one, and
# the bottom row (dots 7 and 8) was added last; this is each sub-cell's dot,
# in bitmask order.
_BRAILLE_DOTS = (0x01, 0x08, 0x02, 0x10, 0x04, 0x20, 0x40, 0x80)

#: The glyph for each bitmask; the empty mask has none.
GLYPHS: dict[HiResMode, tuple[str, ...]] = {
    "halfblock": ("", "▀", "▄", "█"),
    "quadrant": ("", *"▘▝▀▖▌▞▛▗▚▐▜▄▙▟█"),
    "braille": (
        "",
        *(
            chr(
                0x2800
                + sum(dot for bit, dot in enumerate(_BRAILLE_DOTS) if mask >> bit & 1)
            )
            for mask in range(1, 256)
        ),
    ),
}
