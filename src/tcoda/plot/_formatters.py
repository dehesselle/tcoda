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

import time
from abc import ABC, abstractmethod
from calendar import timegm
from collections.abc import Iterator, Sequence
from datetime import UTC, datetime, timedelta, tzinfo
from itertools import pairwise
from math import ceil, floor, isfinite, log10
from typing import ClassVar, Literal

from tcoda.plot._viewport import Range

NICE_INTERVALS = [1.0, 2.0, 5.0, 10.0]


def nice_ticks(low: float, high: float, max_ticks: int = 8) -> list[float]:
    """Ticks between `low` and `high` at 1, 2 or 5 times a power of ten apart.

    As many as fit: the closest such spacing that makes at most `max_ticks`
    intervals.
    """
    delta = high - low
    if not isfinite(delta):
        return []
    if delta <= 0:
        return [low]
    max_ticks = max(1, max_ticks)
    power = floor(log10(delta / max_ticks))
    interval = next(
        step * 10**power
        for step in NICE_INTERVALS
        # A hair of slack, so 0 to 1 in five steps of 0.2 is five, not six.
        if delta / (step * 10**power) <= max_ticks * (1 + 1e-9)
    )
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
        """Tick positions for an axis showing `low` to `high`, at most
        `max_ticks` intervals apart from end to end."""

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

    def around(self, value: float) -> Range:
        """A range to show a single value in, when that is all there is.

        Half the value either side, or -1 to 1 around zero.
        """
        half = abs(value) / 2 or 1.0
        return value - half, value + half


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

    def around(self, value: float) -> Range:
        """Half a category either side."""
        return value - 0.5, value + 0.5


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


# ----------------------------------------------------------- dates and times

_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
_NAIVE_EPOCH = _EPOCH.replace(tzinfo=None)
#: The timestamps a date is shown for: what `datetime` holds, less a day at
#: either end so no time zone can push one past it.
TIMESTAMP_RANGE: Range = (
    (datetime(1, 1, 2, tzinfo=UTC) - _EPOCH).total_seconds(),
    (datetime(9999, 12, 30, tzinfo=UTC) - _EPOCH).total_seconds(),
)
#: Where every platform's `time.localtime` works (a 32-bit `time_t`, and a
#: day clear of either end of it for zones away from UTC).
_LOCALTIME_SAFE: tuple[int, int] = (86400, 2**31 - 86400)
#: No time zone is further than this from UTC (the furthest are 14 hours).
_MAX_OFFSET = 18 * 3600


def _local_offset(timestamp: float) -> int:
    """Seconds local time is ahead of UTC at `timestamp`.

    Outside what the platform converts (Windows refuses anything before
    1970), the offset of the nearest time it does.
    """
    second = floor(timestamp)
    try:
        # Not `tm_gmtoff`: Windows gets that wrong after 2038, while the
        # date and time it converts to are right.
        offset = timegm(time.localtime(second)) - second
    except (OSError, OverflowError, ValueError):
        offset = None
    if offset is None or abs(offset) > _MAX_OFFSET:
        low, high = _LOCALTIME_SAFE
        second = min(max(second, low), high)
        offset = timegm(time.localtime(second)) - second
    return offset


class _LocalTime(tzinfo):
    """The system's local time zone, as `time.localtime` knows it, daylight
    saving included, without the platform's limits on which years it takes."""

    def fromutc(self, dt: datetime) -> datetime:
        timestamp = (dt.replace(tzinfo=None) - _NAIVE_EPOCH).total_seconds()
        return dt + timedelta(seconds=_local_offset(timestamp))

    def utcoffset(self, dt: datetime | None) -> timedelta:
        if dt is None:
            return timedelta(seconds=_local_offset(time.time()))
        # A wall time's offset is that of the moment it names, which the
        # offset itself is needed to find; the second guess is right but
        # around a daylight-saving change.
        wall = (dt.replace(tzinfo=None) - _NAIVE_EPOCH).total_seconds()
        guess = wall - _local_offset(wall)
        return timedelta(seconds=_local_offset(wall - _local_offset(guess)))

    def dst(self, dt: datetime | None) -> timedelta | None:
        return None

    def tzname(self, dt: datetime | None) -> str | None:
        return None


LOCAL_TIME: tzinfo = _LocalTime()

type _Unit = Literal["seconds", "minutes", "hours", "days", "weeks", "months", "years"]

#: Every spacing a date axis's ticks may take, finest first: the unit, how
#: many of it, and the unit's (average) length in seconds.
_STEPS: list[tuple[_Unit, int, float]] = [
    *(("seconds", n, 1.0) for n in (1, 2, 5, 10, 15, 30)),
    *(("minutes", n, 60.0) for n in (1, 2, 5, 10, 15, 30)),
    *(("hours", n, 3600.0) for n in (1, 2, 3, 6, 12)),
    *(("days", n, 86400.0) for n in (1, 2)),
    ("weeks", 1, 7 * 86400.0),
    *(("months", n, 30.44 * 86400) for n in (1, 3, 6)),
]
_YEAR = 365.25 * 86400


class DateTimeFormatter(AxisFormatter):
    """Unix timestamps, labelled as dates and times.

    Ticks fall where a clock or calendar would put them: on the hour or every
    15 minutes, at midnight, on Mondays, on the first of the month or the
    quarter, on round years. Labels are short and say only what changes from
    tick to tick; the date (or the year) is added on the first tick and
    wherever it changes, and a tick on a boundary of it is labelled with it
    alone (``Nov 15`` rather than ``00:00``).

    Timestamps beyond what a date can hold (before year 1 or after 9999) get
    no ticks; nothing here raises, whatever range the axis is zoomed to.
    """

    def __init__(self, tz: tzinfo | None = None) -> None:
        """
        Args:
            tz: The time zone dates and times are shown in. Defaults to the
                system's local time.
        """
        self.tz = tz if tz is not None else LOCAL_TIME

    def around(self, value: float) -> Range:
        """An hour either side."""
        return value - 3600, value + 3600

    def get_ticks(self, low: float, high: float, max_ticks: int = 8) -> list[float]:
        first, last = TIMESTAMP_RANGE
        low, high = max(low, first), min(high, last)
        if not (isfinite(low) and isfinite(high)) or low > high:
            return []
        unit, count = _step(high - low, max(1, max_ticks))
        start, end = self._wall(low), self._wall(high)
        ticks: list[float] = []
        for wall in _walls(_floor(start, unit, count), unit, count):
            if wall > end:
                break
            tick = self._timestamp(wall)
            # A wall time that a daylight-saving change skips or repeats can
            # land on the same moment as its neighbour.
            if low <= tick <= high and (not ticks or tick > ticks[-1]):
                ticks.append(tick)
        return ticks

    def get_labels(self, ticks: Sequence[float]) -> list[str]:
        if not ticks:
            return []
        first, last = TIMESTAMP_RANGE
        walls = [self._wall(tick) if first <= tick <= last else None for tick in ticks]
        spacings = [abs(b - a) for a, b in pairwise(ticks) if a != b]
        # A lone tick says no more than its minute.
        unit = _unit_for(min(spacings, default=60.0))
        labels = []
        previous: datetime | None = None
        for wall in walls:
            labels.append("" if wall is None else _label(wall, previous, unit))
            previous = wall or previous
        return labels

    def _wall(self, timestamp: float) -> datetime:
        """The (naive) date and time on the wall clock at `timestamp`."""
        utc = _EPOCH + timedelta(seconds=timestamp)
        return utc.astimezone(self.tz).replace(tzinfo=None)

    def _timestamp(self, wall: datetime) -> float:
        return wall.replace(tzinfo=self.tz).timestamp()


def _step(span: float, max_ticks: int) -> tuple[_Unit, int]:
    """The finest spacing that fits `span` into at most `max_ticks` intervals."""
    for unit, count, size in _STEPS:
        if span <= count * size * max_ticks:
            return unit, count
    years = span / _YEAR / max_ticks
    power = 10 ** max(0, floor(log10(years))) if years > 0 else 1
    count = next(step * power for step in NICE_INTERVALS if step * power >= years)
    return "years", int(count)


def _floor(wall: datetime, unit: _Unit, count: int) -> datetime:
    """The last tick at or before `wall`, for ticks `count` units apart."""
    match unit:
        case "seconds":
            return wall.replace(second=wall.second // count * count, microsecond=0)
        case "minutes":
            return wall.replace(
                minute=wall.minute // count * count, second=0, microsecond=0
            )
        case "hours":
            return wall.replace(
                hour=wall.hour // count * count, minute=0, second=0, microsecond=0
            )
    day = wall.replace(hour=0, minute=0, second=0, microsecond=0)
    match unit:
        case "days":
            # Counted from the first of the month, as a calendar would.
            return day.replace(day=(day.day - 1) // count * count + 1)
        case "weeks":
            return day - timedelta(days=day.weekday())
        case "months":
            return day.replace(month=(day.month - 1) // count * count + 1, day=1)
    # Round multiples of `count`; there was no year 0 to start from.
    return day.replace(year=day.year // count * count or count, month=1, day=1)


def _walls(wall: datetime, unit: _Unit, count: int) -> Iterator[datetime]:
    """Wall times `count` units apart from `wall` on, until a date runs out."""
    while True:
        yield wall
        try:
            match unit:
                case "seconds" | "minutes" | "hours" | "weeks":
                    wall += timedelta(**{unit: count})
                case "days":
                    following = wall + timedelta(days=count)
                    # A new month starts the count again from its first.
                    wall = (
                        following
                        if following.month == wall.month
                        else following.replace(day=1)
                    )
                case "months":
                    month = wall.month - 1 + count
                    wall = wall.replace(
                        year=wall.year + month // 12, month=month % 12 + 1
                    )
                case "years":
                    wall = wall.replace(year=wall.year + count)
        except (OverflowError, ValueError):
            return


def _unit_for(spacing: float) -> _Unit:
    """The unit ticks `spacing` seconds apart count in. Days are allowed an
    hour either way, for a daylight-saving change between them."""
    if spacing < 60:
        return "seconds"
    if spacing < 3600:
        return "minutes"
    if spacing < 86400 - 3600:
        return "hours"
    if spacing < 28 * 86400:
        return "days"
    if spacing < 365 * 86400:
        return "months"
    return "years"


#: Per unit: how a tick is labelled, and how the first tick and one where the
#: larger unit (the date, or the year) changes are.
_FORMATS: dict[_Unit, tuple[str, str]] = {
    "seconds": ("%H:%M:%S", "%b %d %H:%M:%S"),
    "minutes": ("%H:%M", "%b %d %H:%M"),
    "hours": ("%H:%M", "%b %d %H:%M"),
    "days": ("%b %d", "%b %d %Y"),
    "months": ("%b", "%b %Y"),
    "years": ("%Y", "%Y"),
}


def _label(wall: datetime, previous: datetime | None, unit: _Unit) -> str:
    plain, with_context = _FORMATS[unit]
    if unit in ("seconds", "minutes", "hours"):
        if wall.time() == datetime.min.time():
            return wall.strftime("%b %d")
        changed = previous is None or previous.date() != wall.date()
    elif unit == "days":
        if (wall.month, wall.day) == (1, 1):
            return wall.strftime("%Y")
        changed = previous is None or previous.year != wall.year
    elif unit == "months":
        if wall.month == 1:
            return wall.strftime("%Y")
        changed = previous is None or previous.year != wall.year
    else:
        changed = False
    return wall.strftime(with_context if changed else plain)
