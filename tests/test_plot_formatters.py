# SPDX-FileCopyrightText: 2025 David Fokkema
# SPDX-FileCopyrightText: 2026 René de Hesselle <dehesselle@web.de>
#
# SPDX-License-Identifier: MIT

from datetime import UTC, datetime, timedelta, timezone
from itertools import pairwise

import pytest

from tcoda.plot import (
    AxisFormatter,
    CategoricalFormatter,
    DateTimeFormatter,
    DurationFormatter,
    NumericFormatter,
    _formatters,
)
from tcoda.plot._formatters import nice_ticks


@pytest.fixture
def numeric_formatter() -> NumericFormatter:
    return NumericFormatter()


class TestNumericFormatter:
    @pytest.mark.parametrize(
        "xmin, xmax, expected",
        [
            (0, 10, [0.0, 2.0, 4.0, 6.0, 8.0, 10.0]),
            (0, 1, [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]),
            (1 / 30, 1.0, [0.2, 0.4, 0.6, 0.8, 1.0]),
        ],
    )
    def test_get_ticks(self, numeric_formatter: NumericFormatter, xmin, xmax, expected):
        ticks = numeric_formatter.get_ticks(xmin, xmax)
        assert ticks == pytest.approx(expected)

    @pytest.mark.parametrize(
        "xmin, xmax, expected",
        [
            (0, 10, [0.0, 2.0, 4.0, 6.0, 8.0, 10.0]),
            (0, 1, [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]),
            (1 / 30, 1.0, [0.2, 0.4, 0.6, 0.8, 1.0]),
        ],
    )
    def test_get_ticks_and_labels(
        self, numeric_formatter: NumericFormatter, xmin, xmax, expected
    ):
        ticks, labels = numeric_formatter.get_ticks_and_labels(xmin, xmax)
        assert ticks == pytest.approx(expected)
        # Ensure we get labels for each tick
        assert len(labels) == len(ticks)
        # Ensure labels are strings
        assert all(isinstance(label, str) for label in labels)

    def test_get_labels(self, numeric_formatter: NumericFormatter):
        ticks = [0.0, 0.5, 1.0, 1.5, 2.0]
        labels = numeric_formatter.get_labels(ticks)
        # With spacing of 0.5, decimals should be auto-determined as 1
        assert labels == ["0.0", "0.5", "1.0", "1.5", "2.0"]

    def test_get_labels_auto_decimals(self, numeric_formatter: NumericFormatter):
        # Test that decimals are automatically determined from tick spacing
        ticks = [0.0, 0.05, 0.10, 0.15, 0.20]
        labels = numeric_formatter.get_labels(ticks)
        # With spacing of 0.05, decimals should be 2
        assert labels == ["0.00", "0.05", "0.10", "0.15", "0.20"]

    def test_get_labels_for_empty_ticks(self, numeric_formatter: NumericFormatter):
        labels = numeric_formatter.get_labels([])
        assert labels == []

    def test_is_axis_formatter(self, numeric_formatter: NumericFormatter):
        # Ensure NumericFormatter is an instance of AxisFormatter
        assert isinstance(numeric_formatter, AxisFormatter)


@pytest.fixture
def duration_formatter() -> DurationFormatter:
    return DurationFormatter()


class TestDurationFormatter:
    @pytest.mark.parametrize(
        "xmin, xmax, expected_unit",
        [
            (0, 10, "s"),  # 10 seconds
            (0, 300, "min"),  # 5 minutes
            (0, 7200, "h"),  # 2 hours
            (0, 172800, "d"),  # 2 days
            (0, 5184000, "mo"),  # ~2 months
            (0, 63072000, "y"),  # ~2 years
        ],
    )
    def test_unit_selection(
        self, duration_formatter: DurationFormatter, xmin, xmax, expected_unit
    ):
        _, labels = duration_formatter.get_ticks_and_labels(xmin, xmax)
        # Check that labels contain the expected unit
        assert all(expected_unit in label for label in labels)

    def test_get_ticks_seconds(self, duration_formatter: DurationFormatter):
        # Test for a range in seconds (0-10 seconds)
        ticks = duration_formatter.get_ticks(0, 10)
        # Should get nice intervals like 0, 2, 4, 6, 8, 10
        assert ticks == pytest.approx([0.0, 2.0, 4.0, 6.0, 8.0, 10.0])

    def test_get_ticks_minutes(self, duration_formatter: DurationFormatter):
        # Test for a range in minutes (0-600 seconds = 10 minutes)
        ticks = duration_formatter.get_ticks(0, 600)
        # Should get ticks in minute intervals (0, 2, 4, 6, 8, 10 minutes)
        assert ticks == pytest.approx([0.0, 120.0, 240.0, 360.0, 480.0, 600.0])

    def test_get_ticks_hours(self, duration_formatter: DurationFormatter):
        # Test for a range in hours (0-7200 seconds = 2 hours)
        ticks = duration_formatter.get_ticks(0, 7200)
        # Should get ticks at 0.5 hour intervals
        assert ticks == pytest.approx([0.0, 1800.0, 3600.0, 5400.0, 7200.0])

    def test_get_labels(self, duration_formatter: DurationFormatter):
        # Test label formatting for seconds
        ticks = [0.0, 2.0, 4.0, 6.0, 8.0, 10.0]
        labels = duration_formatter.get_labels(ticks)
        assert labels == ["0s", "2s", "4s", "6s", "8s", "10s"]

    def test_get_labels_minutes(self, duration_formatter: DurationFormatter):
        # Test label formatting for minutes
        ticks = [0.0, 120.0, 240.0, 360.0, 480.0, 600.0]  # 0, 2, 4, 6, 8, 10 minutes
        labels = duration_formatter.get_labels(ticks)
        assert labels == ["0min", "2min", "4min", "6min", "8min", "10min"]

    def test_get_labels_hours(self, duration_formatter: DurationFormatter):
        # Test label formatting for hours
        ticks = [0.0, 3600.0, 7200.0]  # 0, 1, 2 hours
        labels = duration_formatter.get_labels(ticks)
        assert labels == ["0h", "1h", "2h"]

    def test_get_labels_for_empty_ticks(self, duration_formatter: DurationFormatter):
        labels = duration_formatter.get_labels([])
        assert labels == []

    def test_get_ticks_and_labels(self, duration_formatter: DurationFormatter):
        ticks, labels = duration_formatter.get_ticks_and_labels(0, 10)
        # Ensure we get labels for each tick
        assert len(labels) == len(ticks)
        # Ensure labels are strings
        assert all(isinstance(label, str) for label in labels)
        # Ensure labels contain a unit
        assert all(
            any(unit in label for unit, _ in DurationFormatter.UNITS)
            for label in labels
        )

    def test_is_axis_formatter(self, duration_formatter: DurationFormatter):
        # Ensure DurationFormatter is an instance of AxisFormatter
        assert isinstance(duration_formatter, AxisFormatter)


class TestNumericFormatterEdges:
    def test_descending_ticks_are_labelled(self):
        assert NumericFormatter().get_labels([1.0, 0.5, 0.0]) == ["1.0", "0.5", "0.0"]

    def test_repeated_ticks_are_labelled(self):
        assert NumericFormatter().get_labels([2.0, 2.0]) == ["2", "2"]


class TestCategoricalFormatter:
    def test_labels_sit_on_whole_numbers_from_one(self):
        formatter = CategoricalFormatter(["a", "b", "c"])
        assert formatter.get_ticks(0, 10) == [1.0, 2.0, 3.0]
        assert formatter.get_labels([1.0, 2.2, 3.0, 4.0, 0.0]) == [
            "a",
            "b",
            "c",
            "",
            "",
        ]


#: 2023-11-14 22:13:20 UTC.
START = 1.7e9
DAY = 86400


def utc_dates(ticks: list[float]) -> list[datetime]:
    return [datetime(1970, 1, 1, tzinfo=UTC) + timedelta(seconds=t) for t in ticks]


class TestDateTimeFormatter:
    @pytest.mark.parametrize("days", [1, 3, 31, 45, 200, 400, 2000])
    def test_no_two_ticks_fall_on_the_same_boundary(self, days):
        ticks = DateTimeFormatter().get_ticks(START, START + days * DAY)
        assert len(set(ticks)) == len(ticks) > 1

    @pytest.mark.parametrize(
        "low, high",
        [
            (-1e12, 1e12),
            (-400 * DAY, 0),
            (-1e300, -1e299),
            (1e300, 1e301),
            (float("-inf"), float("inf")),
            (START, START),
            (START, START + 0.001),
        ],
    )
    def test_no_range_raises(self, low, high):
        # Pre-1970 raised OSError on Windows; far out, datetime overflows.
        ticks, labels = DateTimeFormatter().get_ticks_and_labels(low, high)
        assert len(ticks) == len(labels)

    def test_ticks_beyond_a_date_get_no_label(self):
        labels = DateTimeFormatter().get_labels([-1e15, START])
        assert labels[0] == "" != labels[1]

    def test_years_are_round(self):
        ticks = DateTimeFormatter(UTC).get_ticks(-1e12, 1e12)
        assert [date.year for date in utc_dates(ticks)] == [2000, 4000, 6000, 8000]

    @pytest.mark.parametrize(
        "span, step",
        [
            (90, 15),
            (40 * 60, 5 * 60),
            (3 * 3600, 30 * 60),
            (20 * 3600, 3 * 3600),
            (40 * 3600, 6 * 3600),
        ],
    )
    def test_steps_are_clock_steps(self, span, step):
        ticks = DateTimeFormatter(UTC).get_ticks(START, START + span)
        assert all(b - a == step for a, b in pairwise(ticks))
        assert all(tick % step == 0 for tick in ticks)

    def test_more_room_takes_more_ticks(self):
        formatter = DateTimeFormatter(UTC)
        few = formatter.get_ticks(START, START + DAY, max_ticks=3)
        many = formatter.get_ticks(START, START + DAY, max_ticks=24)
        assert len(few) - 1 <= 3 < len(many) - 1 <= 24

    def test_ticks_fall_on_midnight(self):
        ticks = DateTimeFormatter(UTC).get_ticks(START, START + 5 * DAY)
        assert all(tick % DAY == 0 for tick in ticks)

    def test_weeks_start_on_monday(self):
        ticks = DateTimeFormatter(UTC).get_ticks(START, START + 50 * DAY)
        assert {date.weekday() for date in utc_dates(ticks)} == {0}

    def test_months_start_on_the_first(self):
        ticks = DateTimeFormatter(UTC).get_ticks(START, START + 200 * DAY)
        assert {date.day for date in utc_dates(ticks)} == {1}

    def test_hours_name_the_date_at_midnight_and_first(self):
        _, labels = DateTimeFormatter(UTC).get_ticks_and_labels(
            START - 0.5 * DAY, START + 0.5 * DAY
        )
        assert labels == [
            "Nov 14 12:00",
            "15:00",
            "18:00",
            "21:00",
            "Nov 15",
            "03:00",
            "06:00",
            "09:00",
        ]

    def test_days_name_the_year_first_and_on_new_year(self):
        new_year = datetime(2024, 1, 1, tzinfo=UTC).timestamp()
        _, labels = DateTimeFormatter(UTC).get_ticks_and_labels(
            new_year - 3 * DAY, new_year + 3 * DAY
        )
        assert labels[:4] == ["Dec 29 2023", "Dec 30", "Dec 31", "2024"]

    def test_months_name_the_year_first_and_in_january(self):
        _, labels = DateTimeFormatter(UTC).get_ticks_and_labels(
            START, START + 400 * DAY
        )
        assert labels == ["2024", "Apr", "Jul", "Oct"]

    def test_custom_ticks_are_labelled_in_their_own_unit(self):
        ticks = [START + 60 * n for n in range(3)]
        assert DateTimeFormatter(UTC).get_labels(ticks) == [
            "Nov 14 22:13",
            "22:14",
            "22:15",
        ]

    def test_hours_are_whole_in_an_odd_time_zone(self):
        kathmandu = timezone(timedelta(hours=5, minutes=45))
        ticks = DateTimeFormatter(kathmandu).get_ticks(START, START + 6 * 3600)
        assert {datetime.fromtimestamp(t, kathmandu).minute for t in ticks} == {0}

    def test_local_time_is_the_default(self, monkeypatch):
        monkeypatch.setattr(_formatters, "_local_offset", lambda timestamp: 7200)
        ticks, labels = DateTimeFormatter().get_ticks_and_labels(
            START, START + 8 * 3600
        )
        # 22:13 UTC is 00:13 at UTC+2, so the first full hour is local 01:00.
        assert labels[0] == "Nov 15 01:00"
        assert ticks[0] % 3600 == 0

    def test_a_daylight_saving_change_keeps_ticks_on_the_hour(self, monkeypatch):
        # Clocks go from UTC+1 to UTC+2 at START: local 23:13:20 becomes 00:13:20.
        monkeypatch.setattr(
            _formatters,
            "_local_offset",
            lambda timestamp: 3600 if timestamp < START else 7200,
        )
        ticks, labels = DateTimeFormatter().get_ticks_and_labels(
            START - 4 * 3600, START + 4 * 3600
        )
        # Local 00:00 never happens; the next hour names the date instead.
        assert labels == ["Nov 14 20:00", "21:00", "22:00", "23:00", "Nov 15 01:00",
                          "02:00", "03:00", "04:00"]  # fmt: skip
        assert len(set(ticks)) == len(ticks)

    def test_a_lone_value_gets_an_hour_either_side(self):
        assert DateTimeFormatter().around(START) == (START - 3600, START + 3600)


class TestAround:
    @pytest.mark.parametrize(
        "formatter",
        [NumericFormatter(), DurationFormatter()],
        ids=["numeric", "duration"],
    )
    @pytest.mark.parametrize(
        "value, expected", [(0, (-1, 1)), (300, (150, 450)), (-4, (-6, -2))]
    )
    def test_a_lone_value_gets_half_itself_either_side(
        self, formatter, value, expected
    ):
        assert formatter.around(value) == expected

    def test_a_lone_category_gets_half_a_category_either_side(self):
        assert CategoricalFormatter(["a"]).around(1) == (0.5, 1.5)


class TestNiceTicks:
    def test_more_room_takes_more_ticks(self):
        assert nice_ticks(0, 10, 30) == pytest.approx([i / 2 for i in range(21)])

    def test_no_range_is_one_tick(self):
        assert nice_ticks(5, 5) == [5]

    def test_an_endless_range_has_no_ticks(self):
        assert nice_ticks(0, float("inf")) == []
