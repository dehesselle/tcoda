# SPDX-FileCopyrightText: 2025 David Fokkema
# SPDX-FileCopyrightText: 2026 René de Hesselle <dehesselle@web.de>
#
# SPDX-License-Identifier: MIT

"""Plots: line, scatter, bar and error-bar, on axes that scale themselves.

A `Plot` takes its data whenever it is handed it, mounted or not::

    def compose(self) -> ComposeResult:
        plot = Plot(x_label="time (s)", legend="top-right")
        plot.plot(times, signal, hires_mode="braille", label="signal")
        plot.scatter(times, noise, label="noise")
        yield plot

and zooming or panning it posts `Plot.RangeChanged`::

    @on(Plot.RangeChanged, "#signal")
    def _follow(self, event: Plot.RangeChanged) -> None:
        ...
"""

from tcoda.plot._formatters import (
    AxisFormatter,
    CategoricalFormatter,
    DateTimeFormatter,
    DurationFormatter,
    NumericFormatter,
)
from tcoda.plot._hires import HiResMode
from tcoda.plot._legend import LegendLocation
from tcoda.plot._plot import Axes, Plot

__all__ = [
    "Axes",
    "AxisFormatter",
    "CategoricalFormatter",
    "DateTimeFormatter",
    "DurationFormatter",
    "HiResMode",
    "LegendLocation",
    "NumericFormatter",
    "Plot",
]
