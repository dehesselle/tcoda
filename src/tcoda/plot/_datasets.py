# SPDX-FileCopyrightText: 2025 David Fokkema
# SPDX-FileCopyrightText: 2026 René de Hesselle <dehesselle@web.de>
#
# SPDX-License-Identifier: MIT

"""What a plot holds: one dataset per call to `Plot.plot`, `Plot.bar`, ...

Each kind draws itself. The plot only works out the viewport and the axes,
then hands every dataset the canvas in the order they were added.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from itertools import pairwise
from math import isfinite

from rich.style import Style

from tcoda.plot._canvas import Canvas, Quad
from tcoda.plot._hires import HiResMode
from tcoda.plot._viewport import Range, Viewport

#: Turns a dataset's style, which may name theme variables, into one to draw.
type Paint = Callable[[str], Style]

#: A legend entry's marker for a line, by mode; markers are three cells wide.
_LEGEND_LINE: dict[HiResMode | None, str] = {
    None: "███",
    "braille": "⠒⠒⠒",
    "halfblock": "▀▀▀",
    "quadrant": "▀▀▀",
}
#: A single dot in each high-resolution mode, for scatter legend entries.
_LEGEND_DOT: dict[HiResMode, str] = {
    "braille": "⠂",
    "halfblock": "▀",
    "quadrant": "▘",
}


@dataclass(kw_only=True)
class Dataset(ABC):
    #: A style such as ``"bold red"``, which may use theme variables
    #: (``"$accent"``); resolved each time the plot is drawn.
    style: str
    #: Shown in the legend; a dataset without one is left out of it.
    label: str | None = None
    #: How to draw it, or None for full cells.
    hires_mode: HiResMode | None = None

    @abstractmethod
    def extent(
        self, x_range: Range | None = None
    ) -> tuple[Sequence[float], Sequence[float]]:
        """The x and y values an automatic range has to include.

        With `x_range`, the y values are only those of what lies in it.
        """

    @abstractmethod
    def draw(self, canvas: Canvas, viewport: Viewport, paint: Paint) -> None:
        """Draw on the canvas. The frame is drawn afterwards, on top."""

    @abstractmethod
    def legend_marker(self) -> str:
        """Three cells that stand for this dataset in the legend."""

    def frame_marks(self, viewport: Viewport) -> Iterable[tuple[int, int, Quad]]:
        """Box-drawing arms this dataset adds to the frame, as (x, y, quad)."""
        return ()


@dataclass(kw_only=True)
class Line(Dataset):
    x: list[float]
    y: list[float]

    def extent(
        self, x_range: Range | None = None
    ) -> tuple[Sequence[float], Sequence[float]]:
        return self.x, [y for x, y in zip(self.x, self.y) if _within(x, x_range)]

    def draw(self, canvas: Canvas, viewport: Viewport, paint: Paint) -> None:
        style = paint(self.style)
        if self.hires_mode:
            points = [viewport.to_point(x, y) for x, y in zip(self.x, self.y)]
            canvas.draw_polyline(points, self.hires_mode, style)
        else:
            cells = [viewport.to_cell(x, y) for x, y in zip(self.x, self.y)]
            for start, end in pairwise(cells):
                canvas.draw_line(*start, *end, "█", style)

    def legend_marker(self) -> str:
        return _LEGEND_LINE[self.hires_mode]


@dataclass(kw_only=True)
class Scatter(Dataset):
    x: list[float]
    y: list[float]
    #: The character drawn at each point; high-resolution modes draw a dot.
    marker: str = "o"

    def extent(
        self, x_range: Range | None = None
    ) -> tuple[Sequence[float], Sequence[float]]:
        return self.x, [y for x, y in zip(self.x, self.y) if _within(x, x_range)]

    def draw(self, canvas: Canvas, viewport: Viewport, paint: Paint) -> None:
        style = paint(self.style)
        if self.hires_mode:
            points = [viewport.to_point(x, y) for x, y in zip(self.x, self.y)]
            canvas.set_points(points, self.hires_mode, style)
        else:
            for x, y in zip(self.x, self.y):
                canvas.set_cell(*viewport.to_cell(x, y), self.marker, style)

    def legend_marker(self) -> str:
        if self.hires_mode:
            return _LEGEND_DOT[self.hires_mode].center(3)
        return self.marker.center(3)


@dataclass(kw_only=True)
class ErrorBars(Scatter):
    #: Per point; 0 draws no bar, a non-finite error none either.
    xerr: list[float]
    yerr: list[float]
    #: None marks each point with ┼ where both bars are drawn, · otherwise.
    marker: str | None = None  # type: ignore[assignment]

    def extent(
        self, x_range: Range | None = None
    ) -> tuple[Sequence[float], Sequence[float]]:
        """The points and the ends of their bars."""
        xs, ys = [], []
        for x, y, xerr, yerr in zip(self.x, self.y, self.xerr, self.yerr):
            xs.extend(_spread(x, xerr))
            if _within(x, x_range):
                ys.extend(_spread(y, yerr))
        return xs, ys

    def draw(self, canvas: Canvas, viewport: Viewport, paint: Paint) -> None:
        """Draw the bars at half-cell resolution, then the points on top.

        A bar too short to show leaves just the point's marker.
        """
        style = paint(self.style)
        origin_x, origin_y = viewport.to_point(0.0, 0.0)
        markers = []
        for x, y, xerr, yerr in zip(self.x, self.y, self.xerr, self.yerr):
            column, row = viewport.to_cell(x, y)

            has_x_bar = False
            if isfinite(xerr):
                end_x, _ = viewport.to_point(xerr, 0.0)
                has_x_bar, cells, half = _bar_lengths(end_x - origin_x)
                canvas.draw_line(column - cells, row, column + cells, row, "─", style)
                if half:
                    canvas.set_cell(column - cells - 1, row, "╶", style)
                    canvas.set_cell(column + cells + 1, row, "╴", style)

            has_y_bar = False
            if isfinite(yerr):
                _, end_y = viewport.to_point(0.0, yerr)
                has_y_bar, cells, half = _bar_lengths(origin_y - end_y)
                canvas.draw_line(column, row - cells, column, row + cells, "│", style)
                if half:
                    canvas.set_cell(column, row - cells - 1, "╷", style)
                    canvas.set_cell(column, row + cells + 1, "╵", style)

            marker = self.marker or ("┼" if has_x_bar and has_y_bar else "·")
            markers.append((column, row, marker))

        if self.hires_mode:
            super().draw(canvas, viewport, paint)
        else:
            for column, row, marker in markers:
                canvas.set_cell(column, row, marker, style)

    def legend_marker(self) -> str:
        if self.hires_mode:
            return _LEGEND_DOT[self.hires_mode].center(3)
        return (self.marker or "┼").center(3)


@dataclass(kw_only=True)
class Bars(Dataset):
    #: The centre of each bar.
    x: list[float]
    #: The height of each bar; bars rise (or fall) from 0.
    y: list[float]
    #: The width of each bar, in data units.
    width: list[float]
    #: A style per bar, overriding `style`, which the legend shows.
    bar_styles: list[str] | None = None

    def extent(
        self, x_range: Range | None = None
    ) -> tuple[Sequence[float], Sequence[float]]:
        """Both sides of every bar; 0 and the height of every bar any part
        of which is in `x_range`."""
        xs, ys = [], []
        for x, y, width in zip(self.x, self.y, self.width):
            left, right = x - width / 2, x + width / 2
            xs += [left, right]
            if x_range is None or (left <= x_range[1] and right >= x_range[0]):
                ys += [0.0, y]
        return xs, ys

    def draw(self, canvas: Canvas, viewport: Viewport, paint: Paint) -> None:
        styles = self.bar_styles or [self.style] * len(self.x)
        for x, y, width, style in zip(self.x, self.y, self.width, styles):
            top_left = (x - width / 2, y)
            bottom_right = (x + width / 2, 0.0)
            if self.hires_mode:
                canvas.fill_rect_hires(
                    *viewport.to_point(*top_left),
                    *viewport.to_point(*bottom_right),
                    self.hires_mode,
                    paint(style),
                )
            else:
                canvas.fill_rect(
                    *viewport.to_cell(*top_left),
                    *viewport.to_cell(*bottom_right),
                    "█",
                    paint(style),
                )

    def legend_marker(self) -> str:
        return "███"


@dataclass(kw_only=True)
class VLine(Dataset):
    """A vertical line across the whole plot, joined to the frame."""

    x: float

    def extent(
        self, x_range: Range | None = None
    ) -> tuple[Sequence[float], Sequence[float]]:
        return [self.x], []

    def draw(self, canvas: Canvas, viewport: Viewport, paint: Paint) -> None:
        column, _ = viewport.to_cell(self.x, 0.0)
        region = viewport.region
        canvas.draw_line(
            column, region.y, column, region.bottom - 1, "│", paint(self.style)
        )

    def legend_marker(self) -> str:
        return "│".center(3)

    def frame_marks(self, viewport: Viewport) -> Iterable[tuple[int, int, Quad]]:
        column, _ = viewport.to_cell(self.x, 0.0)
        yield column, 0, (0, 0, 2, 0)
        yield column, viewport.region.bottom, (2, 0, 0, 0)


def _within(x: float, x_range: Range | None) -> bool:
    return x_range is None or x_range[0] <= x <= x_range[1]


def _spread(value: float, error: float) -> tuple[float, ...]:
    """Where a point's error bar ends, or just the point without one."""
    return (value - error, value + error) if isfinite(error) else (value,)


def _bar_lengths(length: float) -> tuple[bool, int, bool]:
    """Split an error bar's length, in cells, into what to draw of it.

    Returns whether there is a bar at all, how many full cells it reaches out
    from the point, and whether it ends in half a cell beyond those.
    """
    halves = round(length * 2)
    if halves < 1:
        return False, 0, False
    cells, half = divmod(halves - 1, 2)
    return True, cells, bool(half)


def drop_non_finite(
    x: Iterable[float], y: Iterable[float], *others: Iterable[float]
) -> tuple[list[float], ...]:
    """Drop the data points where x or y is NaN or infinite.

    Further iterables (error values, say) are filtered along with x and y so
    they stay with their points; their own values are not checked.

    Raises:
        ValueError: If the iterables have different lengths.
    """
    columns: tuple[list[float], ...] = tuple([] for _ in range(2 + len(others)))
    for values in zip(x, y, *others, strict=True):
        if isfinite(values[0]) and isfinite(values[1]):
            for column, value in zip(columns, values):
                column.append(float(value))
    return columns
