# SPDX-FileCopyrightText: 2025 David Fokkema
# SPDX-FileCopyrightText: 2026 René de Hesselle <dehesselle@web.de>
#
# SPDX-License-Identifier: MIT

from datetime import UTC, datetime

import pytest

from tcoda.plot import (
    AxisFormatter,
    CategoricalFormatter,
    DateTimeFormatter,
    DurationFormatter,
    NumericFormatter,
)


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


class TestDateTimeFormatter:
    @pytest.mark.parametrize("days", [1, 3, 31, 45, 200, 400, 2000])
    def test_no_two_ticks_fall_on_the_same_boundary(self, days):
        ticks, labels = DateTimeFormatter().get_ticks_and_labels(
            START, START + days * DAY
        )
        assert len(set(ticks)) == len(ticks) > 1
        assert len(set(labels)) == len(labels)

    def test_a_month_is_labelled_by_day(self):
        _, labels = DateTimeFormatter().get_ticks_and_labels(START, START + 31 * DAY)
        assert all(label.endswith(", 2023") or ", 20" in label for label in labels)

    def test_ticks_fall_on_midnight(self):
        ticks = DateTimeFormatter().get_ticks(START, START + 5 * DAY)
        assert all(tick % DAY == 0 for tick in ticks)

    def test_hours_repeat_the_date_only_when_it_changes(self):
        ticks, labels = DateTimeFormatter().get_ticks_and_labels(
            START - 0.5 * DAY, START + 0.5 * DAY
        )
        days = [datetime.fromtimestamp(tick, UTC).date() for tick in ticks]
        changed = [i == 0 or days[i] != days[i - 1] for i in range(len(days))]
        assert sum(changed) >= 2
        assert ["," in label for label in labels] == changed
