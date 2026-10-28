# SPDX-FileCopyrightText: 2026 René de Hesselle <dehesselle@web.de>
#
# SPDX-License-Identifier: 0BSD

"""The plot as text, compared character for character with a recording.

These pin down what the plot draws, not how: the recording is the whole
screen's text, so the widget's internals can be rebuilt freely as long as the
picture comes out the same. Colours are deliberately not part of it.

Run with ``TCODA_UPDATE_GOLDEN=1`` to re-record after an intended change, and
review the diff of ``tests/plot_golden/`` like any other.
"""

from __future__ import annotations

import math
import os
from collections.abc import Callable
from pathlib import Path

import pytest
from textual.app import App, ComposeResult

from tcoda.plot import Plot

GOLDEN = Path(__file__).parent / "plot_golden"
UPDATE = bool(os.environ.get("TCODA_UPDATE_GOLDEN"))

XS = [i / 10 for i in range(100)]
SINE = [math.sin(x) for x in XS]


def _legend(plot: Plot) -> None:
    plot.x_label = "time (s)"
    plot.y_label = "signal"
    plot.plot(XS, SINE, label="sine")
    plot.scatter(XS[::7], SINE[::7], hires_mode="braille", label="samples")
    plot.legend = "top-right"


CASES: dict[str, Callable[[Plot], None]] = {
    "line": lambda plot: plot.plot(XS, SINE),
    "line_braille": lambda plot: plot.plot(XS, SINE, hires_mode="braille"),
    "scatter": lambda plot: plot.scatter(XS[::4], SINE[::4]),
    "scatter_halfblock": lambda plot: plot.scatter(
        XS[::2], SINE[::2], hires_mode="halfblock"
    ),
    "bar_quadrant": lambda plot: plot.bar([1, 2, 3], [1, 3, 2], hires_mode="quadrant"),
    "errorbar": lambda plot: plot.errorbar(
        [1, 2, 3], [1, 2, 1], xerr=[0.2] * 3, yerr=[0.3] * 3
    ),
    "vline": lambda plot: (plot.plot(XS, SINE), plot.vline(5.0)),
    "categorical": lambda plot: plot.bar(["red", "green", "blue"], [1, 3, 2]),
    "legend": _legend,
}


class Harness(App[None]):
    def compose(self) -> ComposeResult:
        yield Plot()


def screen_text(app: App[None]) -> str:
    strips = app.screen._compositor.render_strips()
    return "\n".join(strip.text.rstrip() for strip in strips) + "\n"


@pytest.mark.parametrize("name", CASES)
async def test_the_plot_draws_as_recorded(name: str) -> None:
    app = Harness()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        CASES[name](app.query_one(Plot))
        await pilot.pause()
        await pilot.pause()
        actual = screen_text(app)

    path = GOLDEN / f"{name}.txt"
    if UPDATE:
        GOLDEN.mkdir(exist_ok=True)
        path.write_text(actual, encoding="utf-8")
    assert actual == path.read_text(encoding="utf-8")
