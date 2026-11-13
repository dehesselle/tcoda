# SPDX-FileCopyrightText: 2026 René de Hesselle <dehesselle@web.de>
#
# SPDX-License-Identifier: 0BSD

"""Seconds since input: what counts as input, and what does not."""

from __future__ import annotations

from time import monotonic
from typing import ClassVar

import pytest
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.widgets import Static

from tcoda.chords import ChordMixin
from tcoda.input_idle import InputIdleMixin
from tcoda.terminal_title import TerminalTitleMixin

#: How far back a test sets the last input, well clear of how long a test
#: takes to run.
LONG_AGO = 1000.0


class Harness(InputIdleMixin, ChordMixin, TerminalTitleMixin, App[None]):
    TERMINAL_TITLE = "harness"
    CHORD_TIMEOUT = None
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("ctrl+k ctrl+s", "record('save')", "Save all"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.fired: list[str] = []
        self.mounted = False

    def compose(self) -> ComposeResult:
        yield Static("body", id="body")

    def on_mount(self) -> None:
        self.mounted = True

    def action_record(self, name: str) -> None:
        self.fired.append(name)


def _long_ago(app: Harness) -> None:
    app._last_input = monotonic() - LONG_AGO


def _scroll(kind: type[events.MouseEvent]) -> events.MouseEvent:
    return kind(None, 0, 0, 0, 1, 0, False, False, False)


async def test_the_clock_starts_on_mount() -> None:
    assert Harness().seconds_since_input == 0.0
    app = Harness()
    async with app.run_test() as pilot:
        await pilot.pause()
        assert 0.0 <= app.seconds_since_input < LONG_AGO / 2


async def test_the_apps_own_mount_and_the_other_mixins_still_run() -> None:
    """The mixin's handler is the private `_on_mount`, which Textual calls
    for each class in the MRO, so it displaces neither the app's `on_mount`
    nor `TerminalTitleMixin`'s own `_on_mount`."""
    app = Harness()
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.mounted
        assert app.terminal_title == "harness"


async def test_a_key_press_counts() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        _long_ago(app)
        await pilot.press("a")
        assert app.seconds_since_input < LONG_AGO / 2


async def test_a_chord_step_counts_although_chords_consume_it() -> None:
    """`ChordMixin` does not pass a key it consumes on to `super()`, which is
    why this mixin has to come before it."""
    app = Harness()
    async with app.run_test() as pilot:
        await pilot.press("ctrl+k")
        _long_ago(app)
        await pilot.press("ctrl+s")
        assert app.fired == ["save"]
        assert app.seconds_since_input < LONG_AGO / 2


async def test_a_click_counts() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        _long_ago(app)
        await pilot.click("#body")
        assert app.seconds_since_input < LONG_AGO / 2


@pytest.mark.parametrize(
    "event",
    [
        events.Paste("pasted"),
        events.AppFocus(),
        _scroll(events.MouseScrollUp),
        _scroll(events.MouseScrollDown),
        _scroll(events.MouseScrollLeft),
        _scroll(events.MouseScrollRight),
    ],
    ids=lambda event: type(event).__name__,
)
async def test_other_input_counts(event: events.Event) -> None:
    app = Harness()
    async with app.run_test() as pilot:
        _long_ago(app)
        app.post_message(event)
        await pilot.pause()
        assert app.seconds_since_input < LONG_AGO / 2


async def test_moving_the_mouse_does_not_count() -> None:
    """A pointer passing over the terminal on its way elsewhere moves it."""
    app = Harness()
    async with app.run_test() as pilot:
        _long_ago(app)
        await pilot.hover("#body", offset=(1, 0))
        await pilot.hover("#body", offset=(2, 0))
        assert app.seconds_since_input >= LONG_AGO


class CountsMovement(Harness):
    INPUT_EVENTS = (*Harness.INPUT_EVENTS, events.MouseMove)


async def test_an_app_can_count_more_by_overriding_input_events() -> None:
    app = CountsMovement()
    async with app.run_test() as pilot:
        _long_ago(app)
        await pilot.hover("#body", offset=(1, 0))
        await pilot.hover("#body", offset=(2, 0))
        assert app.seconds_since_input < LONG_AGO / 2


async def test_losing_focus_does_not_count() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        _long_ago(app)
        app.post_message(events.AppBlur())
        await pilot.pause()
        assert app.seconds_since_input >= LONG_AGO
