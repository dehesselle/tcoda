# SPDX-FileCopyrightText: 2025 David Fokkema
# SPDX-FileCopyrightText: 2026 René de Hesselle <dehesselle@web.de>
#
# SPDX-License-Identifier: MIT

"""A grid of cells to draw on, one character and one style per cell.

Coordinates come in two kinds. A *cell* is an ``(int, int)`` position. A
*point* is a ``(float, float)`` position in the same units, so ``(2.5, 0.0)``
is halfway across the third cell; points are what the high-resolution modes
draw, lighting whichever sub-cell they fall in.

Nothing here knows about plots. The canvas is drawn on in one go and then
refreshed once: every drawing call writes to the buffer only, and the owner
calls `refresh()` when it is done.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from itertools import pairwise
from math import ceil, floor

from rich.segment import Segment
from rich.style import Style
from textual import events
from textual.css.types import AlignHorizontal
from textual.message import Message
from textual.strip import Strip
from textual.widget import Widget

from tcoda.plot._hires import CELL_GRID, GLYPHS, HiResMode

#: Which arms of a box-drawing character are present, as (top, right, bottom,
#: left); 2 is a heavy arm, 0 none.
type Quad = tuple[int, int, int, int]

# Only heavy lines are drawn, so these are all the glyphs there can be.
_HEAVY_BOX: dict[Quad, str] = {
    (0, 2, 0, 2): "━",
    (2, 0, 2, 0): "┃",
    (0, 2, 2, 0): "┏",
    (0, 0, 2, 2): "┓",
    (2, 2, 0, 0): "┗",
    (2, 0, 0, 2): "┛",
    (2, 2, 2, 0): "┣",
    (2, 0, 2, 2): "┫",
    (0, 2, 2, 2): "┳",
    (2, 2, 0, 2): "┻",
    (2, 2, 2, 2): "╋",
    (0, 2, 0, 0): "╺",
    (0, 0, 0, 2): "╸",
    (2, 0, 0, 0): "╹",
    (0, 0, 2, 0): "╻",
}


class Canvas(Widget):
    """Cells to draw on, sized to the widget."""

    class Resized(Message):
        """The canvas changed size, so what was drawn on it is gone."""

        def __init__(self, canvas: Canvas) -> None:
            self.canvas = canvas
            super().__init__()

        @property
        def control(self) -> Canvas:
            return self.canvas

    def __init__(self, *, id: str | None = None) -> None:
        super().__init__(id=id)
        self._width = 0
        self._height = 0
        self._chars: list[list[str]] = []
        self._styles: list[list[Style | None]] = []
        #: Box-drawing arms per cell, merged so crossing lines join up.
        self._boxes: dict[tuple[int, int], Quad] = {}

    def _on_resize(self, event: events.Resize) -> None:
        self.reset()
        self.post_message(self.Resized(self))

    def reset(self) -> None:
        """Blank every cell, at the widget's current size."""
        self._width, self._height = self.size
        self._chars = [[" "] * self._width for _ in range(self._height)]
        self._styles = [[None] * self._width for _ in range(self._height)]
        self._boxes = {}

    def render_line(self, y: int) -> Strip:
        if y >= self._height:
            return Strip.blank(self.size.width, self.rich_style)
        base_style = self.rich_style
        chars = self._chars[y]
        if all(char == " " for char in chars):
            return Strip.blank(self._width, base_style)

        # One segment per run of cells sharing a style.
        segments: list[Segment] = []
        run_style = self._styles[y][0]
        run = ""
        for char, style in zip(chars, self._styles[y]):
            if style is not run_style and style != run_style:
                segments.append(Segment(run, base_style + run_style))
                run_style, run = style, ""
            run += char
        segments.append(Segment(run, base_style + run_style))
        return Strip(segments).simplify()

    # ------------------------------------------------------------ cells

    def contains(self, x: int, y: int) -> bool:
        return 0 <= x < self._width and 0 <= y < self._height

    def get_cell(self, x: int, y: int) -> str:
        return self._chars[y][x]

    def set_cell(self, x: int, y: int, char: str, style: Style) -> None:
        """Draw one character; a cell off the canvas is ignored."""
        if self.contains(x, y):
            self._chars[y][x] = char
            self._styles[y][x] = style

    def add_box(self, x: int, y: int, quad: Quad, style: Style) -> None:
        """Add heavy box-drawing arms to a cell, joining any already there."""
        if not self.contains(x, y):
            return
        if (current := self._boxes.get((x, y))) is not None:
            quad = tuple(map(max, current, quad))  # type: ignore[assignment]
        self._boxes[x, y] = quad
        self.set_cell(x, y, _HEAVY_BOX[quad], style)

    def draw_box(self, x0: int, y0: int, x1: int, y1: int, style: Style) -> None:
        """Draw a heavy frame with its corners at (x0, y0) and (x1, y1)."""
        for x in range(x0 + 1, x1):
            self.add_box(x, y0, (0, 2, 0, 2), style)
            self.add_box(x, y1, (0, 2, 0, 2), style)
        for y in range(y0 + 1, y1):
            self.add_box(x0, y, (2, 0, 2, 0), style)
            self.add_box(x1, y, (2, 0, 2, 0), style)
        self.add_box(x0, y0, (0, 2, 2, 0), style)
        self.add_box(x1, y0, (0, 0, 2, 2), style)
        self.add_box(x0, y1, (2, 2, 0, 0), style)
        self.add_box(x1, y1, (2, 0, 0, 2), style)

    def draw_line(
        self, x0: int, y0: int, x1: int, y1: int, char: str, style: Style
    ) -> None:
        """Draw a line of cells between two cells, inclusive."""
        if (clipped := self._clip(x0, y0, x1, y1)) is None:
            return
        cx0, cy0, cx1, cy1 = (int(c) for c in clipped)
        for x, y in _line(cx0, cy0, cx1, cy1):
            self.set_cell(x, y, char, style)

    def fill_rect(
        self, x0: int, y0: int, x1: int, y1: int, char: str, style: Style
    ) -> None:
        """Fill the cells between two corner cells, inclusive."""
        x_start, x_end = sorted((x0, x1))
        y_start, y_end = sorted((y0, y1))
        x_start, y_start = max(x_start, 0), max(y_start, 0)
        x_end, y_end = min(x_end, self._width - 1), min(y_end, self._height - 1)
        if x_start > x_end or y_start > y_end:
            return
        width = x_end - x_start + 1
        for y in range(y_start, y_end + 1):
            self._chars[y][x_start : x_end + 1] = [char] * width
            self._styles[y][x_start : x_end + 1] = [style] * width

    def write_text(
        self,
        x: int,
        y: int,
        text: str,
        style: Style,
        align: AlignHorizontal = "left",
    ) -> None:
        """Write plain text, aligned on cell `x`, cropped to the canvas.

        Centred text of even length sits one cell right of centre.
        """
        if not text or not 0 <= y < self._height:
            return
        if align == "right":
            x -= len(text) - 1
        elif align == "center":
            half, odd = divmod(len(text), 2)
            x -= half - (not odd)
        for offset, char in enumerate(text):
            self.set_cell(x + offset, y, char, style)

    # ----------------------------------------------------------- points

    def set_points(
        self, points: Iterable[tuple[float, float]], hires_mode: HiResMode, style: Style
    ) -> None:
        """Light the sub-cell each point falls in.

        A cell takes the glyph for the sub-cells lit by *this* call, replacing
        whatever it showed before.
        """
        columns, rows = CELL_GRID[hires_mode]
        glyphs = GLYPHS[hires_mode]
        masks: dict[tuple[int, int], int] = {}
        for x, y in points:
            if not self.contains(floor(x), floor(y)):
                continue
            sub_x, sub_y = floor(x * columns), floor(y * rows)
            cell = (sub_x // columns, sub_y // rows)
            bit = (sub_y % rows) * columns + sub_x % columns
            masks[cell] = masks.get(cell, 0) | 1 << bit
        for (x, y), mask in masks.items():
            if glyph := glyphs[mask]:
                self.set_cell(x, y, glyph, style)

    def draw_polyline(
        self,
        points: Sequence[tuple[float, float]],
        hires_mode: HiResMode,
        style: Style,
    ) -> None:
        """Draw lines between consecutive points, at sub-cell resolution."""
        columns, rows = CELL_GRID[hires_mode]
        lit: list[tuple[float, float]] = []
        for (x0, y0), (x1, y1) in pairwise(points):
            if (clipped := self._clip(x0, y0, x1, y1)) is None:
                continue
            cx0, cy0, cx1, cy1 = clipped
            lit.extend(
                (sub_x / columns, sub_y / rows)
                for sub_x, sub_y in _line(
                    floor(cx0 * columns),
                    floor(cy0 * rows),
                    floor(cx1 * columns),
                    floor(cy1 * rows),
                )
            )
        self.set_points(lit, hires_mode, style)

    def fill_rect_hires(
        self,
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        hires_mode: HiResMode,
        style: Style,
    ) -> None:
        """Fill the area between two corner points, at sub-cell resolution.

        Cells wholly inside are filled with full blocks; only the cells along
        a fractional edge are worked out sub-cell by sub-cell.
        """
        x_start, x_end = sorted((x0, x1))
        y_start, y_end = sorted((y0, y1))
        if x_start == x_end and y_start == y_end:
            self.set_points([(x_start, y_start)], hires_mode, style)
            return

        columns, rows = CELL_GRID[hires_mode]
        # Snap to the sub-cell grid.
        x_start = round(x_start * columns) / columns
        x_end = round(x_end * columns) / columns
        y_start = round(y_start * rows) / rows
        y_end = round(y_end * rows) / rows

        def area(ax0: float, ay0: float, ax1: float, ay1: float) -> list:
            if ax0 >= ax1 or ay0 >= ay1:
                return []
            width, height = ax1 - ax0, ay1 - ay0
            x_steps = max(1, ceil(width * columns))
            y_steps = max(1, ceil(height * rows))
            return [
                (ax0 + (j / x_steps) * width, ay0 + (i / y_steps) * height)
                for i in range(y_steps + 1)
                for j in range(x_steps + 1)
            ]

        # The cells wholly inside.
        ix_start, iy_start = ceil(x_start), ceil(y_start)
        ix_end, iy_end = floor(x_end), floor(y_end)

        if ix_start >= ix_end or iy_start >= iy_end:
            # Too thin to have an inside: all edge.
            self.set_points(area(x_start, y_start, x_end, y_end), hires_mode, style)
            return

        self.fill_rect(
            ix_start, iy_start, ix_end - 1, iy_end - 1, GLYPHS[hires_mode][-1], style
        )
        # The edges, laid out as
        #   [      top      ]
        #   [L]  [inside]  [R]
        #   [    bottom     ]
        # each stopping just short of the next cell, which belongs to its
        # neighbour.
        epsilon = 1e-9
        edges: list[tuple[float, float]] = []
        if y_start < iy_start:
            edges += area(x_start, y_start, x_end - epsilon, iy_start - epsilon)
        if y_end > iy_end:
            edges += area(x_start, iy_end, x_end - epsilon, y_end - epsilon)
        if x_start < ix_start:
            edges += area(x_start, iy_start, ix_start - epsilon, iy_end - epsilon)
        if x_end > ix_end:
            edges += area(ix_end, iy_start, x_end - epsilon, iy_end - epsilon)
        if edges:
            self.set_points(edges, hires_mode, style)

    # ---------------------------------------------------------- helpers

    def _clip(
        self, x0: float, y0: float, x1: float, y1: float
    ) -> tuple[float, float, float, float] | None:
        """Clip a line to the canvas (Cohen-Sutherland), or None if it misses."""
        inside, left, right, below, above = 0, 1, 2, 4, 8
        x_min, y_min = 0, 0
        x_max, y_max = self._width - 1, self._height - 1

        def outcode(x: float, y: float) -> int:
            code = inside
            if x < x_min:
                code |= left
            elif x > x_max:
                code |= right
            if y < y_min:
                code |= below
            elif y > y_max:
                code |= above
            return code

        code0, code1 = outcode(x0, y0), outcode(x1, y1)
        while True:
            if not code0 | code1:
                return x0, y0, x1, y1
            if code0 & code1:
                return None
            out = code0 or code1
            if out & above:
                x = x0 + (x1 - x0) * (y_max - y0) / (y1 - y0) if y1 != y0 else x0
                y = y_max
            elif out & below:
                x = x0 + (x1 - x0) * (y_min - y0) / (y1 - y0) if y1 != y0 else x0
                y = y_min
            elif out & right:
                y = y0 + (y1 - y0) * (x_max - x0) / (x1 - x0) if x1 != x0 else y0
                x = x_max
            else:
                y = y0 + (y1 - y0) * (x_min - x0) / (x1 - x0) if x1 != x0 else y0
                x = x_min
            if out == code0:
                x0, y0 = x, y
                code0 = outcode(x0, y0)
            else:
                x1, y1 = x, y
                code1 = outcode(x1, y1)


def _line(x0: int, y0: int, x1: int, y1: int) -> list[tuple[int, int]]:
    """The cells on a line between two cells, inclusive (Bresenham)."""
    if y0 == y1:
        return [(x, y0) for x in range(min(x0, x1), max(x0, x1) + 1)]
    if x0 == x1:
        return [(x0, y) for y in range(min(y0, y1), max(y0, y1) + 1)]

    dx, sx = abs(x1 - x0), 1 if x0 < x1 else -1
    dy, sy = -abs(y1 - y0), 1 if y0 < y1 else -1
    error = dx + dy
    x, y = x0, y0
    cells = [(x, y)]
    while (x, y) != (x1, y1):
        doubled = 2 * error
        if doubled >= dy:
            if x == x1:
                break
            error += dy
            x += sx
        if doubled <= dx:
            if y == y1:
                break
            error += dx
            y += sy
        cells.append((x, y))
    return cells
