"""MultiSelect: the generic checkbox-dropdown mechanics -- open/close via
click, keyboard and blur, toggling rows, compact mode, and scrolling a tall
option list. Domain-specific integration (labels, hiding log sources) is
covered in test_log_viewer.py instead."""

from __future__ import annotations

import asyncio

from textual.app import App, ComposeResult
from textual.pilot import Pilot
from textual.widgets import Button
from textual.widgets.selection_list import Selection

from tcoda.widgets._multi_select import (
    MultiSelect,
    MultiSelectCurrent,
    MultiSelectOverlay,
)


class Harness(App[None]):
    """A `MultiSelect` plus a focusable `Button`, so tests can move focus
    elsewhere the same way a real toolbar would."""

    def __init__(self, *, options: int = 3, compact: bool = False) -> None:
        super().__init__()
        self._options = options
        self._compact = compact

    def compose(self) -> ComposeResult:
        yield MultiSelect[str](
            [
                Selection(f"Option {i}", f"option-{i}", True)
                for i in range(self._options)
            ],
            label="Pick",
            compact=self._compact,
            id="multi-select",
        )
        yield Button("Elsewhere", id="elsewhere")


async def settle(pilot: Pilot[None], rounds: int = 3) -> None:
    for _ in range(rounds):
        await pilot.pause()
        await asyncio.sleep(0.02)


async def test_clicking_the_trigger_opens_the_overlay() -> None:
    app = Harness()
    async with app.run_test(size=(40, 24)) as pilot:
        await pilot.pause()
        multi_select = app.query_one("#multi-select", MultiSelect)
        assert multi_select.expanded is False

        await pilot.click("#multi-select")
        await settle(pilot)
        assert multi_select.expanded is True


async def test_reclicking_the_trigger_does_not_close_it_matching_select() -> None:
    """Not a bug: a single click on the trigger while open both blurs the
    overlay (dismissing it) and re-toggles `expanded` via `SelectCurrent.
    Toggle`, netting no change -- confirmed against a real stock `Select`,
    which has the exact same quirk. Escape or clicking a genuinely different
    focusable widget are the ways to close it (see the tests below)."""
    app = Harness()
    async with app.run_test(size=(40, 24)) as pilot:
        await pilot.pause()
        await pilot.click("#multi-select")
        await settle(pilot)
        multi_select = app.query_one("#multi-select", MultiSelect)
        assert multi_select.expanded is True

        await pilot.click("#multi-select")
        await settle(pilot)
        assert multi_select.expanded is True


async def test_escape_closes_the_overlay() -> None:
    app = Harness()
    async with app.run_test(size=(40, 24)) as pilot:
        await pilot.pause()
        await pilot.click("#multi-select")
        await settle(pilot)
        multi_select = app.query_one("#multi-select", MultiSelect)
        assert multi_select.expanded is True

        await pilot.press("escape")
        await settle(pilot)
        assert multi_select.expanded is False


async def test_moving_focus_to_another_widget_closes_it() -> None:
    """Blur-driven, matching `Select`: no manual outside-click detection --
    moving focus to another widget dismisses the overlay for free. Tab,
    not a click, is used to move focus here: the open overlay visually (and
    hit-test-wise) sits on top of anything below it on screen, same as a
    real `Select`'s overlay would, so a click "behind" it lands on the
    overlay itself rather than the widget underneath.

    A click that lands on nothing focusable (e.g. bare screen background)
    does *not* close it either -- confirmed against a real stock `Select`,
    which behaves identically. Only Escape or focusing something else does."""
    app = Harness()
    async with app.run_test(size=(40, 24)) as pilot:
        await pilot.pause()
        await pilot.click("#multi-select")
        await settle(pilot)
        multi_select = app.query_one("#multi-select", MultiSelect)
        assert multi_select.expanded is True

        await pilot.press("tab")
        await settle(pilot)
        assert multi_select.expanded is False


async def test_toggling_a_row_posts_option_toggled_and_updates_selected() -> None:
    app = Harness()
    async with app.run_test(size=(40, 24)) as pilot:
        await pilot.pause()
        multi_select = app.query_one("#multi-select", MultiSelect)
        await pilot.click("#multi-select")
        await settle(pilot)

        overlay = multi_select.query_one(MultiSelectOverlay)
        overlay.toggle("option-0")
        await settle(pilot)

        assert multi_select.is_selected("option-0") is False
        assert "option-1" in multi_select.selected


async def test_programmatic_select_and_deselect_do_not_post_option_toggled() -> None:
    events: list[str] = []

    class RecordingHarness(Harness):
        def on_multi_select_option_toggled(
            self, event: MultiSelect.OptionToggled
        ) -> None:
            events.append(event.value)

    app = RecordingHarness()
    async with app.run_test(size=(40, 24)) as pilot:
        await pilot.pause()
        multi_select = app.query_one("#multi-select", MultiSelect)

        multi_select.deselect("option-0")
        await settle(pilot)
        assert multi_select.is_selected("option-0") is False

        multi_select.select("option-0")
        await settle(pilot)
        assert multi_select.is_selected("option-0") is True

        assert events == []


async def test_compact_strips_both_the_trigger_and_overlay_border() -> None:
    """Matches the real `Select`: `compact=True` removes the trigger's
    border, and -- verified against a real stock `Select` -- the overlay's
    too. `compact` is data-bound down to the overlay the same way `Select`
    binds it to `SelectOverlay`, so `OptionList`'s own `&.-textual-compact
    { border: none !important; }` applies there as well."""
    app = Harness(compact=True)
    async with app.run_test(size=(40, 24)) as pilot:
        await pilot.pause()
        multi_select = app.query_one("#multi-select", MultiSelect)
        current = multi_select.query_one(MultiSelectCurrent)
        assert current.styles.border_top[0] == ""

        await pilot.click("#multi-select")
        await settle(pilot)
        overlay = multi_select.query_one(MultiSelectOverlay)
        assert overlay.styles.border_top[0] == ""


async def test_the_overlay_widens_for_a_long_option_added_while_open() -> None:
    """Sources are discovered live and their names are arbitrary log-source
    text, unlike a `Select`'s usually-static, caller-sized option list -- so
    the overlay can't just inherit the trigger's fixed width the way a real
    `Select`'s does. `width: auto` (with `min-width: 1fr` so it's never
    narrower than the trigger) lets it grow to fit the longest known option,
    live, even while already open."""

    class NarrowHarness(App[None]):
        CSS = "#multi-select { width: 12; }"

        def compose(self) -> ComposeResult:
            yield MultiSelect[str](
                [Selection("short", "short", True)], label="Pick", id="multi-select"
            )

    app = NarrowHarness()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        multi_select = app.query_one("#multi-select", MultiSelect)
        await pilot.click("#multi-select")
        await settle(pilot)
        overlay = multi_select.query_one(MultiSelectOverlay)
        before = overlay.region.width

        overlay.add_option(Selection("a-much-longer-source-name", "long-source", True))
        await settle(pilot)
        assert overlay.region.width > before
        assert multi_select.region.width == 12


async def test_the_overlay_width_is_capped_for_an_extremely_long_option() -> None:
    """An unreasonably long single source name must not push the overlay off
    the edge of the screen."""

    class NarrowHarness(App[None]):
        CSS = "#multi-select { width: 12; }"

        def compose(self) -> ComposeResult:
            yield MultiSelect[str](
                [Selection("x" * 200, "long", True)], label="Pick", id="multi-select"
            )

    app = NarrowHarness()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        multi_select = app.query_one("#multi-select", MultiSelect)
        await pilot.click("#multi-select")
        await settle(pilot)
        overlay = multi_select.query_one(MultiSelectOverlay)
        assert overlay.region.width <= 80


async def test_a_tall_option_list_scrolls() -> None:
    app = Harness(options=30)
    async with app.run_test(size=(40, 24)) as pilot:
        await pilot.pause()
        multi_select = app.query_one("#multi-select", MultiSelect)
        await pilot.click("#multi-select")
        await settle(pilot)

        overlay = multi_select.query_one(MultiSelectOverlay)
        assert overlay.scrollable_content_region.height < overlay.option_count
        overlay.scroll_end(animate=False)
        await settle(pilot)
        assert overlay.scroll_y > 0
