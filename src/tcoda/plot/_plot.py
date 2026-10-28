# SPDX-FileCopyrightText: 2025 David Fokkema
# SPDX-FileCopyrightText: 2026 René de Hesselle <dehesselle@web.de>
#
# SPDX-License-Identifier: MIT

"""The plot widget: datasets, axes and a legend, zoomed and panned by mouse
and keyboard.

State is ordinary attributes and reactives, so a plot can be filled in
before it is mounted, and drawing is a pure function of that state: any change
schedules one redraw of every canvas, however many changes come before it
runs.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import replace
from itertools import pairwise
from math import isfinite
from numbers import Real
from typing import ClassVar, Literal, NamedTuple, get_args

from rich.style import Style as RichStyle
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Container
from textual.content import Content
from textual.errors import NoWidget
from textual.geometry import Offset, Region, Size
from textual.message import Message
from textual.reactive import var
from textual.style import Style
from textual.timer import Timer
from textual.widget import Widget

from tcoda.plot._canvas import Canvas
from tcoda.plot._datasets import (
    Bars,
    Dataset,
    ErrorBars,
    Line,
    Scatter,
    VLine,
    drop_non_finite,
)
from tcoda.plot._formatters import AxisFormatter, CategoricalFormatter, NumericFormatter
from tcoda.plot._hires import HiResMode
from tcoda.plot._legend import Legend, LegendLocation
from tcoda.plot._viewport import Range, Viewport, constrain, pan, zoom

#: An axis's limits; None leaves that end to follow the data.
type Limits = tuple[float | None, float | None]

_HIRES_MODES: tuple[HiResMode, ...] = get_args(HiResMode.__value__)
_LEGEND_LOCATIONS: tuple[LegendLocation, ...] = get_args(LegendLocation.__value__)

_ZOOM = Binding.Group("Zoom")
_PAN = Binding.Group("Pan")
#: The axes zooming and panning move: both, or just one.
type Axes = Literal["xy", "x", "y"]
_AXES: tuple[Axes, ...] = get_args(Axes.__value__)

#: The actions `pan_and_zoom` can turn off, and the axes each moves.
_VIEW_ACTIONS: dict[str, Axes] = {
    "zoom_in": "xy",
    "zoom_out": "xy",
    "zoom_x_in": "x",
    "zoom_x_out": "x",
    "zoom_y_in": "y",
    "zoom_y_out": "y",
    "pan_left": "x",
    "pan_right": "x",
    "pan_up": "y",
    "pan_down": "y",
    "reset_range": "xy",
}


class _XTick(NamedTuple):
    """An x tick as drawn: its column on the data canvas, and its label's."""

    x: int
    label: str
    #: The first and last column the label covers.
    start: int
    end: int


class _RangeMessage(Message):
    """The x and y range a plot shows.

    `Plot.RangeChanged` and `Plot.RangeSettled` share this rather than one
    extending the other: a handler for one would be called for both.
    """

    def __init__(self, plot: Plot, x_range: Range, y_range: Range) -> None:
        self.plot = plot
        self.x_range = x_range
        self.y_range = y_range
        super().__init__()

    @property
    def control(self) -> Plot:
        return self.plot


class Plot(Widget, can_focus=True):
    """Line, scatter, bar and error-bar plots, with axes that scale themselves.

    | Component class | Styles |
    | :- | :- |
    | `plot--axis` | The frame and its tick marks. |
    | `plot--tick` | The tick labels. |
    | `plot--label` | The axis labels. |
    """

    class RangeChanged(_RangeMessage):
        """The range shown changed: zoomed, panned, or reset to the limits."""

    class RangeSettled(_RangeMessage):
        """Zooming, panning or resetting came to rest: nothing moved the range
        for `SETTLE_DELAY` seconds. The time to fetch data for it."""

    COMPONENT_CLASSES: ClassVar[set[str]] = {"plot--axis", "plot--tick", "plot--label"}

    # The grid tracks are the space left of and around the data: tick labels
    # to the left, the y label above, tick labels and the x label below.
    # They are `auto`, sized to what is drawn in them; CSS overrides them.
    DEFAULT_CSS = """
    Plot {
        layout: grid;
        grid-size: 2 3;
        grid-columns: auto 1fr;
        grid-rows: auto 1fr auto;

        & > .plot--axis {
            color: $secondary;
        }
        &:focus > .plot--axis {
            color: $primary;
        }
        & > .plot--tick {
            color: $secondary;
            text-style: bold;
        }
        & > .plot--label {
            color: $primary;
            text-style: bold italic;
        }

        & > #plot-y-label, & > #plot-x-axis {
            column-span: 2;
        }
        & > #plot-area {
            layers: canvas legend;

            &.-legend-top-left { align: left top; }
            &.-legend-top-right { align: right top; }
            &.-legend-bottom-left { align: left bottom; }
            &.-legend-bottom-right { align: right bottom; }

            & > #plot-canvas {
                layer: canvas;
                width: 1fr;
                height: 1fr;
            }
            & > #plot-legend {
                layer: legend;
                width: auto;
                height: auto;
                margin: 1;
                border: solid $foreground;

                &.-dragging {
                    border: heavy $accent;
                }
            }
        }
    }
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        # Each has an id, so an app's keymap can move it to another key.
        Binding("plus", "zoom_in", "Zoom in", group=_ZOOM, id="plot.zoom_in"),
        Binding("minus", "zoom_out", "Zoom out", group=_ZOOM, id="plot.zoom_out"),
        Binding(
            "ctrl+equals_sign",
            "zoom_x_in",
            "Zoom x in",
            show=False,
            id="plot.zoom_x_in",
        ),
        Binding(
            "ctrl+minus", "zoom_x_out", "Zoom x out", show=False, id="plot.zoom_x_out"
        ),
        Binding(
            "ctrl+shift+equals_sign",
            "zoom_y_in",
            "Zoom y in",
            show=False,
            id="plot.zoom_y_in",
        ),
        Binding(
            "ctrl+shift+minus",
            "zoom_y_out",
            "Zoom y out",
            show=False,
            id="plot.zoom_y_out",
        ),
        Binding("left", "pan_left", "Pan left", group=_PAN, id="plot.pan_left"),
        Binding("right", "pan_right", "Pan right", group=_PAN, id="plot.pan_right"),
        Binding("up", "pan_up", "Pan up", group=_PAN, id="plot.pan_up"),
        Binding("down", "pan_down", "Pan down", group=_PAN, id="plot.pan_down"),
        Binding("r", "reset_range", "Reset", id="plot.reset_range"),
    ]

    #: How much one notch of the wheel zooms.
    MOUSE_ZOOM_FACTOR: ClassVar[float] = 0.05
    #: How much one key press zooms.
    KEYBOARD_ZOOM_FACTOR: ClassVar[float] = 0.15
    #: How many cells one key press pans.
    KEYBOARD_PAN_CELLS: ClassVar[float] = 2.0
    #: The fewest columns between x ticks; they are spaced wider still where
    #: their labels need it.
    X_TICK_SPACING: ClassVar[int] = 8
    #: The fewest rows between y ticks.
    Y_TICK_SPACING: ClassVar[int] = 3
    #: How much further than the data an end that follows it goes, as a
    #: fraction of the range, so the extremes stay clear of the frame.
    AUTO_MARGIN: ClassVar[float] = 0.05
    #: How long, in seconds, the range has to stay put after zooming, panning
    #: or resetting before `RangeSettled` is posted.
    SETTLE_DELAY: ClassVar[float] = 0.15
    #: Styles handed out, in turn, to datasets added without one.
    PALETTE: ClassVar[tuple[str, ...]] = (
        "$primary",
        "$secondary",
        "$accent",
        "$success",
        "$warning",
        "$error",
    )

    x_label: var[str] = var("", init=False)
    y_label: var[str] = var("", init=False)
    #: What the axes show, until zoomed or panned; `reset_range` comes back
    #: here.
    x_limits: var[Limits] = var((None, None), init=False)
    y_limits: var[Limits] = var((None, None), init=False)
    #: Where the ticks go: None lets the formatter choose, [] shows none.
    x_ticks: var[Sequence[float] | None] = var(None, init=False)
    y_ticks: var[Sequence[float] | None] = var(None, init=False)
    x_formatter: var[AxisFormatter] = var(NumericFormatter, init=False)
    y_formatter: var[AxisFormatter] = var(NumericFormatter, init=False)
    #: The corner the legend starts out in, or None for no legend.
    legend: var[LegendLocation | None] = var(None, init=False)
    #: The axes the mouse and keys zoom and pan, or None for neither. An
    #: axis left out stays as the limits have it, its keys leave the footer,
    #: and the wheel over its tick labels passes through to whatever is
    #: behind the plot (as it does everywhere, with None).
    pan_and_zoom: var[Axes | None] = var("xy", init=False, bindings=True)
    #: How far zooming and panning may take each axis: (first, last), None
    #: leaving that end open.
    x_bounds: var[Limits] = var((None, None), init=False)
    y_bounds: var[Limits] = var((None, None), init=False)
    #: The shortest and longest range zooming may reach on each axis, None
    #: leaving that end open.
    x_span: var[Limits] = var((None, None), init=False)
    y_span: var[Limits] = var((None, None), init=False)
    #: Whether scrolling down zooms out instead of in.
    invert_mouse_wheel: var[bool] = var(False, init=False)

    def __init__(
        self,
        *,
        x_label: str = "",
        y_label: str = "",
        legend: LegendLocation | None = None,
        pan_and_zoom: Axes | None = "xy",
        invert_mouse_wheel: bool = False,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        """
        Args:
            x_label: The x axis label.
            y_label: The y axis label.
            legend: The corner the legend starts out in, or None for none.
            pan_and_zoom: The axes the mouse and keys zoom and pan, or None.
            invert_mouse_wheel: Whether scrolling down zooms out.
            name: The widget's name.
            id: DOM id.
            classes: CSS classes.
            disabled: Whether the widget starts out disabled.
        """
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self.set_reactive(Plot.x_label, x_label)
        self.set_reactive(Plot.y_label, y_label)
        self.set_reactive(Plot.legend, self.validate_legend(legend))
        self.set_reactive(Plot.pan_and_zoom, self.validate_pan_and_zoom(pan_and_zoom))
        self.set_reactive(Plot.invert_mouse_wheel, invert_mouse_wheel)

        self._datasets: list[Dataset] = []
        #: How many datasets have taken a style from `PALETTE` so far.
        self._unstyled = 0
        #: The range zooming and panning left, or None to follow the limits.
        self._x_view: Range | None = None
        self._y_view: Range | None = None
        self._redraw_pending = False
        #: Counts down to `RangeSettled`, from the last move of the range.
        self._settle_timer: Timer | None = None
        #: Styles resolved against the theme, for the redraw in progress.
        self._styles: dict[str, Style] = {}
        #: What a left-button drag is moving, while one is: the legend, or
        #: the axes it pans.
        self._drag: Literal["legend"] | Axes | None = None
        #: Where on screen the drag was last seen; moves are measured from
        #: here rather than taken from `MouseMove.delta`.
        self._drag_from = Offset()
        self._legend_offset = Offset()

        self._y_label_canvas = Canvas(id="plot-y-label")
        self._y_ticks_canvas = Canvas(id="plot-y-ticks")
        self._canvas = Canvas(id="plot-canvas")
        self._x_axis_canvas = Canvas(id="plot-x-axis")
        self._legend = Legend(id="plot-legend")
        self._area = Container(id="plot-area")
        self._place_legend(self.legend, Offset())
        self._size_label_rows()

    def compose(self) -> ComposeResult:
        yield self._y_label_canvas
        yield self._y_ticks_canvas
        with self._area:
            yield self._canvas
            yield self._legend
        yield self._x_axis_canvas

    def on_mount(self) -> None:
        self._schedule_redraw()

    # ------------------------------------------------------------ datasets

    def plot(
        self,
        x: Iterable[float],
        y: Iterable[float],
        *,
        style: str | None = None,
        hires_mode: HiResMode | None = None,
        label: str | None = None,
    ) -> None:
        """Add a line through the points, in the order given.

        Args:
            x: The points' x values.
            y: The points' y values.
            style: The line's style; theme variables (``"$accent"``) work.
                Defaults to the next one in `PALETTE`.
            hires_mode: Draw at sub-cell resolution, or None for full cells.
            label: The line's legend entry; without one it has none.
        """
        x, y = drop_non_finite(x, y)
        self._add(
            Line(
                x=x,
                y=y,
                style=self._next_style(style),
                hires_mode=_check_mode(hires_mode),
                label=label,
            )
        )

    def scatter(
        self,
        x: Iterable[float],
        y: Iterable[float],
        *,
        marker: str = "o",
        style: str | None = None,
        hires_mode: HiResMode | None = None,
        label: str | None = None,
    ) -> None:
        """Add a marker at each point.

        Args:
            x: The points' x values.
            y: The points' y values.
            marker: The character drawn at each point. A high-resolution mode
                lights a single sub-cell instead.
            style: As for `plot`.
            hires_mode: As for `plot`.
            label: As for `plot`.
        """
        x, y = drop_non_finite(x, y)
        self._add(
            Scatter(
                x=x,
                y=y,
                marker=marker,
                style=self._next_style(style),
                hires_mode=_check_mode(hires_mode),
                label=label,
            )
        )

    def errorbar(
        self,
        x: Iterable[float],
        y: Iterable[float],
        *,
        xerr: Iterable[float] | None = None,
        yerr: Iterable[float] | None = None,
        marker: str | None = None,
        style: str | None = None,
        hires_mode: HiResMode | None = None,
        label: str | None = None,
    ) -> None:
        """Add points with error bars, drawn at half-cell resolution.

        The points are drawn after the bars, so a bar never hides one.

        Args:
            x: The points' x values.
            y: The points' y values.
            xerr: How far each point's bar reaches either side, or None.
            yerr: How far each point's bar reaches up and down, or None.
            marker: The character drawn at each point. None draws ┼ where a
                point has both bars and · where it has fewer. A
                high-resolution mode lights a single sub-cell instead.
            style: The style of the bars and points, as for `plot`.
            hires_mode: As for `plot`.
            label: As for `plot`.
        """
        x = list(x)
        zeros = [0.0] * len(x)
        x, y, xerr_list, yerr_list = drop_non_finite(
            x, y, zeros if xerr is None else xerr, zeros if yerr is None else yerr
        )
        self._add(
            ErrorBars(
                x=x,
                y=y,
                xerr=xerr_list,
                yerr=yerr_list,
                marker=marker,
                style=self._next_style(style),
                hires_mode=_check_mode(hires_mode),
                label=label,
            )
        )

    def bar(
        self,
        x: Iterable[float] | Iterable[str],
        y: Iterable[float],
        *,
        width: float | Iterable[float] | None = None,
        style: str | Sequence[str] | None = None,
        hires_mode: HiResMode | None = None,
        label: str | None = None,
    ) -> None:
        """Add bars rising from 0 to each y value.

        Names instead of numbers for `x` put the bars at 1, 2, 3, ... and
        label the x axis with the names, by setting `x_formatter` to a
        `CategoricalFormatter` and `x_ticks` to those positions.

        Args:
            x: The bars' centres, or their names.
            y: The bars' heights.
            width: The bars' width in data units, one for all or one per bar.
                Defaults to 80% of the closest spacing between bars.
            style: One style for all bars, or one per bar (the legend shows
                the first). Defaults to the next one in `PALETTE`.
            hires_mode: As for `plot`.
            label: As for `plot`.
        """
        xs: list = list(x)
        if xs and isinstance(xs[0], str):
            names, xs = xs, [float(i) for i in range(1, len(xs) + 1)]
            self.x_formatter = CategoricalFormatter(names)
            self.x_ticks = xs
        ys = list(y)
        widths = (
            None
            if width is None
            else [width] * len(xs)
            if isinstance(width, Real)
            else _same_length(list(width), len(xs), "width")
        )
        styles = (
            None
            if style is None or isinstance(style, str)
            else _same_length(list(style), len(xs), "style")
        )

        # Per-bar widths and styles go wherever their bar goes.
        keep = [
            i
            for i, (xi, yi) in enumerate(zip(xs, ys, strict=True))
            if isfinite(xi) and isfinite(yi)
        ]
        xs = [float(xs[i]) for i in keep]
        if widths is None:
            # Narrower than the closest gap, so neighbours never merge.
            gap = min((b - a for a, b in pairwise(sorted(xs))), default=1.0)
            widths = [0.8 * gap] * len(xs)
        else:
            widths = [float(widths[i]) for i in keep]
        bar_styles = None if styles is None else [styles[i] for i in keep]
        self._add(
            Bars(
                x=xs,
                y=[float(ys[i]) for i in keep],
                width=widths,
                style=(
                    bar_styles[0]
                    if bar_styles
                    else self._next_style(style if isinstance(style, str) else None)
                ),
                bar_styles=bar_styles,
                hires_mode=_check_mode(hires_mode),
                label=label,
            )
        )

    def vline(
        self, x: float, *, style: str | None = None, label: str | None = None
    ) -> None:
        """Add a vertical line at `x`, from the bottom of the frame to the top.

        Args:
            x: Where the line crosses the x axis.
            style: As for `plot`.
            label: As for `plot`.
        """
        self._add(VLine(x=x, style=self._next_style(style), label=label))

    def clear(self) -> None:
        """Remove every dataset. Limits, labels and the like stay as they are."""
        self._datasets = []
        self._unstyled = 0
        self._schedule_redraw()

    def _add(self, dataset: Dataset) -> None:
        # Datasets draw in the order they were added, later ones on top.
        self._datasets.append(dataset)
        self._schedule_redraw()

    def _next_style(self, style: str | None) -> str:
        if style is not None:
            return style
        style = self.PALETTE[self._unstyled % len(self.PALETTE)]
        self._unstyled += 1
        return style

    # --------------------------------------------------------------- range

    @property
    def x_range(self) -> Range:
        """The x range shown: `x_limits` with any open end following the
        data, or wherever zooming and panning took it since."""
        return self._range(self._x_view, self.x_limits, 0)

    @property
    def y_range(self) -> Range:
        """The y range shown; see `x_range`."""
        return self._range(self._y_view, self.y_limits, 1)

    def _range(self, view: Range | None, limits: Limits, axis: int) -> Range:
        formatter = self.x_formatter if axis == 0 else self.y_formatter
        if view is not None:
            low, high = view
            if low == high:
                low, high = formatter.around(low)
            return float(low), float(high)

        values = self._extent(axis)
        fixed_low, fixed_high = limits
        followed = bool(values)
        if not values:
            # Nothing to follow: an open end meets the fixed one, or with
            # both open, the axis shows 0 to 1.
            values = (
                [0.0, 1.0]
                if fixed_low is None and fixed_high is None
                else [fixed_low if fixed_high is None else fixed_high]
            )
        low = min(values) if fixed_low is None else fixed_low
        high = max(values) if fixed_high is None else fixed_high
        if fixed_low is None and fixed_high is not None:
            low = min(low, high)
        if fixed_high is None and fixed_low is not None:
            high = max(low, high)

        if low == high:
            # A single value still needs a range to sit in, but a fixed end
            # stays where it was put.
            around_low, around_high = formatter.around(low)
            if fixed_low is None or fixed_high is not None:
                low = around_low
            if fixed_high is None or fixed_low is not None:
                high = around_high
        elif followed:
            margin = (high - low) * self.AUTO_MARGIN
            if fixed_low is None:
                low -= margin
            if fixed_high is None:
                high += margin
        return float(low), float(high)

    def _extent(self, axis: int) -> list[float]:
        """The values an end of the axis that follows the data follows.

        For y, those of the data in the x range shown, so zooming in on x
        fits y to what is left; or all of it, while none is in view.
        """
        if axis == 0:
            return [x for dataset in self._datasets for x in dataset.extent()[0]]
        x_range = self.x_range
        in_view = [y for dataset in self._datasets for y in dataset.extent(x_range)[1]]
        return in_view or [y for dataset in self._datasets for y in dataset.extent()[1]]

    def validate_x_limits(self, limits: Limits) -> Limits:
        low, high = limits
        return low, high

    validate_y_limits = validate_x_limits

    def watch_x_limits(self) -> None:
        # While the user is still zooming or panning, new limits only change
        # where a reset goes; snapping back mid-gesture would undo them.
        if self._settle_timer is None:
            self._x_view = None
        self._schedule_redraw()

    def watch_y_limits(self) -> None:
        if self._settle_timer is None:
            self._y_view = None
        self._schedule_redraw()

    def _viewport(self) -> Viewport | None:
        """Where data goes on the canvas, or None while it is too small to
        hold any inside its frame."""
        width, height = self._canvas.size
        if width < 3 or height < 3:
            return None
        return Viewport(self.x_range, self.y_range, Region(1, 1, width - 2, height - 2))

    @property
    def data_size(self) -> Size:
        """The cells data is drawn in, inside the frame: how many points a
        line has room for, say. Empty until the plot is laid out."""
        viewport = self._viewport()
        return Size(0, 0) if viewport is None else viewport.region.size

    def data_at(self, offset: Offset) -> tuple[float, float] | None:
        """The data point under a cell of the screen, such as a mouse event's
        `screen_offset`; None outside the frame.

        The point is the cell's centre, to a cell's precision.
        """
        if (viewport := self._viewport()) is None:
            return None
        x, y = offset - self._canvas.content_region.offset
        if not viewport.region.contains(x, y):
            return None
        return viewport.to_data(x, y)

    # ------------------------------------------------------------- drawing

    def _schedule_redraw(self) -> None:
        if self._redraw_pending or not self.is_running:
            # Already on its way; or not mounted yet, and on_mount will ask.
            return
        self._redraw_pending = True
        self.call_later(self._redraw)

    # Anything else that changes the picture just asks for a redraw.
    watch_x_ticks = watch_y_ticks = _schedule_redraw
    watch_x_formatter = watch_y_formatter = _schedule_redraw

    def watch_x_label(self) -> None:
        self._size_label_rows()
        self._schedule_redraw()

    watch_y_label = watch_x_label

    def _size_label_rows(self) -> None:
        """Make room for the axis labels there are, and none for the rest."""
        # The y label, and a row between it and the top tick label.
        self._y_label_canvas.content_height = 2 if self.y_label else 0
        # The tick labels, then a row and the x label.
        self._x_axis_canvas.content_height = 3 if self.x_label else 1
        self._y_label_canvas.refresh(layout=True)
        self._x_axis_canvas.refresh(layout=True)

    def _on_canvas_resized(self, event: Canvas.Resized) -> None:
        event.stop()
        self._schedule_redraw()

    def notify_style_update(self) -> None:
        # Focus, hover and the theme all come through here.
        super().notify_style_update()
        self._schedule_redraw()

    def _redraw(self) -> None:
        self._redraw_pending = False
        self._styles.clear()
        canvases = (
            self._y_label_canvas,
            self._y_ticks_canvas,
            self._canvas,
            self._x_axis_canvas,
        )
        for canvas in canvases:
            canvas.reset()
        if (viewport := self._viewport()) is not None:
            y_ticks = self._y_ticks_in_view(viewport)
            self._fit_y_ticks_column([label for _, label in y_ticks])
            for dataset in self._datasets:
                dataset.draw(self._canvas, viewport, self._rich_style)
            self._draw_frame(viewport)
            self._draw_x_ticks(viewport)
            self._draw_y_ticks(viewport, y_ticks)
        self._draw_labels()
        self._legend.show(
            (dataset.legend_marker(), self._style(dataset.style), dataset.label)
            for dataset in self._datasets
            if dataset.label is not None
        )
        for canvas in canvases:
            canvas.refresh()

    def _style(self, style: str) -> Style:
        if (resolved := self._styles.get(style)) is None:
            resolved = Style.parse(style, self.app.theme_variables)
            if (colour := resolved.foreground) is not None and colour.a < 1:
                # A cell's colour has no alpha, so blend it with what is
                # behind the plot here.
                _, background = self.background_colors
                resolved = replace(resolved, foreground=background + colour)
            self._styles[style] = resolved
        return resolved

    def _rich_style(self, style: str) -> RichStyle:
        return self._style(style).rich_style

    def _draw_frame(self, viewport: Viewport) -> None:
        style = self.get_component_rich_style("plot--axis")
        region = viewport.region
        self._canvas.draw_box(0, 0, region.right, region.bottom, style)
        for dataset in self._datasets:
            for x, y, quad in dataset.frame_marks(viewport):
                self._canvas.add_box(x, y, quad, style)

    def _x_ticks_in_view(self, viewport: Viewport) -> list[_XTick]:
        """The x ticks to draw: as many as `X_TICK_SPACING` allows, fewer
        where their labels would otherwise come closer than two cells."""
        if self.x_ticks is not None:
            ticks = list(self.x_ticks)
            return self._place_x_ticks(
                viewport, ticks, self.x_formatter.get_labels(ticks)
            )
        low, high = viewport.x_range
        most = max(1, viewport.region.width // self.X_TICK_SPACING)
        placed: list[_XTick] = []
        for max_ticks in range(most, 0, -1):
            ticks, labels = self.x_formatter.get_ticks_and_labels(low, high, max_ticks)
            placed = self._place_x_ticks(viewport, ticks, labels)
            if all(b.start - a.end > 2 for a, b in pairwise(placed)):
                break
        return placed

    def _place_x_ticks(
        self, viewport: Viewport, ticks: Sequence[float], labels: Sequence[str]
    ) -> list[_XTick]:
        low, high = viewport.x_range
        categorical = isinstance(self.x_formatter, CategoricalFormatter)
        # Labels may start as far left as the axis canvas does, under the y
        # tick labels, but end no further right than the frame.
        first = self._x_axis_canvas.region.x - self._canvas.region.x
        last = viewport.region.right
        placed = []
        for tick, label in sorted(zip(ticks, labels)):
            if not low <= tick <= high:
                continue
            x, _ = viewport.to_cell(tick, 0.0)
            if tick == low and not categorical:
                # The start of the range sits on the frame's corner.
                x -= 1
            # Centred on the tick where there is room, else moved inside.
            start = x - (len(label) - 1) // 2
            start = max(first, min(start, last - len(label) + 1))
            placed.append(_XTick(x, label, start, start + len(label) - 1))
        return placed

    def _draw_x_ticks(self, viewport: Viewport) -> None:
        axis_style = self.get_component_rich_style("plot--axis")
        tick_style = self.get_component_rich_style("plot--tick")
        # Labels may reach out under the y axis, so they go on a canvas that
        # starts further left than the data's.
        shift = self._canvas.region.x - self._x_axis_canvas.region.x
        right, bottom = viewport.region.right, viewport.region.bottom
        for tick in self._x_ticks_in_view(viewport):
            # A tick at either end of the range falls on a corner, which a
            # mark would turn into a junction; the corner marks it already.
            if 0 < tick.x < right:
                self._canvas.add_box(tick.x, 0, (2, 0, 0, 0), axis_style)
                self._canvas.add_box(tick.x, bottom, (0, 0, 2, 0), axis_style)
            self._x_axis_canvas.write_text(
                tick.start + shift, 0, tick.label, tick_style
            )

    def _y_ticks_in_view(self, viewport: Viewport) -> list[tuple[int, str]]:
        """The y ticks to draw, one per `Y_TICK_SPACING` rows at most, as
        (row on the data canvas, label)."""
        low, high = viewport.y_range
        if self.y_ticks is not None:
            ticks = list(self.y_ticks)
            labels = self.y_formatter.get_labels(ticks)
        else:
            ticks, labels = self.y_formatter.get_ticks_and_labels(
                low, high, max(1, viewport.region.height // self.Y_TICK_SPACING)
            )
        rows = []
        for tick, label in zip(ticks, labels):
            if not low <= tick <= high:
                continue
            _, y = viewport.to_cell(0.0, tick)
            if tick == low:
                # The bottom of the range sits on the frame's corner.
                y += 1
            rows.append((y, label))
        return rows

    def _fit_y_ticks_column(self, labels: Sequence[str]) -> None:
        """Size the tick labels' column to the widest of them, with a cell
        either side, for when CSS leaves it `auto`."""
        width = max(map(len, labels), default=0) + 2
        if width != self._y_ticks_canvas.content_width:
            self._y_ticks_canvas.content_width = width
            # The canvases resize, which draws again at the new size.
            self._y_ticks_canvas.refresh(layout=True)

    def _draw_y_ticks(
        self, viewport: Viewport, ticks: Sequence[tuple[int, str]]
    ) -> None:
        axis_style = self.get_component_rich_style("plot--axis")
        tick_style = self.get_component_rich_style("plot--tick")
        width = self._y_ticks_canvas.size.width
        shift = self._canvas.region.y - self._y_ticks_canvas.region.y
        right, bottom = viewport.region.right, viewport.region.bottom
        for y, label in ticks:
            # As for x: no mark on a corner.
            if 0 < y < bottom:
                self._canvas.add_box(0, y, (0, 0, 0, 2), axis_style)
                self._canvas.add_box(right, y, (0, 2, 0, 0), axis_style)
            # Cropped, where CSS makes the column narrower, to leave a gap
            # before the axis.
            self._y_ticks_canvas.write_text(
                width - 2, y + shift, label[: width - 1], tick_style, "right"
            )

    def _draw_labels(self) -> None:
        style = self.get_component_rich_style("plot--label")
        centre = (
            self._canvas.region.x
            - self._x_axis_canvas.region.x
            + self._canvas.size.width // 2
        )
        self._x_axis_canvas.write_text(centre, 2, self.x_label, style, "center")
        self._y_label_canvas.write_text(
            self._y_ticks_canvas.size.width - 2, 0, self.y_label, style, "center"
        )

    # -------------------------------------------------------------- legend

    def legend_content(self) -> Content:
        """The legend on one line, each entry's marker in its style, for a
        border title say. Needs the plot mounted, for the theme's colours."""
        return Content("  ").join(
            Content.assemble(
                (dataset.legend_marker().strip(), self._style(dataset.style)),
                " ",
                dataset.label,
            )
            for dataset in self._datasets
            if dataset.label is not None
        )

    def validate_legend(self, location: LegendLocation | None) -> LegendLocation | None:
        if location is not None and location not in _LEGEND_LOCATIONS:
            raise ValueError(
                f"legend must be one of {', '.join(_LEGEND_LOCATIONS)} or None,"
                f" not {location!r}"
            )
        return location

    def watch_legend(self, location: LegendLocation | None) -> None:
        self._place_legend(location, Offset())

    def _place_legend(self, location: LegendLocation | None, offset: Offset) -> None:
        for corner in _LEGEND_LOCATIONS:
            self._area.set_class(corner == location, f"-legend-{corner}")
        self._legend.display = location is not None
        self._legend_offset = offset
        self._legend.styles.offset = (offset.x, offset.y)

    # ---------------------------------------------------------------- view

    def validate_pan_and_zoom(self, axes: Axes | None) -> Axes | None:
        if axes is not None and axes not in _AXES:
            raise ValueError(
                f"pan_and_zoom must be one of {', '.join(_AXES)} or None, not {axes!r}"
            )
        return axes

    def _allowed(self, axes: Axes) -> Axes | None:
        """Those of `axes` that `pan_and_zoom` lets the user move."""
        allowed = "".join(axis for axis in axes if axis in (self.pan_and_zoom or ""))
        return allowed or None  # type: ignore[return-value]

    def _zoom(self, x: float, y: float, factor: float, axes: Axes) -> None:
        before = self.x_range, self.y_range
        allowed = self._allowed(axes) or ""
        if "x" in allowed:
            self._move_x(zoom(before[0], x, factor), before[0], x)
        if "y" in allowed:
            self._move_y(zoom(before[1], y, factor), before[1], y)
        self._range_changed(before)

    def _zoom_centre(self, factor: float, axes: Axes) -> None:
        (x_min, x_max), (y_min, y_max) = self.x_range, self.y_range
        self._zoom((x_min + x_max) / 2, (y_min + y_max) / 2, factor, axes)

    def _pan(self, cells_x: float, cells_y: float) -> None:
        """Move the data by this many cells, right and down."""
        if (viewport := self._viewport()) is None:
            return
        before = self.x_range, self.y_range
        allowed = self.pan_and_zoom or ""
        across, up = viewport.data_per_cell()
        if cells_x and "x" in allowed:
            self._move_x(pan(before[0], -across * cells_x), before[0])
        if cells_y and "y" in allowed:
            self._move_y(pan(before[1], up * cells_y), before[1])
        self._range_changed(before)

    def _move_x(self, new: Range, old: Range, anchor: float | None = None) -> None:
        """Zoom or pan x towards `new`, as far as its bounds and span allow."""
        new = constrain(new, old, self.x_bounds, self.x_span, anchor)
        if new != old:
            self._x_view = new

    def _move_y(self, new: Range, old: Range, anchor: float | None = None) -> None:
        """Zoom or pan y towards `new`, as far as its bounds and span allow."""
        new = constrain(new, old, self.y_bounds, self.y_span, anchor)
        if new != old:
            self._y_view = new

    def _range_changed(self, before: tuple[Range, Range]) -> None:
        """Tell the app and redraw, if the range moved at all; at a bound or
        span limit, it may not have."""
        if (self.x_range, self.y_range) == before:
            return
        self.post_message(self.RangeChanged(self, self.x_range, self.y_range))
        self._schedule_redraw()
        if self._settle_timer is not None:
            self._settle_timer.stop()
        self._settle_timer = self.set_timer(self.SETTLE_DELAY, self._settled)

    def _settled(self) -> None:
        self._settle_timer = None
        self.post_message(self.RangeSettled(self, self.x_range, self.y_range))

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool:
        axes = _VIEW_ACTIONS.get(action)
        return axes is None or self._allowed(axes) is not None

    def action_zoom_in(self) -> None:
        self._zoom_centre(self.KEYBOARD_ZOOM_FACTOR, "xy")

    def action_zoom_out(self) -> None:
        self._zoom_centre(-self.KEYBOARD_ZOOM_FACTOR, "xy")

    def action_zoom_x_in(self) -> None:
        self._zoom_centre(self.KEYBOARD_ZOOM_FACTOR, "x")

    def action_zoom_x_out(self) -> None:
        self._zoom_centre(-self.KEYBOARD_ZOOM_FACTOR, "x")

    def action_zoom_y_in(self) -> None:
        self._zoom_centre(self.KEYBOARD_ZOOM_FACTOR, "y")

    def action_zoom_y_out(self) -> None:
        self._zoom_centre(-self.KEYBOARD_ZOOM_FACTOR, "y")

    def action_pan_left(self) -> None:
        self._pan(self.KEYBOARD_PAN_CELLS, 0)

    def action_pan_right(self) -> None:
        self._pan(-self.KEYBOARD_PAN_CELLS, 0)

    def action_pan_up(self) -> None:
        self._pan(0, self.KEYBOARD_PAN_CELLS)

    def action_pan_down(self) -> None:
        self._pan(0, -self.KEYBOARD_PAN_CELLS)

    def action_reset_range(self) -> None:
        """Go back to `x_limits` and `y_limits`."""
        before = self.x_range, self.y_range
        self._x_view = self._y_view = None
        self._range_changed(before)

    # --------------------------------------------------------------- mouse

    def _part_at(self, event: events.MouseEvent) -> Widget | None:
        """The widget under the pointer.

        Not `event.widget`: events from the terminal carry none, only ones a
        test pilot makes up do.
        """
        try:
            widget, _ = self.screen.get_widget_at(event.screen_x, event.screen_y)
        except NoWidget:
            return None
        return widget

    def _axes_at(self, widget: Widget | None) -> Axes | None:
        """Which axes the mouse moves over `widget`: both over the data, one
        over its tick labels."""
        if widget is self._canvas or widget is self._legend:
            return "xy"
        if widget is self._x_axis_canvas:
            return "x"
        if widget is self._y_ticks_canvas:
            return "y"
        return None

    def _on_mouse_scroll_down(self, event: events.MouseScrollDown) -> None:
        self._zoom_at_pointer(event, self.MOUSE_ZOOM_FACTOR)

    def _on_mouse_scroll_up(self, event: events.MouseScrollUp) -> None:
        self._zoom_at_pointer(event, -self.MOUSE_ZOOM_FACTOR)

    def _zoom_at_pointer(self, event: events.MouseEvent, factor: float) -> None:
        """Zoom keeping the data under the pointer where it is."""
        if (
            (axes := self._axes_at(self._part_at(event))) is None
            or (axes := self._allowed(axes)) is None
            or (viewport := self._viewport()) is None
        ):
            # Not for the plot: let it bubble, to a scrolling container say.
            return
        event.stop()
        if self.invert_mouse_wheel:
            factor = -factor
        origin = self._canvas.content_region.offset
        x, y = viewport.to_data(event.screen_x - origin.x, event.screen_y - origin.y)
        self._zoom(x, y, factor, axes)

    def _on_mouse_down(self, event: events.MouseDown) -> None:
        if event.button != 1:
            return
        part = self._part_at(event)
        if part is self._legend:
            # Moving the legend is not panning, so it is always allowed.
            self._drag = "legend"
            self._legend.add_class("-dragging")
        elif (axes := self._axes_at(part)) and (axes := self._allowed(axes)):
            self._drag = axes
        else:
            return
        self._drag_from = event.screen_offset
        # Captured, a drag carries on past the edge of the plot.
        self.capture_mouse()
        event.stop()

    def _on_mouse_move(self, event: events.MouseMove) -> None:
        if self._drag is None:
            return
        event.stop()
        delta = event.screen_offset - self._drag_from
        self._drag_from = event.screen_offset
        if self._drag == "legend":
            self._legend_offset += delta
            self._legend.styles.offset = (self._legend_offset.x, self._legend_offset.y)
        else:
            self._pan(
                delta.x if "x" in self._drag else 0,
                delta.y if "y" in self._drag else 0,
            )

    def _on_mouse_up(self, event: events.MouseUp) -> None:
        if self._drag is None:
            return
        event.stop()
        self._end_drag()
        self.release_mouse()

    def _on_mouse_release(self, event: events.MouseRelease) -> None:
        # The capture was taken away mid-drag.
        self._end_drag()

    def _end_drag(self) -> None:
        if self._drag == "legend":
            self._legend.remove_class("-dragging")
            # Re-anchor to the nearest corner, so it stays put relative to
            # that corner when the plot is resized.
            location, offset = self._legend.nearest_corner(self._area.content_region)
            self.set_reactive(Plot.legend, location)
            self._place_legend(location, offset)
        self._drag = None


def _check_mode(hires_mode: HiResMode | None) -> HiResMode | None:
    if hires_mode is not None and hires_mode not in _HIRES_MODES:
        raise ValueError(
            f"hires_mode must be one of {', '.join(_HIRES_MODES)} or None,"
            f" not {hires_mode!r}"
        )
    return hires_mode


def _same_length[T](values: list[T], count: int, name: str) -> list[T]:
    if len(values) != count:
        raise ValueError(f"{name} has {len(values)} values for {count} bars")
    return values
