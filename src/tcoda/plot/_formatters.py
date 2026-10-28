# SPDX-FileCopyrightText: 2025 David Fokkema
# SPDX-FileCopyrightText: 2026 René de Hesselle <dehesselle@web.de>
#
# SPDX-License-Identifier: MIT

"""Where an axis puts its ticks, and what it writes at them.

A formatter is handed the range an axis shows and answers with tick
positions; separately, it labels positions, which may be ticks it chose or
ones the app set. Both are plain data values, so a formatter for timestamps
still works in seconds.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from bisect import bisect_left
from collections.abc import Sequence
from datetime import UTC, datetime, tzinfo
from math import ceil, floor, log10
from typing import ClassVar

NICE_INTERVALS = [1.0, 2.0, 5.0, 10.0]


def nice_ticks(low: float, high: float, max_ticks: int = 8) -> list[float]:
    """Ticks between `low` and `high` at 1, 2 or 5 times a power of ten apart.

    About five ticks; never more than `max_ticks` intervals.
    """
    delta = high - low
    tick_spacing = delta / 5
    power = floor(log10(tick_spacing)) if tick_spacing > 0 else 0
    approx_interval = tick_spacing / 10**power

    idx = bisect_left(NICE_INTERVALS, approx_interval)
    interval = (NICE_INTERVALS[idx - 1] if idx > 0 else NICE_INTERVALS[0]) * 10**power
    if delta // interval > max_ticks:
        interval = NICE_INTERVALS[idx] * 10**power
    return arange(ceil(low / interval) * interval, high + interval / 2, interval)


def arange(start: float, stop: float, step: float) -> list[float]:
    """Evenly spaced values in the half-open interval [start, stop)."""
    count = max(0, ceil((stop - start) / step))
    return [start + i * step for i in range(count)]


def decimals_for(ticks: Sequence[float]) -> int:
    """Decimal places that tell neighbouring ticks apart: none for a spacing
    of 1 or more, one for 0.1, and so on."""
    if len(ticks) < 2 or (spacing := abs(ticks[1] - ticks[0])) == 0:
        return 0
    return max(0, -floor(log10(spacing)))


class AxisFormatter(ABC):
    """Chooses an axis's ticks and labels them.

    Subclass it for a kind of data the shipped formatters do not cover; only
    `get_ticks` and `get_labels` need writing.
    """

    @abstractmethod
    def get_ticks(self, low: float, high: float, max_ticks: int = 8) -> list[float]:
        """Tick positions for an axis showing `low` to `high`."""

    @abstractmethod
    def get_labels(self, ticks: Sequence[float]) -> list[str]:
        """A label for each of `ticks`, which need not be ones this formatter
        chose."""

    def get_ticks_and_labels(
        self, low: float, high: float, max_ticks: int = 8
    ) -> tuple[list[float], list[str]]:
        """`get_ticks`, then `get_labels` for them."""
        ticks = self.get_ticks(low, high, max_ticks)
        return ticks, self.get_labels(ticks)


class NumericFormatter(AxisFormatter):
    """Plain numbers, at nice intervals (1, 2, 5, 10, 20, ...).

    Labels get as many decimals as the spacing between the first two ticks
    needs.
    """

    def get_ticks(self, low: float, high: float, max_ticks: int = 8) -> list[float]:
        return nice_ticks(low, high, max_ticks)

    def get_labels(self, ticks: Sequence[float]) -> list[str]:
        decimals = decimals_for(ticks)
        return [f"{tick:.{decimals}f}" for tick in ticks]


class CategoricalFormatter(AxisFormatter):
    """Names at the whole numbers 1, 2, 3, ...

    `Plot.bar` sets this up by itself when given names instead of numbers.
    """

    def __init__(self, categories: Sequence[str]) -> None:
        """
        Args:
            categories: The names, for positions 1, 2, 3, ... in order.
        """
        self.categories = list(categories)

    def get_ticks(self, low: float, high: float, max_ticks: int = 8) -> list[float]:
        """Every category; the range and `max_ticks` play no part."""
        return [float(tick) for tick in range(1, len(self.categories) + 1)]

    def get_labels(self, ticks: Sequence[float]) -> list[str]:
        """The category nearest each tick, or nothing between categories."""
        labels = []
        for tick in ticks:
            index = round(tick) - 1
            labels.append(
                self.categories[index] if 0 <= index < len(self.categories) else ""
            )
        return labels


def _largest_unit[Unit](
    units: Sequence[tuple[Unit, float]], span: float, at_least: float
) -> tuple[Unit, float]:
    """The largest unit `span` covers at least `at_least` of, else the smallest."""
    for unit in units:
        if span >= unit[1] * at_least:
            return unit
    return units[-1]


class DurationFormatter(AxisFormatter):
    """Seconds, labelled in whichever unit suits the range: s, min, h, d, mo or y.

    A unit is chosen once the range spans at least half of one, so labels run
    from 0.5 of a unit up to just under half the next one up (``0.5h`` to
    ``11.5h``, then days).
    """

    #: Each unit and its length in seconds, largest first.
    UNITS: ClassVar[list[tuple[str, float]]] = [
        ("y", 365.25 * 24 * 3600),  # Julian year, leap days averaged in
        ("mo", 30.44 * 24 * 3600),  # average month
        ("d", 24 * 3600),
        ("h", 3600),
        ("min", 60),
        ("s", 1),
    ]

    def get_ticks(self, low: float, high: float, max_ticks: int = 8) -> list[float]:
        """Nice intervals in the chosen unit, returned in seconds."""
        _, size = _largest_unit(self.UNITS, high - low, 0.5)
        return [tick * size for tick in nice_ticks(low / size, high / size, max_ticks)]

    def get_labels(self, ticks: Sequence[float]) -> list[str]:
        """Labels in the unit that suits the ticks' own span."""
        if not ticks:
            return []
        name, size = _largest_unit(self.UNITS, max(ticks) - min(ticks), 0.5)
        in_unit = [tick / size for tick in ticks]
        decimals = decimals_for(in_unit)
        return [f"{tick:.{decimals}f}{name}" for tick in in_unit]


class DateTimeFormatter(AxisFormatter):
    """Unix timestamps, labelled as dates and times.

    Ticks fall on calendar boundaries: midnight, the hour, the first of the
    month, ... A unit is chosen once the range spans two of it, and ticks are
    at least one of it apart, so no two fall on the same boundary.
    """

    #: Each unit and its (average) length in seconds, largest first.
    UNITS: ClassVar[list[tuple[str, float]]] = [
        ("years", 365.25 * 24 * 3600),
        ("months", 30.44 * 24 * 3600),
        ("days", 24 * 3600),
        ("hours", 3600),
        ("minutes", 60),
        ("seconds", 1),
    ]

    def __init__(self, tz: tzinfo | None = None) -> None:
        """
        Args:
            tz: The time zone dates and times are shown in. Defaults to UTC.
        """
        self.tz = tz if tz is not None else UTC

    def _truncate(self, timestamp: float, unit: str) -> float:
        """The start of the `unit` that `timestamp` falls in."""
        dt = datetime.fromtimestamp(timestamp, tz=self.tz)
        match unit:
            case "years":
                dt = dt.replace(month=1, day=1, hour=0, minute=0, second=0)
            case "months":
                dt = dt.replace(day=1, hour=0, minute=0, second=0)
            case "days":
                dt = dt.replace(hour=0, minute=0, second=0)
            case "hours":
                dt = dt.replace(minute=0, second=0)
            case "minutes":
                dt = dt.replace(second=0)
        return dt.replace(microsecond=0).timestamp()

    def get_ticks(self, low: float, high: float, max_ticks: int = 8) -> list[float]:
        name, size = _largest_unit(self.UNITS, high - low, 2)
        in_unit = nice_ticks(low / size, high / size, max_ticks)
        if len(in_unit) >= 2 and in_unit[1] - in_unit[0] < 1:
            # Truncating ticks less than a unit apart would stack them up on
            # the same boundary; one unit apart is as fine as this unit goes.
            in_unit = arange(ceil(low / size), high / size + 0.5, 1.0)
        # Months and years vary in length, so even a unit apart, two ticks
        # can truncate to the same boundary; keep the first.
        return list(dict.fromkeys(self._truncate(t * size, name) for t in in_unit))

    def get_labels(self, ticks: Sequence[float]) -> list[str]:
        """Labels as precise as the ticks' own span calls for; the date is
        only repeated on an hourly axis when it changes."""
        if not ticks:
            return []
        unit, _ = _largest_unit(self.UNITS, max(ticks) - min(ticks), 2)
        labels = []
        previous_date = None
        for tick in ticks:
            dt = datetime.fromtimestamp(tick, tz=self.tz)
            match unit:
                case "years":
                    label = dt.strftime("%Y")
                case "months":
                    label = dt.strftime("%b %Y")
                case "days":
                    label = dt.strftime("%b %d, %Y")
                case "hours" if dt.date() != previous_date:
                    label = dt.strftime("%b %d, %H:%M")
                case "hours" | "minutes":
                    label = dt.strftime("%H:%M")
                case _:
                    label = dt.strftime("%H:%M:%S")
            previous_date = dt.date()
            labels.append(label)
        return labels
