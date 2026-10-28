# SPDX-FileCopyrightText: 2025 David Fokkema
# SPDX-FileCopyrightText: 2026 René de Hesselle <dehesselle@web.de>
#
# SPDX-License-Identifier: MIT

"""Where data lands on the canvas, and how zooming and panning move it."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil, floor

from textual.geometry import Region

type Range = tuple[float, float]


@dataclass(frozen=True, slots=True)
class Viewport:
    """The data ranges shown, and the canvas region they are shown in."""

    x_range: Range
    y_range: Range
    #: The cells data is drawn in. The axes run along its edges, so a value at
    #: the top or right end of a range lands on the frame.
    region: Region

    def to_cell(self, x: float, y: float) -> tuple[int, int]:
        """The cell a data point is drawn in."""
        region = self.region
        return (
            floor(_rescale(x, self.x_range, (region.x, region.right))),
            # Rows count downwards.
            ceil(_rescale(y, self.y_range, (region.bottom - 1, region.y - 1))),
        )

    def to_point(self, x: float, y: float) -> tuple[float, float]:
        """Where a data point falls on the canvas, to a fraction of a cell."""
        region = self.region
        return (
            _rescale(x, self.x_range, (region.x, region.right)),
            _rescale(y, self.y_range, (region.bottom, region.y)),
        )

    def to_data(self, x: int, y: int) -> tuple[float, float]:
        """The data point at the centre of a cell."""
        region = self.region
        return (
            _rescale(x + 0.5, (region.x, region.right), self.x_range),
            _rescale(y + 0.5, (region.bottom, region.y), self.y_range),
        )

    def data_per_cell(self) -> tuple[float, float]:
        """How far one cell is in data units, across and up."""
        (x_min, x_max), (y_min, y_max) = self.x_range, self.y_range
        return (
            (x_max - x_min) / self.region.width,
            (y_max - y_min) / self.region.height,
        )


def zoom(range_: Range, centre: float, factor: float) -> Range:
    """Shrink a range towards `centre` (or grow it, for a negative factor).

    Each end moves to ``(end + factor * centre) / (1 + factor)``, which keeps
    `centre` where it is on screen.
    """
    low, high = range_
    return (low + factor * centre) / (1 + factor), (high + factor * centre) / (
        1 + factor
    )


def pan(range_: Range, delta: float) -> Range:
    """Shift a range by `delta`."""
    low, high = range_
    return low + delta, high + delta


#: The narrowest a range may be, relative to how far it is from zero: much
#: narrower, and neighbouring cells would map to the same float.
MIN_RELATIVE_SPAN = 1e-9
#: How far from zero a range may reach. Further, and mapping it onto cells
#: overflows a float.
MAX_MAGNITUDE = 1e300


def constrain(
    new: Range,
    old: Range,
    bounds: tuple[float | None, float | None],
    spans: tuple[float | None, float | None],
    anchor: float | None = None,
) -> Range:
    """Where zooming or panning from `old` to `new` may go.

    The span is kept between the shortest and longest of `spans`, around
    `anchor` (the point zoomed around), and the range is moved back inside
    `bounds`, or shrunk to them. Each limit only stops a range from getting
    worse: one that `old` is already past is relaxed to where `old` is.

    A range too wide or too far out for floats (see `MAX_MAGNITUDE`), or too
    narrow for them to tell its cells apart, is refused outright: the answer
    is `old`.
    """
    low, high = new
    old_low, old_high = old
    width, old_width = high - low, old_high - old_low
    magnitude = max(abs(low), abs(high))
    # NaN fails every comparison, so it is refused along with the rest.
    if not (MIN_RELATIVE_SPAN * magnitude < width and magnitude <= MAX_MAGNITUDE):
        return old

    shortest, longest = spans
    target = width
    if shortest is not None:
        target = max(target, min(shortest, old_width))
    if longest is not None:
        target = min(target, max(longest, old_width))
    if target != width:
        centre = (low + high) / 2 if anchor is None else anchor
        scale = target / width
        low, high = centre - (centre - low) * scale, centre + (high - centre) * scale

    first, last = bounds
    if first is not None:
        first = min(first, old_low)
    if last is not None:
        last = max(last, old_high)
    if first is not None and last is not None and high - low > last - first:
        return first, last
    if first is not None and low < first:
        low, high = first, high + first - low
    if last is not None and high > last:
        low, high = low - (high - last), last
    return low, high


def _rescale(value: float, source: Range, target: Range) -> float:
    """Map `value` linearly from the `source` range onto the `target` range."""
    (a, b), (a_target, b_target) = source, target
    return a_target + (value - a) * (b_target - a_target) / (b - a)
