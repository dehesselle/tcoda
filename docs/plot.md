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
- **`x_ticks` set to None lets the formatter choose, and `[]` shows none.**
- **Labels are plain text, never markup**, so `"Voltage [mV]"` reads as written.
- **Formatters** choose ticks and label them: `NumericFormatter` (the
  default), `DurationFormatter` for seconds in a fitting unit (`0.5h`,
  `1.0h`, ...), `DateTimeFormatter` for Unix timestamps, and
  `CategoricalFormatter`. Subclass `AxisFormatter` for anything else; only
  `get_ticks` and `get_labels` need writing.
- **`DateTimeFormatter` puts ticks where a clock or calendar would**: every
  15 minutes, on the hour, every 3 or 6 hours, at midnight, on Mondays, on the
  first of the month or quarter, on round years. Its labels say only what
  changes: `21:00`, then `Nov 15` at midnight, then `03:00`. The first tick
  also carries the date (or the year). It shows local time unless given a
  `tz`, and it never raises, whatever the range: there are no ticks before
  year 1 or after 9999. So plot real timestamps, not times shifted by the
  zone's offset.

## Look

- **Unstyled datasets take the theme's colours in turn**: `$primary`,
  `$secondary`, `$accent`, `$success`, `$warning`, `$error`, from
  `Plot.PALETTE`, a class attribute to override. Any `style` may name theme
  variables (`"bold $accent"`), and every style is resolved again on each
  redraw, so a theme change recolours the plot.
- **The space around the data is CSS grid tracks**: `grid-columns: 10 1fr` for
  the tick labels on the left, `grid-rows: 2 1fr 3` for the y label above and
  the x tick labels and label below. Override them on `Plot` to make room for
  longer labels; y tick labels are cropped to the space they get.
- **The component classes `plot--axis`, `plot--tick` and `plot--label`** style
  the frame and tick marks, the tick labels and the axis labels. The axis takes
  `$primary` while the plot has focus.

## Legend

- **`legend` is the corner it starts out in** (`"top-left"`, `"top-right"`,
  `"bottom-left"`, `"bottom-right"`), or None for no legend. It lists every
  dataset that has a `label`.
- **The legend can be dragged.** Letting go re-anchors it to the corner it is
  nearest, so a resize keeps it where it was put relative to that corner.
  Dragging it is allowed even with `allow_pan_and_zoom` off, since moving the
  legend changes nothing about the data shown.

## Zoom and pan

- **The wheel zooms around the pointer**: over the data, both axes; over a
  row or column of tick labels, that axis only. Dragging pans the same way.
  A drag captures the mouse, so it carries on past the edge of the plot.
- **The keys** are `+`/`-` (zoom), `ctrl+=`/`ctrl+-` for the x axis only,
  `ctrl+shift+=`/`ctrl+shift+-` for the y axis only, the arrow keys (pan)
  and `r` (reset).
- **`allow_pan_and_zoom=False` turns off the wheel, dragging and the keys**,
  and the keys leave the footer (through `check_action`). The wheel then
  passes through, so a plot inside a scrolling container does not block the
  scroll. `invert_mouse_wheel=True` flips the wheel.
- **Zooming, panning and resetting post `Plot.RangeChanged`**, which carries
  the new `x_range` and `y_range` and has a `control`, so
  `@on(Plot.RangeChanged, "#id")` works. Assigning `x_limits` posts nothing:
  the app already knows.

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
