"""The countdown: what it renders, and the spinner it drives itself.

Deliberately no `Footer` anywhere in this file -- the widget is generic, and a
test that needed a footer to exercise it would mean it wasn't.
"""

from __future__ import annotations

import asyncio

from textual.app import App, ComposeResult

from tcw.widgets import Countdown


class Harness(App[None]):
    def __init__(self, **kwargs: object) -> None:
        super().__init__()
        self._kwargs = kwargs

    def compose(self) -> ComposeResult:
        yield Countdown(**self._kwargs)


# ------------------------------------------------------------------ rendering


async def test_it_renders_the_seconds_remaining() -> None:
    app = Harness(remaining=42)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.query_one(Countdown).render() == "42"


async def test_zero_renders_a_zero_rather_than_nothing() -> None:
    """Reaching zero is a real state. Blanking it there would make a genuine
    zero indistinguishable from a countdown that is switched off -- which is
    what `display` is for."""
    app = Harness(remaining=0)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.query_one(Countdown).render() == "0"


async def test_a_longer_wait_than_the_cap_shows_the_cap() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        await pilot.pause()
        countdown = app.query_one(Countdown)
        countdown.remaining = Countdown.MAX_SECONDS + 500
        assert countdown.render() == str(Countdown.MAX_SECONDS)


async def test_remaining_relayouts_so_a_narrower_value_is_not_left_clipped() -> None:
    """The widget is `width: auto`; a plain reactive would only repaint in
    place, leaving "100" as "10" plus a stale column when it became "99"."""
    app = Harness(remaining=100)
    async with app.run_test() as pilot:
        await pilot.pause()
        countdown = app.query_one(Countdown)
        assert countdown.outer_size.width == 3
        countdown.remaining = 9
        await pilot.pause()
        assert countdown.outer_size.width == 1


# -------------------------------------------------------------------- spinner


async def test_refreshing_shows_a_spinner_frame_instead_of_the_number() -> None:
    app = Harness(remaining=42)
    async with app.run_test() as pilot:
        await pilot.pause()
        countdown = app.query_one(Countdown)
        countdown.refreshing = True
        await pilot.pause()
        assert countdown.render() in Countdown.SPINNER


async def test_the_spinner_advances_on_its_own_with_no_caller_tick() -> None:
    """The widget owns its clock: a caller says only whether something is in
    flight. Nothing in this test ticks a frame counter."""
    app = Harness()
    async with app.run_test() as pilot:
        await pilot.pause()
        countdown = app.query_one(Countdown)
        countdown.refreshing = True
        await pilot.pause()
        first = countdown.render()
        seen = {first}
        for _ in range(20):
            await asyncio.sleep(Countdown.SPINNER_INTERVAL)
            await pilot.pause()
            seen.add(countdown.render())
            if len(seen) > 1:
                break
        assert len(seen) > 1, "the spinner never advanced"


async def test_clearing_refreshing_stops_the_spinner_and_shows_the_number() -> None:
    app = Harness(remaining=7)
    async with app.run_test() as pilot:
        await pilot.pause()
        countdown = app.query_one(Countdown)
        countdown.refreshing = True
        await pilot.pause()
        countdown.refreshing = False
        await pilot.pause()
        assert countdown.render() == "7"
        assert countdown._spinner is None


async def test_refreshing_set_before_mount_still_spins() -> None:
    """A timer needs a running message pump, so the watcher cannot start one
    at construction time -- mounting has to pick it up."""
    app = Harness()
    async with app.run_test() as pilot:
        countdown = app.query_one(Countdown)
        countdown.refreshing = True
        await pilot.pause()
        assert countdown._spinner is not None
