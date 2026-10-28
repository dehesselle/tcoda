# Plot

A plotting widget: line, scatter, bar and error-bar plots with axes that scale
themselves, "nice" ticks (1, 2, 5, 10, 20, ...), a legend, and zooming and
panning by mouse and keyboard. A dataset is drawn either with full cells or in
one of three high-resolution modes, which pack 1×2, 2×2 or 2×4 dots into a
cell.

```python
from tcoda.plot import Plot


class MyApp(App[None]):
    def compose(self) -> ComposeResult:
        plot = Plot(x_label="time (s)", legend="top-right")
        plot.plot(xs, ys, hires_mode="braille", label="signal")
        plot.scatter(xs, noise, style="$error", label="noise")
        yield plot
```

## Data

- **`plot`, `scatter`, `errorbar`, `bar` and `vline` each add one dataset;
  `clear` removes them all.** Datasets are drawn in the order they were added,
  later ones on top. Data is any iterable of numbers, including NumPy arrays,
  though tcoda does not depend on NumPy. NaNs and infinities are dropped before
  drawing, along with anything that belongs to the same point: its error, its
  bar's width or style.
- **A plot takes data whenever it is handed it**, before or after it is
  mounted. Drawing is a function of the plot's state alone, and any change
  schedules one redraw, however many changes come before it runs.
- **`bar` takes names instead of numbers for `x`.** The bars go at 1, 2, 3, ...
  and the axis is labelled with the names, by setting `x_formatter` to a
  `CategoricalFormatter` and `x_ticks` to those positions. Those are ordinary
  reactives, so you can see and undo what it did.
- **`hires_mode` is `"halfblock"`, `"quadrant"`, `"braille"` or None** for full
  cells. A scatter or error-bar dataset in a high-resolution mode lights a
  single dot per point instead of drawing its `marker`.

## Axes

- **Everything about an axis is a reactive**: `x_label`, `x_limits`,
  `x_ticks` and `x_formatter`, and the same for y. Assigning one redraws.
- **`x_limits` is `(low, high)`, with None for an end that follows the data.**
  It is what the axis shows until the user zooms or pans. `x_range` is what it
  shows now, and `reset_range` (`r`) goes back to the limits.
- **A y end that follows the data follows the data in view**: the points
  inside `x_range`, or, for bars, those that reach into it. So narrowing x,
  by limits or by zooming, fits y to what is left. With nothing in view, y
  follows all the data. Error bars count up to their ends.
- **`x_ticks` set to None lets the formatter choose, and `[]` shows none.**
- **Labels are plain text, never markup**, so `"Voltage [mV]"` reads as written.
- **Formatters** choose ticks and label them: `NumericFormatter` (the
  default), `DurationFormatter` for seconds in a fitting unit (`0.5h`,
  `1.0h`, ...), `DateTimeFormatter` for Unix timestamps, and
  `CategoricalFormatter`. Subclass `AxisFormatter` for anything else; only
  `get_ticks` and `get_labels` need writing.
- **`DateTimeFormatter` puts ticks where a clock or calendar would**: every
  15 minutes, on the hour, every 3 or 6 hours, at midnight, on (every other)
  Monday, on the first of the month or quarter, on round years. Its labels say only what
  changes: `21:00`, then `Nov 15` at midnight, then `03:00`. The first tick
  also carries the date (or the year). It shows local time unless given a
  `tz`, and it never raises, whatever the range: there are no ticks before
  year 1 or after 9999. So plot real timestamps, not times shifted by the
  zone's offset.
- **`NumericFormatter` writes very large and very small numbers
  scientifically** (`1.5e20`, `2e-9`) once a label written out in full would
  be longer than `MAX_PLAIN_WIDTH` (8, a class attribute), and only if that
  is shorter. So zooming far out or in never grows the label column without
  end.
- **Ticks fit the plot's size.** y gets one per `Y_TICK_SPACING` rows (3) at
  most. x gets one per `X_TICK_SPACING` columns (8) at most, and fewer where
  their labels would come closer than two cells. Both are class attributes.
  A label near either end is moved inside the plot rather than cut off.
- **An end that follows the data goes `AUTO_MARGIN` (5%) past it**, so the
  highest and lowest values are not hidden under the frame. A fixed end goes
  exactly where it was put.
- **A lone value gets a range from its formatter's `around`**: half the value
  either side (-1 to 1 around zero), an hour either side for dates, half a
  category for categories. A fixed end stays fixed, so `y_limits=(0, None)`
  over all zeros shows 0 to 1.

## Look

- **Unstyled datasets take the theme's colours in turn**: `$primary`,
  `$secondary`, `$accent`, `$success`, `$warning`, `$error`, from
  `Plot.PALETTE`, a class attribute to override. Any `style` may name theme
  variables (`"bold $accent"`), and every style is resolved again on each
  redraw, so a theme change recolours the plot. A translucent colour
  (`"$foreground 60%"`) is blended with the plot's background.
- **The space around the data is CSS grid tracks, `auto` by default**:
  `grid-columns: auto 1fr` for the y tick labels on the left, as wide as the
  widest of them; `grid-rows: auto 1fr auto` for the y label above and the x
  tick labels and label below, with no room for an axis label that is not
  set. Override them on `Plot` for fixed sizes; y tick labels are then cropped
  to the space they get.
- **A tick at either end of a range gets no mark of its own**: it falls on a
  corner of the frame, which marks it already, and a mark would turn the
  corner into a junction. Its label is drawn as usual.
- **The component classes `plot--axis`, `plot--tick` and `plot--label`** style
  the frame and tick marks, the tick labels and the axis labels. The axis takes
  `$primary` while the plot has focus.

## Legend

- **`legend` is the corner it starts out in** (`"top-left"`, `"top-right"`,
  `"bottom-left"`, `"bottom-right"`), or None for no legend. It lists every
  dataset that has a `label`.
- **The legend can be dragged.** Letting go re-anchors it to the corner it is
  nearest, so a resize keeps it where it was put relative to that corner.
  Dragging it is allowed even with `pan_and_zoom=None`, since moving the
  legend changes nothing about the data shown.
- **`legend_content()` is the legend on one line**, as `Content` with each
  marker in its dataset's style: `⠒⠒⠒ sent  ⠒⠒⠒ received`. Put it in a border
  title, say, where it takes no room from the data.

## Zoom and pan

- **The wheel zooms around the pointer**: over the data, both axes; over a
  row or column of tick labels, that axis only. Dragging pans the same way.
  A drag captures the mouse, so it carries on past the edge of the plot.
- **The keys** are `+`/`-` (zoom), `ctrl+=`/`ctrl+-` for the x axis only,
  `ctrl+shift+=`/`ctrl+shift+-` for the y axis only, the arrow keys (pan)
  and `r` (reset). Each binding has an id (`plot.zoom_in`, `plot.pan_left`,
  ..., `plot.reset_range`), so an app's keymap (`App.set_keymap`) can move it
  to another key. A subclass that wants an action gone altogether returns
  False for it from `check_action`.
- **`pan_and_zoom` says which axes the user moves**: `"xy"` (the default),
  `"x"`, `"y"`, or None for neither. The keys of an axis left out leave the
  footer and pass through to the app (through `check_action`), so with `"x"`,
  `up` and `down` still reach whatever is behind the plot. The wheel over an
  axis left out passes through too, and with None it does everywhere, so a
  plot inside a scrolling container does not block the scroll.
  `invert_mouse_wheel=True` flips the wheel.
- **`x_bounds` and `x_span` keep zooming and panning in check** (and the same
  for y). `x_bounds=(first, last)` is how far the range may go, and
  `x_span=(shortest, longest)` how narrow and wide it may get; None leaves an
  end open. They clamp rather than refuse: panning stops at the wall, zooming out
  near it moves the range back inside, and zooming stops at the span around
  the pointer. Limits the app sets may lie beyond them; then they only stop
  the range from getting worse.
- **Every plot refuses a range floats cannot draw**: one reaching further
  than 1e300 from zero, or narrower than a billionth of its distance from
  zero. Zooming out or in for ever stops there instead of crashing.
- **Zooming, panning and resetting post `Plot.RangeChanged`**, which carries
  the new `x_range` and `y_range` and has a `control`, so
  `@on(Plot.RangeChanged, "#id")` works. A press that moves nothing, at a
  bound say, posts nothing. Assigning `x_limits` posts nothing either: the
  app already knows.
- **`Plot.RangeSettled` follows once the range has stayed put for
  `SETTLE_DELAY`** (0.15 s, a class attribute): one message for a whole burst
  of wheel notches or key presses, with the same fields. That is the moment
  to fetch data for the new range. `RangeChanged` still comes with every
  step, for whatever follows the range live.
- **Limits assigned before the range settles do not move it.** A refresh
  that lands mid-gesture would otherwise snap the view back under the user's
  hands. The new limits are still where `reset_range` goes; assigned after
  `RangeSettled`, they move the view as usual.

## Size and pointer

- **`data_size` is the area inside the frame**, in cells: how many points a
  line has room for (twice as many across, in braille), or how many buckets
  are worth fetching. It is `Size(0, 0)` until the plot is laid out.
- **`data_at(offset)` is the data point under a screen cell**, such as a
  mouse event's `screen_offset`, or None outside the frame. Hover readouts
  need nothing more:

  ```python
  def on_mouse_move(self, event: events.MouseMove) -> None:
      point = self.query_one(Plot).data_at(event.screen_offset)
      self.border_subtitle = "" if point is None else f"{point[0]:.1f}"
  ```

## Provenance

`tcoda.plot` is not originally tcoda's own code. It is
[textual-plot](https://github.com/davidfokkema/textual-plot) and the canvas it
draws on, [textual-hires-canvas](https://github.com/davidfokkema/textual-hires-canvas),
both by David Fokkema and MIT-licensed. They were brought in as they were at:

| Upstream | Version | Commit |
| --- | --- | --- |
| textual-plot | 0.10.1 | `319ca75` |
| textual-hires-canvas | 0.14.0 | `f73bffe` |

The code was absorbed, not vendored: it is changed here as tcoda needs, and
not kept in sync with upstream. The commit that imported it changed nothing
but headers and import paths, so `git diff` against that commit shows
everything tcoda has done since. By now that is most of it: the widget was
rebuilt as a native Textual one, and upstream's API (`PlotWidget`,
`set_xlabel`, `HiResMode.BRAILLE`, ...) is gone.

Every file in `src/tcoda/plot/` stays under the MIT license, as do the two
test files that came along (`tests/test_plot_formatters.py` and
`tests/test_plot_viewport.py`). The canvas (`_canvas.py`, `_hires.py`) is
private to `tcoda.plot` and depends on no private Textual module.
