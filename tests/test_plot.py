# SPDX-FileCopyrightText: 2026 René de Hesselle <dehesselle@web.de>
#
# SPDX-License-Identifier: 0BSD

"""The plot widget, end to end: each kind of dataset reaches the canvas, and
the widget behaves like any other Textual widget around it.

`test_plot_golden.py` pins down exactly what is drawn; these check that
something is, and everything that isn't a picture.
"""

from __future__ import annotations

import math
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import ClassVar, get_args

import pytest
from textual import events, on
from textual.app import App, ComposeResult
from textual.binding import BindingType
from textual.containers import VerticalScroll
from textual.pilot import Pilot
from textual.widget import Widget
from textual.widgets import Static

from tcoda.plot import DateTimeFormatter, HiResMode, LegendLocation, Plot
from tcoda.plot._canvas import Canvas

SIZE = (80, 24)
XS = [i / 10 for i in range(100)]
SINE = [math.sin(x) for x in XS]

#: Every way a dataset can be drawn: full cells, then each high-resolution mode.
MODES = [None, *get_args(HiResMode.__value__)]
LOCATIONS = get_args(LegendLocation.__value__)


class Harness(App[None]):
    def compose(self) -> ComposeResult:
        yield Plot()


def canvas(plot: Plot) -> Canvas:
    return plot.query_one("#plot-canvas", Canvas)


def drawn_cells(plot: Plot) -> int:
    """Non-blank cells inside the data area's frame."""
    rows = canvas(plot)._chars
    return sum(cell != " " for row in rows[1:-1] for cell in row[1:-1])


def text_of(plot: Plot, canvas_id: str) -> str:
    return "\n".join("".join(row) for row in plot.query_one(canvas_id, Canvas)._chars)


def x_labels(plot: Plot) -> str:
    return "".join(plot.query_one("#plot-x-axis", Canvas)._chars[0])


def scroll_down(widget: Widget, x: int, y: int) -> None:
    """One notch of the wheel over a cell of `widget`, as a terminal sends it:
    to the widget under the pointer, bubbling up from there, and naming no
    widget -- only events made up by a pilot do."""
    region = widget.content_region
    widget.post_message(
        events.MouseScrollDown(
            None, x, y, 0, 0, 0, False, False, False,
            screen_x=region.x + x, screen_y=region.y + y,
        )
    )  # fmt: skip


async def settle(pilot: Pilot[None], plot: Plot) -> None:
    """Wait for the plot to finish drawing. A change in how wide its y tick
    labels are lays it out again, and that draws it a second time."""
    before = None
    for _ in range(10):
        await pilot.pause()
        now = [canvas._chars for canvas in plot.query(Canvas)]
        if now == before and not plot._redraw_pending:
            return
        before = now


@asynccontextmanager
async def drawn(draw: Callable[[Plot], object]) -> AsyncIterator[Plot]:
    """A freshly mounted plot, drawn on and rendered, while the app still runs."""
    app = Harness()
    async with app.run_test(size=SIZE) as pilot:
        plot = app.query_one(Plot)
        await pilot.pause()
        draw(plot)
        await settle(pilot, plot)
        yield plot


# ------------------------------------------------------------------ drawing


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
    def draw(plot: Plot) -> None:
        plot.errorbar([1, 2, 3], [1, 2, 1], yerr=[0.3] * 3, hires_mode=mode)

    async with drawn(draw) as plot:
        assert drawn_cells(plot) > 0


async def test_an_unknown_mode_is_refused() -> None:
    with pytest.raises(ValueError, match="hires_mode"):
        Plot().plot(XS, SINE, hires_mode="Braille")  # type: ignore[arg-type]


async def test_errors_are_dropped_along_with_their_nan_points() -> None:
    """The big error belongs to the dropped point; it must not slide onto
    the next one."""

    def with_nan(plot: Plot) -> None:
        plot.errorbar([1, math.nan, 3, 5], [1, 1, 2, 1], yerr=[0.1, 5, 0.1, 0.1])
        plot.x_limits = (0, 6)
        plot.y_limits = (-5, 8)

    def without(plot: Plot) -> None:
        plot.errorbar([1, 3, 5], [1, 2, 1], yerr=[0.1, 0.1, 0.1])
        plot.x_limits = (0, 6)
        plot.y_limits = (-5, 8)

    async with drawn(with_nan) as plot:
        actual = canvas(plot)._chars
    async with drawn(without) as plot:
        expected = canvas(plot)._chars
    assert actual == expected


async def test_bar_styles_are_dropped_along_with_their_nan_bars() -> None:
    def draw(plot: Plot) -> None:
        plot.bar([1, math.nan, 3], [1, 1, 2], style=["red", "green", "blue"])

    async with drawn(draw) as plot:
        styles = {str(s) for row in canvas(plot)._styles for s in row if s}
        assert any("#ff0000" in s for s in styles)
        assert any("#0000ff" in s for s in styles)
        assert not any("#008000" in s for s in styles)


async def test_categorical_bars_label_the_x_axis() -> None:
    async with drawn(
        lambda plot: plot.bar(["red", "green", "blue"], [1, 3, 2])
    ) as plot:
        assert x_labels(plot).split() == ["red", "green", "blue"]


async def test_nans_and_infs_are_dropped_rather_than_drawn() -> None:
    def draw(plot: Plot) -> None:
        plot.plot([0, 1, 2, 3], [math.nan, 0, math.inf, 1])

    async with drawn(draw) as plot:
        assert drawn_cells(plot) > 0


async def test_a_vertical_line_draws() -> None:
    async with drawn(lambda plot: plot.vline(0.5)) as plot:
        assert drawn_cells(plot) > 0


async def test_clear_removes_every_dataset() -> None:
    def draw(plot: Plot) -> None:
        plot.plot(XS, SINE)
        plot.clear()

    async with drawn(draw) as plot:
        assert drawn_cells(plot) == 0


async def test_limits_outside_the_data_leave_the_plot_empty() -> None:
    def draw(plot: Plot) -> None:
        plot.plot([0, 1], [0, 1])
        plot.x_limits = (5, 6)

    async with drawn(draw) as plot:
        assert drawn_cells(plot) == 0


async def test_limits_set_the_axis_labels() -> None:
    def draw(plot: Plot) -> None:
        plot.x_limits = (0, 10)

    async with drawn(draw) as plot:
        labels = x_labels(plot).split()
        assert (labels[0], labels[-1]) == ("0", "10")


async def test_an_open_limit_follows_the_data() -> None:
    def draw(plot: Plot) -> None:
        plot.plot([2, 7], [0, 1])
        plot.x_limits = (0, None)

    async with drawn(draw) as plot:
        # The open end goes a margin past the data, the fixed one stays.
        assert plot.x_range == pytest.approx((0.0, 7.0 * (1 + Plot.AUTO_MARGIN)))


async def test_a_datetime_axis_labels_dates() -> None:
    def draw(plot: Plot) -> None:
        plot.x_formatter = DateTimeFormatter()
        plot.plot([1.7e9, 1.7e9 + 3 * 86400], [0, 1])

    async with drawn(draw) as plot:
        assert x_labels(plot).split()[:3] == ["Nov", "15", "12:00"]


async def test_descending_custom_ticks_draw() -> None:
    def draw(plot: Plot) -> None:
        plot.x_limits = (0, 10)
        plot.x_ticks = [8, 4, 0]

    async with drawn(draw) as plot:
        assert x_labels(plot).split() == ["0", "4", "8"]


async def test_a_resize_redraws_at_the_new_size() -> None:
    app = Harness()
    async with app.run_test(size=SIZE) as pilot:
        plot = app.query_one(Plot)
        plot.plot(XS, SINE)
        await pilot.pause()
        before = canvas(plot).size

        await pilot.resize_terminal(60, 20)
        await pilot.pause()

        assert canvas(plot).size.width < before.width
        assert len(canvas(plot)._chars[0]) == canvas(plot).size.width
        assert drawn_cells(plot) > 0


async def test_a_lone_point_gets_a_range_around_it() -> None:
    async with drawn(lambda plot: plot.plot([5], [300])) as plot:
        assert plot.x_range == (2.5, 7.5)
        assert plot.y_range == (150.0, 450.0)
        assert x_labels(plot).split()[0] != x_labels(plot).split()[-1]


async def test_a_flat_line_on_a_fixed_floor_keeps_the_floor() -> None:
    def draw(plot: Plot) -> None:
        plot.plot([0, 1, 2], [0, 0, 0])
        plot.y_limits = (0, None)

    async with drawn(draw) as plot:
        assert plot.y_range == (0.0, 1.0)


async def test_an_open_end_without_data_meets_the_fixed_one() -> None:
    def draw(plot: Plot) -> None:
        plot.x_limits = (5, None)

    async with drawn(draw) as plot:
        assert plot.x_range == (5.0, 7.5)


async def test_the_extremes_stay_clear_of_the_frame() -> None:
    async with drawn(lambda plot: plot.plot(XS, SINE)) as plot:
        rows = canvas(plot)._chars
        # Nothing is drawn on the frame's top or bottom row but the frame.
        assert all(char in "━┏┓┗┛┻┳" for char in rows[0] + rows[-1])
        assert drawn_cells(plot) > 0


async def test_x_ticks_thin_out_on_a_narrow_plot() -> None:
    class Narrow(App[None]):
        CSS = "Plot { width: 30; }"

        def compose(self) -> ComposeResult:
            yield Plot()

    def labels_and_gaps(plot: Plot) -> tuple[list[str], list[int]]:
        row = x_labels(plot)
        words = row.split()
        starts = [row.index(word) for word in words]
        gaps = [b - (a + len(w)) for a, b, w in zip(starts, starts[1:], words)]
        return words, gaps

    async with drawn(lambda plot: plot.plot([0, 1000], [0, 1])) as plot:
        wide, _ = labels_and_gaps(plot)
    app = Narrow()
    async with app.run_test(size=SIZE) as pilot:
        plot = app.query_one(Plot)
        plot.plot([0, 1000], [0, 1])
        await settle(pilot, plot)
        narrow, gaps = labels_and_gaps(plot)
    assert 1 < len(narrow) < len(wide)
    assert min(gaps) >= 2


async def test_y_ticks_follow_the_height() -> None:
    app = Harness()
    async with app.run_test(size=SIZE) as pilot:
        plot = app.query_one(Plot)
        plot.y_limits = (0, 100)
        await settle(pilot, plot)
        tall = text_of(plot, "#plot-y-ticks").split()
        await pilot.resize_terminal(80, 12)
        await settle(pilot, plot)
        short = text_of(plot, "#plot-y-ticks").split()
    assert 1 < len(short) < len(tall)


async def test_rows_without_a_label_take_no_room() -> None:
    def heights(plot: Plot) -> tuple[int, int]:
        return (
            plot.query_one("#plot-y-label").size.height,
            plot.query_one("#plot-x-axis").size.height,
        )

    app = Harness()
    async with app.run_test(size=SIZE) as pilot:
        plot = app.query_one(Plot)
        await settle(pilot, plot)
        assert heights(plot) == (0, 1)
        plot.x_label = "time"
        plot.y_label = "volts"
        await settle(pilot, plot)
        assert heights(plot) == (2, 3)


async def test_the_y_tick_column_fits_the_widest_label() -> None:
    def draw(plot: Plot) -> None:
        plot.y_limits = (0, 1_000_000)

    async with drawn(draw) as plot:
        assert plot.query_one("#plot-y-ticks").size.width == len("1000000") + 2
        lines = text_of(plot, "#plot-y-ticks").splitlines()
        assert "1000000" in [line.strip() for line in lines]


async def test_a_translucent_style_is_blended_with_the_background() -> None:
    async with drawn(lambda plot: plot.plot([0, 1], [0, 1])) as plot:
        solid = plot._style("$foreground").foreground
        faded = plot._style("$foreground 50%").foreground
        assert faded is not None and faded.a == 1
        assert faded != solid
        # The colour a cell gets, which has no alpha to carry it otherwise.
        assert plot._rich_style("$foreground 50%").color == faded.rich_color


async def test_y_follows_the_data_in_the_x_range_shown() -> None:
    def draw(plot: Plot) -> None:
        plot.plot(list(range(11)), list(range(11)))
        plot.x_limits = (0, 2)

    async with drawn(draw) as plot:
        margin = 2 * Plot.AUTO_MARGIN
        assert plot.y_range == pytest.approx((-margin, 2 + margin))


async def test_y_follows_x_as_it_is_zoomed() -> None:
    app = Harness()
    async with app.run_test(size=SIZE) as pilot:
        plot = app.query_one(Plot)
        plot.plot(XS, [x * x for x in XS])
        plot.focus()
        await settle(pilot, plot)
        before = plot.y_range
        await pilot.press("ctrl+equals_sign", "ctrl+equals_sign")
        await settle(pilot, plot)
        assert plot.y_range[1] < before[1]


async def test_with_nothing_in_view_y_follows_all_the_data() -> None:
    def draw(plot: Plot) -> None:
        plot.scatter([0, 10], [0, 1])
        plot.x_limits = (4, 6)

    async with drawn(draw) as plot:
        margin = Plot.AUTO_MARGIN
        assert plot.y_range == pytest.approx((-margin, 1 + margin))


async def test_a_bar_partly_in_view_counts() -> None:
    def draw(plot: Plot) -> None:
        plot.bar([1, 2, 3], [5, 1, 9], width=1)
        plot.x_limits = (2.6, 3.5)

    async with drawn(draw) as plot:
        assert plot.y_range[1] > 9


async def test_a_fixed_y_end_is_not_fitted() -> None:
    def draw(plot: Plot) -> None:
        plot.plot(list(range(11)), list(range(11)))
        plot.x_limits = (0, 2)
        plot.y_limits = (None, 10)

    async with drawn(draw) as plot:
        assert plot.y_range == pytest.approx((-Plot.AUTO_MARGIN * 10, 10))


async def test_error_bars_are_inside_the_range() -> None:
    async with drawn(
        lambda plot: plot.errorbar([1, 2], [1, 2], xerr=[0.5, 0.5], yerr=[1, 1])
    ) as plot:
        (x_low, x_high), (y_low, y_high) = plot.x_range, plot.y_range
        assert x_low < 0.5 and x_high > 2.5
        assert y_low < 0 and y_high > 3


# ------------------------------------------------------------ composability


async def test_a_plot_can_be_filled_in_before_it_is_mounted() -> None:
    class Composed(App[None]):
        def compose(self) -> ComposeResult:
            plot = Plot(x_label="time", legend="top-left")
            plot.plot(XS, SINE, label="sine")
            yield plot

    app = Composed()
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        plot = app.query_one(Plot)
        assert drawn_cells(plot) > 0
        assert "time" in text_of(plot, "#plot-x-axis")
        assert str(plot.query_one("#plot-legend", Static).content).endswith("sine")


async def test_setting_a_label_alone_redraws() -> None:
    app = Harness()
    async with app.run_test(size=SIZE) as pilot:
        plot = app.query_one(Plot)
        plot.plot(XS, SINE)
        await pilot.pause()
        plot.x_label = "seconds"
        plot.y_label = "volts"
        await pilot.pause()
        assert "seconds" in text_of(plot, "#plot-x-axis")
        assert "volts" in text_of(plot, "#plot-y-label")


async def test_labels_are_plain_text_not_markup() -> None:
    def draw(plot: Plot) -> None:
        plot.x_label = "Voltage [mV]"
        plot.y_label = "a[b]"
        plot.plot(XS, SINE, label="[bold]x[/]")
        plot.legend = "top-right"

    async with drawn(draw) as plot:
        assert "Voltage [mV]" in text_of(plot, "#plot-x-axis")
        assert "a[b]" in text_of(plot, "#plot-y-label")
        legend = plot.query_one("#plot-legend", Static)
        assert str(legend.content).endswith("[bold]x[/]")


async def test_the_grid_tracks_are_css() -> None:
    class Wide(App[None]):
        CSS = "Plot { grid-columns: 16 1fr; }"

        def compose(self) -> ComposeResult:
            yield Plot()

    app = Wide()
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        plot = app.query_one(Plot)
        assert plot.query_one("#plot-y-ticks").size.width == 16
        # Tick labels end two cells short of the axis, wherever it is.
        row = text_of(plot, "#plot-y-ticks").splitlines()
        assert max(len(line.rstrip()) for line in row) == 15


# ------------------------------------------------------------------ legend


@pytest.mark.parametrize("location", LOCATIONS)
async def test_the_legend_lists_labelled_datasets(location: LegendLocation) -> None:
    def draw(plot: Plot) -> None:
        plot.plot(XS, SINE, label="sine")
        plot.scatter(XS, SINE)
        plot.legend = location

    async with drawn(draw) as plot:
        legend = plot.query_one("#plot-legend", Static)
        assert legend.display
        assert str(legend.content).endswith(" sine")


async def test_no_legend_hides_it() -> None:
    def draw(plot: Plot) -> None:
        plot.plot(XS, SINE, label="sine")
        plot.legend = "top-left"
        plot.legend = None

    async with drawn(draw) as plot:
        assert not plot.query_one("#plot-legend").display


async def test_an_unknown_legend_location_is_refused() -> None:
    with pytest.raises(ValueError, match="legend"):
        Plot(legend="top")  # type: ignore[arg-type]


async def test_a_dragged_legend_reanchors_to_the_nearest_corner() -> None:
    app = Harness()
    async with app.run_test(size=SIZE) as pilot:
        plot = app.query_one(Plot)
        plot.plot(XS, SINE, label="sine")
        plot.legend = "top-left"
        await pilot.pause()
        legend = plot.query_one("#plot-legend")
        start = legend.region.offset

        grab = start + (1, 1)
        await pilot.mouse_down(app.screen, offset=grab)
        # Most of the way to the bottom-right corner, one cell at a time.
        for step in range(1, 41):
            await pilot.hover(app.screen, offset=grab + (step, step // 3))
        await pilot.mouse_up(app.screen, offset=grab + (40, 13))
        await pilot.pause()

        assert plot.legend == "bottom-right"
        assert not legend.has_class("-dragging")
        moved_to = legend.region.offset
        # Re-anchoring does not move it on screen...
        await pilot.resize_terminal(90, 30)
        await pilot.pause()
        # ...and from then on it keeps to the bottom-right corner.
        assert legend.region.offset - moved_to == (10, 6)
        assert moved_to != start


# ------------------------------------------------------------ zoom and pan


async def test_keyboard_zoom_narrows_the_x_range() -> None:
    app = Harness()
    async with app.run_test(size=SIZE) as pilot:
        plot = app.query_one(Plot)
        plot.x_limits = (0, 10)
        plot.focus()
        await pilot.pause()

        await pilot.press("plus")
        await pilot.pause()
        low, high = plot.x_range
        assert high - low < 10


async def test_reset_returns_to_the_limits() -> None:
    app = Harness()
    async with app.run_test(size=SIZE) as pilot:
        plot = app.query_one(Plot)
        plot.x_limits = (0, 10)
        plot.focus()
        await pilot.press("plus", "left", "r")
        await pilot.pause()
        assert plot.x_range == (0.0, 10.0)


async def test_the_wheel_zooms_around_the_pointer() -> None:
    app = Harness()
    async with app.run_test(size=SIZE) as pilot:
        plot = app.query_one(Plot)
        plot.plot([0, 10], [0, 10])
        await pilot.pause()
        area = canvas(plot)
        cell = (20, 7)
        viewport = plot._viewport()
        assert viewport is not None
        before = viewport.to_data(*cell)

        scroll_down(area, *cell)
        await pilot.pause()

        after = plot._viewport()
        assert after is not None
        assert plot.x_range != (0.0, 10.0)
        assert after.to_data(*cell) == pytest.approx(before)


async def test_range_changed_can_be_handled_by_selector() -> None:
    seen: list[Plot.RangeChanged] = []

    class Selecting(App[None]):
        def compose(self) -> ComposeResult:
            yield Plot(id="signal")

        @on(Plot.RangeChanged, "#signal")
        def _changed(self, event: Plot.RangeChanged) -> None:
            seen.append(event)

    app = Selecting()
    async with app.run_test(size=SIZE) as pilot:
        plot = app.query_one(Plot)
        plot.x_limits = (0, 10)
        plot.focus()
        await pilot.press("minus")
        await pilot.pause()
        assert len(seen) == 1
        assert seen[0].control is plot
        assert seen[0].x_range == plot.x_range


async def test_a_drag_keeps_panning_past_the_edge_of_the_plot() -> None:
    class Small(App[None]):
        CSS = "Plot { width: 40; height: 12; }"

        def compose(self) -> ComposeResult:
            yield Plot()

    app = Small()
    async with app.run_test(size=SIZE) as pilot:
        plot = app.query_one(Plot)
        plot.x_limits = (0, 10)
        await pilot.pause()
        area = canvas(plot)

        await pilot.mouse_down(area, offset=(10, 3))
        await pilot.hover(area, offset=(20, 3))
        inside = plot.x_range
        # Well past the plot's right edge, over the screen behind it.
        await pilot.hover(app.screen, offset=(70, 3))
        await pilot.mouse_up(app.screen, offset=(70, 3))
        await pilot.pause()

        assert inside[0] < 0
        assert plot.x_range[0] < inside[0]


async def test_without_pan_and_zoom_the_wheel_scrolls_what_is_behind() -> None:
    class Scrolling(App[None]):
        def compose(self) -> ComposeResult:
            with VerticalScroll():
                yield Plot(pan_and_zoom=None)
                yield Widget(classes="filler")

        CSS = "Plot { height: 20; } .filler { height: 100; }"

    app = Scrolling()
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        scroll = app.query_one(VerticalScroll)
        plot = app.query_one(Plot)
        scroll_down(canvas(plot), 10, 5)
        await pilot.pause()
        assert scroll.scroll_y > 0
        assert plot.x_range == (0.0, 1.0)


async def test_without_pan_and_zoom_the_keys_leave_the_footer() -> None:
    app = Harness()
    async with app.run_test(size=SIZE) as pilot:
        plot = app.query_one(Plot)
        plot.focus()
        await pilot.pause()
        assert plot.check_action("zoom_in", ())
        plot.pan_and_zoom = None
        assert not plot.check_action("zoom_in", ())
        await pilot.press("plus")
        assert plot.x_range == (0.0, 1.0)


async def test_an_unknown_pan_and_zoom_is_refused() -> None:
    with pytest.raises(ValueError, match="pan_and_zoom"):
        Plot(pan_and_zoom="z")  # type: ignore[arg-type]


class Keyed(App[None]):
    """A plot with only x to zoom and pan, and an app that wants ↑ for
    itself."""

    BINDINGS: ClassVar[list[BindingType]] = [("up", "went_up")]

    def __init__(self) -> None:
        super().__init__()
        self.went_up = 0

    def compose(self) -> ComposeResult:
        yield Plot(pan_and_zoom="x")

    def action_went_up(self) -> None:
        self.went_up += 1


async def test_x_alone_zooms_and_pans_x_alone() -> None:
    app = Keyed()
    async with app.run_test(size=SIZE) as pilot:
        plot = app.query_one(Plot)
        plot.x_limits = plot.y_limits = (0, 10)
        plot.focus()
        await pilot.press("plus", "left", "ctrl+shift+equals_sign")
        await settle(pilot, plot)
        low, high = plot.x_range
        assert high - low < 10 and low < 0.75
        assert plot.y_range == (0.0, 10.0)
        assert not plot.check_action("pan_up", ())
        assert not plot.check_action("zoom_y_in", ())
        assert plot.check_action("zoom_in", ())


async def test_a_key_for_an_axis_left_out_reaches_the_app() -> None:
    app = Keyed()
    async with app.run_test(size=SIZE) as pilot:
        plot = app.query_one(Plot)
        plot.y_limits = (0, 10)
        plot.focus()
        await pilot.press("up")
        await settle(pilot, plot)
        assert app.went_up == 1
        assert plot.y_range == (0.0, 10.0)


async def test_the_wheel_over_an_axis_left_out_scrolls_what_is_behind() -> None:
    class Scrolling(App[None]):
        def compose(self) -> ComposeResult:
            with VerticalScroll():
                yield Plot(pan_and_zoom="x")
                yield Widget(classes="filler")

        CSS = "Plot { height: 20; } .filler { height: 100; }"

    app = Scrolling()
    async with app.run_test(size=SIZE) as pilot:
        plot = app.query_one(Plot)
        plot.x_limits = (0, 10)
        await settle(pilot, plot)
        scroll = app.query_one(VerticalScroll)
        scroll_down(plot.query_one("#plot-y-ticks"), 1, 5)
        await pilot.pause()
        assert scroll.scroll_y > 0
        # Over the data, only x zooms.
        scroll_down(canvas(plot), 10, 5)
        await pilot.pause()
        assert plot.x_range != (0.0, 10.0)
        assert plot._y_view is None


async def test_panning_stops_at_a_bound_without_a_message() -> None:
    seen: list[Plot.RangeChanged] = []

    class Bounded(App[None]):
        def compose(self) -> ComposeResult:
            yield Plot()

        def on_plot_range_changed(self, event: Plot.RangeChanged) -> None:
            seen.append(event)

    app = Bounded()
    async with app.run_test(size=SIZE) as pilot:
        plot = app.query_one(Plot)
        plot.x_limits = (0, 10)
        plot.x_bounds = (0, None)
        plot.focus()
        await pilot.press("left")
        await settle(pilot, plot)
        assert plot.x_range == (0.0, 10.0)
        assert seen == []
        await pilot.press("right", "left", "left")
        await settle(pilot, plot)
        assert plot.x_range == (0.0, 10.0)
        assert len(seen) == 2


async def test_zooming_stops_at_the_span_limits() -> None:
    app = Harness()
    async with app.run_test(size=SIZE) as pilot:
        plot = app.query_one(Plot)
        plot.x_limits = (0, 10)
        plot.x_span = (5, 20)
        plot.focus()
        await pilot.press(*["ctrl+equals_sign"] * 10)
        low, high = plot.x_range
        assert high - low == pytest.approx(5)
        await pilot.press(*["ctrl+minus"] * 20)
        low, high = plot.x_range
        assert high - low == pytest.approx(20)


async def test_zooming_out_for_ever_stays_finite() -> None:
    app = Harness()
    async with app.run_test(size=SIZE) as pilot:
        plot = app.query_one(Plot)
        plot.x_formatter = DateTimeFormatter()
        plot.plot([1.7e9, 1.8e9], [0, 1])
        await settle(pilot, plot)
        for _ in range(6000):
            plot._zoom_centre(-Plot.KEYBOARD_ZOOM_FACTOR, "xy")
        await settle(pilot, plot)
        assert all(map(math.isfinite, plot.x_range + plot.y_range))
        for _ in range(400):
            plot._zoom_centre(Plot.KEYBOARD_ZOOM_FACTOR, "xy")
        await settle(pilot, plot)
        low, high = plot.x_range
        assert high > low


async def test_a_keymap_moves_a_plot_key() -> None:
    app = Harness()
    async with app.run_test(size=SIZE) as pilot:
        plot = app.query_one(Plot)
        plot.x_limits = (0, 10)
        app.set_keymap({"plot.reset_range": "home"})
        plot.focus()
        await pilot.press("plus", "r")
        assert plot.x_range != (0.0, 10.0)
        await pilot.press("home")
        assert plot.x_range == (0.0, 10.0)


# ------------------------------------------------------------------- theme


async def test_unstyled_datasets_take_theme_colours_in_turn() -> None:
    def draw(plot: Plot) -> None:
        plot.plot([0, 1], [0, 0])
        plot.plot([0, 1], [1, 1])

    async with drawn(draw) as plot:
        variables = plot.app.theme_variables
        first, second = (
            plot._style(style).rich_style.color.name.lower()  # type: ignore[union-attr]
            for style in (plot._datasets[0].style, plot._datasets[1].style)
        )
        assert first == variables["primary"].lower()
        assert second == variables["secondary"].lower()


async def test_a_theme_change_recolours_the_plot() -> None:
    app = Harness()
    async with app.run_test(size=SIZE) as pilot:
        plot = app.query_one(Plot)
        plot.plot([0, 1], [0.5, 0.5])
        await pilot.pause()

        def colours() -> set[str]:
            return {
                str(style.color)
                for row in canvas(plot)._styles
                for style in row
                if style is not None and style.color is not None
            }

        before = colours()
        app.theme = "textual-light"
        await pilot.pause()
        await pilot.pause()
        assert colours() != before
