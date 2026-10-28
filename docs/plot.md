# Plot

A plotting widget: line, scatter, bar and error-bar plots with auto-scaling
axes, "nice" ticks (1, 2, 5, 10, 20, ...), a legend, and zooming and panning
by mouse and keyboard. Datasets can be drawn with full cells or with one of
three high-resolution modes, which pack 1×2, 2×2 or 2×4 pixels into a cell.

```python
from tcoda.plot import HiResMode, LegendLocation, PlotWidget


class MyApp(App[None]):
    def compose(self) -> ComposeResult:
        yield PlotWidget()

    def on_mount(self) -> None:
        plot = self.query_one(PlotWidget)
        plot.plot(xs, ys, hires_mode=HiResMode.BRAILLE, label="signal")
        plot.scatter(xs, noise, marker_style="red", label="noise")
        plot.set_xlabel("time (s)")
        plot.show_legend(LegendLocation.TOPRIGHT)
```

- **Datasets**: `plot`, `scatter`, `bar`, `errorbar` and `add_v_line` each add
  one; `clear` removes them all. Data is any iterable of numbers — lists,
  tuples, generators, and NumPy arrays too, though tcoda does not depend on
  NumPy. `bar` also takes a list of strings for `x`, which labels the bars by
  category. NaNs and infinities are dropped before drawing.
- **Axes**: `set_xlimits`/`set_ylimits` (pass `None` for either end to
  auto-scale it), `set_xlabel`/`set_ylabel`, `set_xticks`/`set_yticks` (`None`
  for automatic, `[]` for none), and `set_x_formatter`/`set_y_formatter` with an
  `AxisFormatter` — `NumericAxisFormatter` is the default, `DurationFormatter`
  labels seconds in a fitting unit (`0.5h`, `1.0h`, ...). A date-and-time
  formatter exists as well,
  but has not been made public yet (upstream did not export it either).
- **Zoom and pan**: the scroll wheel zooms around the pointer, dragging pans.
  The keys are `+`/`-` (zoom), `ctrl+=`/`ctrl+-` for the x axis only,
  `ctrl+shift+=`/`ctrl+shift+-` for the y axis only, the arrow keys (pan) and
  `r` (reset). `allow_pan_and_zoom=False` turns off the mouse side only — the
  keys keep working — and `invert_mouse_wheel=True` flips the wheel. Zooming, panning and resetting
  post `PlotWidget.ScaleChanged`.
- **Styling**: the component classes `plot--axis`, `plot--tick` and
  `plot--label`, and the reactives `margin_top`, `margin_bottom` and
  `margin_left` for the space taken by ticks and labels.

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
everything tcoda has done since. Every file in `src/tcoda/plot/` stays under
the MIT license, as do the two test files that came along
(`tests/test_plot_formatters.py`, `tests/test_plot_transformations.py`).

The canvas (`_canvas.py`, `_hires.py`) is private to `tcoda.plot`. Both it and
the plot widget import Textual's private `textual._box_drawing`, so check
these two when raising the Textual pin.
