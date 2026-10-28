# SPDX-FileCopyrightText: 2025 David Fokkema
# SPDX-FileCopyrightText: 2026 René de Hesselle <dehesselle@web.de>
#
# SPDX-License-Identifier: MIT

from math import inf, isnan, nan

import pytest
from textual.geometry import Region

from tcoda.plot._datasets import drop_non_finite
from tcoda.plot._viewport import Viewport, pan, zoom


class TestViewport:
    @pytest.mark.parametrize(
        "x, y, xmin, xmax, ymin, ymax, region, expected",
        [
            (0.0, 0.0, 0.0, 10.0, 0.0, 20.0, Region(0, 0, 4, 4), (0, 3)),
            (1.0, 1.0, 0.0, 10.0, 0.0, 20.0, Region(0, 0, 4, 4), (0, 3)),
            (4.99, 4.99, 0.0, 10.0, 0.0, 20.0, Region(0, 0, 4, 4), (1, 3)),
            (1.0, 1.0, 0.0, 10.0, 0.0, 20.0, Region(2, 3, 4, 4), (2, 6)),
            (10.0, 20.0, 0.0, 10.0, 0.0, 20.0, Region(0, 0, 4, 4), (4, -1)),
        ],
    )
    def test_to_cell(self, x, y, xmin, xmax, ymin, ymax, region, expected):
        viewport = Viewport((xmin, xmax), (ymin, ymax), region)
        assert viewport.to_cell(x, y) == expected

    @pytest.mark.parametrize(
        "x, y, xmin, xmax, ymin, ymax, region, expected",
        [
            (0.0, 0.0, 0.0, 10.0, 0.0, 20.0, Region(0, 0, 4, 4), (0.0, 4.0)),
            (1.0, 1.0, 0.0, 10.0, 0.0, 20.0, Region(0, 0, 4, 4), (0.4, 3.8)),
            (5.0, 5.0, 0.0, 10.0, 0.0, 20.0, Region(0, 0, 4, 4), (2.0, 3.0)),
            (1.0, 1.0, 0.0, 10.0, 0.0, 20.0, Region(2, 3, 4, 4), (2.4, 6.8)),
            (10.0, 20.0, 0.0, 10.0, 0.0, 20.0, Region(0, 0, 4, 4), (4.0, 0.0)),
        ],
    )
    def test_to_point(self, x, y, xmin, xmax, ymin, ymax, region, expected):
        viewport = Viewport((xmin, xmax), (ymin, ymax), region)
        assert viewport.to_point(x, y) == expected

    @pytest.mark.parametrize(
        "px, py, xmin, xmax, ymin, ymax, region, expected",
        [
            (0, 3, 0.0, 10.0, 0.0, 20.0, Region(0, 0, 4, 4), (1.25, 2.5)),
            (2, 2, 0.0, 10.0, 0.0, 20.0, Region(0, 0, 4, 4), (6.25, 7.5)),
            (1, 1, 0.0, 10.0, 0.0, 20.0, Region(0, 0, 4, 4), (3.75, 12.5)),
            (2, 3, 0.0, 10.0, 0.0, 20.0, Region(2, 3, 4, 4), (1.25, 17.5)),
        ],
    )
    def test_to_data(self, px, py, xmin, xmax, ymin, ymax, region, expected):
        viewport = Viewport((xmin, xmax), (ymin, ymax), region)
        assert viewport.to_data(px, py) == expected

    def test_drop_non_finite(self):
        assert drop_non_finite([1, nan, 3, 4], [5, 6, inf, 8]) == (
            [1.0, 4.0],
            [5.0, 8.0],
        )

    def test_drop_non_finite_keeps_others_aligned(self):
        # errors belonging to dropped points are dropped as well, while
        # non-finite errors of kept points are preserved
        x, y, xerr, yerr = drop_non_finite(
            [1, nan, 3, 4], [5, 6, 7, 8], [0.1, 0.2, nan, 0.4], [1, 2, 3, 4]
        )
        assert x == [1.0, 3.0, 4.0]
        assert y == [5.0, 7.0, 8.0]
        assert xerr[0] == 0.1 and isnan(xerr[1]) and xerr[2] == 0.4
        assert yerr == [1.0, 3.0, 4.0]

    def test_drop_non_finite_length_mismatch(self):
        with pytest.raises(ValueError):
            drop_non_finite([1, 2], [1, 2], [0.1])


class TestZoomAndPan:
    def test_zoom_keeps_the_centre_in_place(self):
        low, high = zoom((0.0, 10.0), 2.0, 0.25)
        # 2.0 stays the same fraction of the way across.
        assert (2.0 - low) / (high - low) == pytest.approx(0.2)
        assert high - low == pytest.approx(8.0)

    def test_negative_zoom_widens(self):
        low, high = zoom((0.0, 10.0), 5.0, -0.2)
        assert high - low > 10.0

    def test_pan_shifts_both_ends(self):
        assert pan((0.0, 10.0), 2.5) == (2.5, 12.5)

    def test_data_per_cell(self):
        viewport = Viewport((0.0, 10.0), (0.0, 20.0), Region(0, 0, 4, 5))
        assert viewport.data_per_cell() == (2.5, 4.0)
