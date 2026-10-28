# SPDX-FileCopyrightText: 2025 David Fokkema
# SPDX-FileCopyrightText: 2026 René de Hesselle <dehesselle@web.de>
#
# SPDX-License-Identifier: MIT

from math import inf, isnan, nan

import pytest
from textual.geometry import Region

from tcoda.plot._plot_widget import (
    drop_nans_and_infs,
    map_coordinate_to_hires_pixel,
    map_coordinate_to_pixel,
    map_pixel_to_coordinate,
)


class TestImplementation:
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
    def test_map_coordinate_to_pixel(
        self, x, y, xmin, xmax, ymin, ymax, region, expected
    ):
        assert map_coordinate_to_pixel(x, y, xmin, xmax, ymin, ymax, region) == expected

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
    def test_map_coordinate_to_hires_pixel(
        self, x, y, xmin, xmax, ymin, ymax, region, expected
    ):
        assert (
            map_coordinate_to_hires_pixel(x, y, xmin, xmax, ymin, ymax, region)
            == expected
        )

    @pytest.mark.parametrize(
        "px, py, xmin, xmax, ymin, ymax, region, expected",
        [
            (0, 3, 0.0, 10.0, 0.0, 20.0, Region(0, 0, 4, 4), (1.25, 2.5)),
            (2, 2, 0.0, 10.0, 0.0, 20.0, Region(0, 0, 4, 4), (6.25, 7.5)),
            (1, 1, 0.0, 10.0, 0.0, 20.0, Region(0, 0, 4, 4), (3.75, 12.5)),
            (2, 3, 0.0, 10.0, 0.0, 20.0, Region(2, 3, 4, 4), (1.25, 17.5)),
        ],
    )
    def test_map_pixel_to_coordinate(
        self, px, py, xmin, xmax, ymin, ymax, region, expected
    ):
        assert (
            map_pixel_to_coordinate(px, py, xmin, xmax, ymin, ymax, region) == expected
        )

    def test_drop_nans_and_infs(self):
        assert drop_nans_and_infs([1, nan, 3, 4], [5, 6, inf, 8]) == (
            [1.0, 4.0],
            [5.0, 8.0],
        )

    def test_drop_nans_and_infs_keeps_others_aligned(self):
        # errors belonging to dropped points are dropped as well, while
        # non-finite errors of kept points are preserved
        x, y, xerr, yerr = drop_nans_and_infs(
            [1, nan, 3, 4], [5, 6, 7, 8], [0.1, 0.2, nan, 0.4], [1, 2, 3, 4]
        )
        assert x == [1.0, 3.0, 4.0]
        assert y == [5.0, 7.0, 8.0]
        assert xerr[0] == 0.1 and isnan(xerr[1]) and xerr[2] == 0.4
        assert yerr == [1.0, 3.0, 4.0]

    def test_drop_nans_and_infs_length_mismatch(self):
        with pytest.raises(ValueError):
            drop_nans_and_infs([1, 2], [1, 2], [0.1])
