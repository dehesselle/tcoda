# SPDX-FileCopyrightText: 2026 René de Hesselle <dehesselle@web.de>
#
# SPDX-License-Identifier: 0BSD

"""The plot widget, end to end: each kind of dataset reaches the canvas.

Upstream's own tests cover the axis formatters and the coordinate maths; these
cover the drawing, so that reworking its internals shows up as a failure here
rather than as a blank plot.
"""

from __future__ import annotations

import math
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

import pytest
from textual.app import App, ComposeResult

from tcoda.plot import HiResMode, LegendLocation, PlotWidget
from tcoda.plot._axis_formatter import DateTimeFormatter
from tcoda.plot._canvas import Canvas

SIZE = (80, 24)
XS = [i / 10 for i in range(100)]
SINE = [math.sin(x) for x in XS]

#: Every way a dataset can be drawn: full cells, then each high-resolution mode.
MODES = [None, *HiResMode]


class Harness(App[None]):
    def compose(self) -> ComposeResult:
        yield PlotWidget()


def drawn_cells(plot: PlotWidget) -> int:
    """Non-blank cells inside the plot area's frame."""
    canvas = plot.query_one("#plot", Canvas)
    return sum(cell != " " for row in canvas._buffer[1:-1] for cell in row[1:-1])


def x_labels(plot: PlotWidget) -> str:
    return "".join(plot.query_one("#margin-bottom", Canvas)._buffer[0])


@asynccontextmanager
async def drawn(draw: Callable[[PlotWidget], None]) -> AsyncIterator[PlotWidget]:
    """A freshly mounted plot, drawn on and rendered, while the app still runs."""
    app = Harness()
    async with app.run_test(size=SIZE) as pilot:
        plot = app.query_one(PlotWidget)
        await pilot.pause()
        draw(plot)
        await pilot.pause()
        yield plot


async def test_an_empty_plot_draws_nothing_inside_its_frame() -> None:
    async with drawn(lambda plot: None) as plot:
        assert drawn_cells(plot) == 0


@pytest.mark.parametrize("mode", MODES, ids=str)
async def test_a_line_plot_draws(mode: HiResMode | None) -> None:
    async with drawn(lambda plot: plot.plot(XS, SINE, hires_mode=mode)) as plot:
        assert drawn_cells(plot) > 0


@pytest.mark.parametrize("mode", MODES, ids=str)
async def test_a_scatter_plot_draws(mode: HiResMode | None) -> None:
    async with drawn(lambda plot: plot.scatter(XS, SINE, hires_mode=mode)) as plot:
        assert drawn_cells(plot) > 0


@pytest.mark.parametrize("mode", MODES, ids=str)
async def test_a_bar_plot_draws(mode: HiResMode | None) -> None:
    async with drawn(
        lambda plot: plot.bar([1, 2, 3], [1, 3, 2], hires_mode=mode)
    ) as plot:
        assert drawn_cells(plot) > 0


@pytest.mark.parametrize("mode", MODES, ids=str)
async def test_an_errorbar_plot_draws(mode: HiResMode | None) -> None:
    def draw(plot: PlotWidget) -> None:
        plot.errorbar([1, 2, 3], [1, 2, 1], yerr=[0.3] * 3, hires_mode=mode)

    async with drawn(draw) as plot:
        assert drawn_cells(plot) > 0


async def test_errors_are_dropped_along_with_their_nan_points() -> None:
    """The big error belongs to the dropped point; it must not slide onto
    the next one."""

    def canvas(plot: PlotWidget) -> list[list[str]]:
        return plot.query_one("#plot", Canvas)._buffer

    def with_nan(plot: PlotWidget) -> None:
        plot.errorbar([1, math.nan, 3, 5], [1, 1, 2, 1], yerr=[0.1, 5, 0.1, 0.1])
        plot.set_xlimits(0, 6)
        plot.set_ylimits(-5, 8)

    def without(plot: PlotWidget) -> None:
        plot.errorbar([1, 3, 5], [1, 2, 1], yerr=[0.1, 0.1, 0.1])
        plot.set_xlimits(0, 6)
        plot.set_ylimits(-5, 8)

    async with drawn(with_nan) as plot:
        actual = canvas(plot)
    async with drawn(without) as plot:
        expected = canvas(plot)
    assert actual == expected


async def test_categorical_bars_label_the_x_axis() -> None:
    async with drawn(
        lambda plot: plot.bar(["red", "green", "blue"], [1, 3, 2])
    ) as plot:
        assert x_labels(plot).split() == ["red", "green", "blue"]


async def test_nans_and_infs_are_dropped_rather_than_drawn() -> None:
    def draw(plot: PlotWidget) -> None:
        plot.plot([0, 1, 2, 3], [math.nan, 0, math.inf, 1])

    async with drawn(draw) as plot:
        assert drawn_cells(plot) > 0


async def test_a_vertical_line_draws() -> None:
    async with drawn(lambda plot: plot.add_v_line(0.5)) as plot:
        assert drawn_cells(plot) > 0


async def test_clear_removes_every_dataset() -> None:
    def draw(plot: PlotWidget) -> None:
        plot.plot(XS, SINE)
        plot.clear()

    async with drawn(draw) as plot:
        assert drawn_cells(plot) == 0


async def test_limits_outside_the_data_leave_the_plot_empty() -> None:
    def draw(plot: PlotWidget) -> None:
        plot.plot([0, 1], [0, 1])
        plot.set_xlimits(5, 6)

    async with drawn(draw) as plot:
        assert drawn_cells(plot) == 0


async def test_limits_set_the_axis_labels() -> None:
    async with drawn(lambda plot: plot.set_xlimits(0, 10)) as plot:
        labels = x_labels(plot).split()
        assert (labels[0], labels[-1]) == ("0", "10")


async def test_a_datetime_axis_labels_dates() -> None:
    def draw(plot: PlotWidget) -> None:
        plot.set_x_formatter(DateTimeFormatter())
        plot.plot([1.7e9, 1.7e9 + 3 * 86400], [0, 1])

    async with drawn(draw) as plot:
        assert "2023" in x_labels(plot)


@pytest.mark.parametrize("location", LegendLocation, ids=str)
async def test_the_legend_lists_labelled_datasets(location: LegendLocation) -> None:
    def draw(plot: PlotWidget) -> None:
        plot.plot(XS, SINE, label="sine")
        plot.scatter(XS, SINE)
        plot.show_legend(location)

    async with drawn(draw) as plot:
        legend = plot.query_one("#legend")
        assert legend.display
        assert str(legend.content).endswith(" sine")


async def test_a_resize_redraws_at_the_new_size() -> None:
    app = Harness()
    async with app.run_test(size=SIZE) as pilot:
        plot = app.query_one(PlotWidget)
        plot.plot(XS, SINE)
        await pilot.pause()
        before = plot.query_one("#plot", Canvas)._canvas_size

        await pilot.resize_terminal(60, 20)
        await pilot.pause()
        after = plot.query_one("#plot", Canvas)._canvas_size

        assert after.width < before.width
        assert drawn_cells(plot) > 0


async def test_keyboard_zoom_narrows_the_x_range() -> None:
    app = Harness()
    async with app.run_test(size=SIZE) as pilot:
        plot = app.query_one(PlotWidget)
        plot.set_xlimits(0, 10)
        plot.focus()
        await pilot.pause()

        await pilot.press("plus")
        await pilot.pause()
        assert plot._x_max - plot._x_min < 10
