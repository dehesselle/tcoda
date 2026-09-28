"""ChordViewer: when it shows, what it lists, how it lays it out, and holding
the chord open while it is up."""

from __future__ import annotations

from typing import ClassVar

import pytest
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.screen import Screen
from textual.widgets import Static

from tcw.chords import ChordMixin
from tcw.widgets import ChordViewer, Footer
from tcw.widgets._chord_viewer import ChordViewerEntry, _columns


class Harness(ChordMixin, App[None]):
    AUTO_FOCUS = None
    CHORD_TIMEOUT = None

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("ctrl+k ctrl+s", "record('save')", "Save all"),
        Binding("ctrl+k ?", "record('help')", "Help", show=False),
        Binding("ctrl+k x y", "record('xy')", "Three steps"),
        Binding("ctrl+k x z", "record('xz')", "Other three"),
        Binding("ctrl+k g a", "record('ga')", "Unnamed"),
        Binding("ctrl+k d", "record('dimmed')", "Dimmed"),
        Binding("ctrl+k h", "record('hidden')"),
    ]
    CHORD_GROUPS: ClassVar[dict[str, str]] = {
        "ctrl+k": "Keyboard",
        "ctrl+k x": "Extras",
    }

    def __init__(self, delay: float = 0) -> None:
        super().__init__()
        self.delay = delay
        self.fired: list[str] = []

    def compose(self) -> ComposeResult:
        yield Footer()
        yield ChordViewer(delay=self.delay)

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        return None if parameters == ("dimmed",) else True

    def action_record(self, name: str) -> None:
        self.fired.append(name)


def listed(app: App[None]) -> dict[str, str]:
    return {e.item.key_display: e.item.description for e in app.query(ChordViewerEntry)}


def entry(app: App[None], key_display: str) -> ChordViewerEntry:
    return next(
        e for e in app.query(ChordViewerEntry) if e.item.key_display == key_display
    )


def text(app: App[None], id: str) -> str:
    return str(app.query_one(f"#{id}", Static).content)


async def test_it_appears_only_after_the_delay() -> None:
    app = Harness(delay=0.2)
    async with app.run_test() as pilot:
        viewer = app.query_one(ChordViewer)
        assert not viewer.display
        await pilot.press("ctrl+k")
        assert not viewer.display
        await pilot.pause(0.4)
        assert viewer.display


async def test_a_chord_typed_quickly_never_shows_it() -> None:
    app = Harness(delay=0.3)
    async with app.run_test() as pilot:
        viewer = app.query_one(ChordViewer)
        await pilot.press("ctrl+k", "ctrl+s")
        assert app.fired == ["save"]
        await pilot.pause(0.5)
        assert not viewer.display


async def test_once_shown_it_holds_the_chord_until_escape() -> None:
    app = Harness()
    app.CHORD_TIMEOUT = 0.2
    async with app.run_test() as pilot:
        viewer = app.query_one(ChordViewer)
        await pilot.press("ctrl+k")
        await pilot.pause(0.5)
        assert viewer.display
        assert app.pending_chord == ("ctrl+k",)
        await pilot.press("escape")
        assert not viewer.display
        assert app.pending_chord == ()


async def test_it_lists_each_next_step_once_sorted_by_key() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        await pilot.press("ctrl+k")
        await pilot.pause()
        # `show=False` is listed; no description is not.
        assert listed(app) == {
            "?": "Help",
            "^s": "Save all",
            "d": "Dimmed",
            "g": "+1 chord",
            "x": "+Extras",
        }
        keys = [e.item.key_display for e in app.query(ChordViewerEntry)]
        assert keys == ["?", "^s", "d", "g", "x"]
        assert entry(app, "d").has_class("-disabled")
        assert not entry(app, "^s").has_class("-disabled")


async def test_the_bottom_line_shows_the_steps_and_the_keys() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        await pilot.press("ctrl+k")
        await pilot.pause()
        assert text(app, "chord-viewer-trail") == "^k Keyboard"
        # Nothing to go back to from the first step.
        assert text(app, "chord-viewer-help") == "esc close"
        await pilot.press("x")
        await pilot.pause()
        assert listed(app) == {"y": "Three steps", "z": "Other three"}
        assert text(app, "chord-viewer-trail") == "^k Keyboard » x Extras"
        assert text(app, "chord-viewer-help") == "esc close   ⌫ back"


async def test_backspace_steps_back_then_closes() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        viewer = app.query_one(ChordViewer)
        await pilot.press("ctrl+k", "x")
        await pilot.pause()
        await pilot.press("backspace")
        await pilot.pause()
        assert app.pending_chord == ("ctrl+k",)
        assert viewer.display
        assert "x" in listed(app)
        await pilot.press("backspace")
        assert app.pending_chord == ()
        assert not viewer.display


async def test_clicking_an_entry_presses_its_step() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        await pilot.press("ctrl+k")
        await pilot.pause()
        await pilot.click(entry(app, "x"))
        await pilot.pause()
        assert app.pending_chord == ("ctrl+k", "x")
        await pilot.click(entry(app, "y"))
        await pilot.pause()
        assert app.fired == ["xy"]


def test_columns_fit_the_width_and_fill_downwards_first() -> None:
    # (80 // (20 + 3)) columns of two rows, the last one short.
    assert _columns([5] * 5, 80, 20, 3) == [range(2), range(2, 4), range(4, 5)]
    # Columns the items do not reach still exist, empty.
    assert _columns([5] * 2, 80, 20, 3) == [range(1), range(1, 2), range(2, 2)]
    # One wide item decides for all of them, and there is always one column.
    assert _columns([30, 5, 5], 80, 20, 3) == [range(2), range(2, 3)]
    assert _columns([100], 80, 20, 3) == [range(1)]
    assert _columns([], 80, 20, 3) == []


async def test_it_lays_itself_out_again_on_resize() -> None:
    app = Harness()
    async with app.run_test(size=(120, 24)) as pilot:
        await pilot.press("ctrl+k")
        await pilot.pause()
        # 120 wide less the 4 columns of padding.
        assert len(app.query(".chord-viewer-box")) == 116 // 23
        await pilot.resize_terminal(50, 24)
        await pilot.pause()
        assert len(app.query(".chord-viewer-box")) == 46 // 23


async def test_a_blank_line_separates_the_entries_from_the_bottom_line() -> None:
    app = Harness()
    async with app.run_test(size=(120, 24)) as pilot:
        await pilot.press("ctrl+k")
        await pilot.pause()
        last = max(e.region.bottom for e in app.query(ChordViewerEntry))
        assert app.query_one("#chord-viewer-bar").region.y == last + 1


async def test_it_never_takes_more_than_half_the_screen() -> None:
    app = Harness()
    # One column of five entries, their padding and the bottom line: 8 rows.
    async with app.run_test(size=(30, 10)) as pilot:
        await pilot.press("ctrl+k")
        await pilot.pause()
        viewer = app.query_one(ChordViewer)
        columns = app.query_one("#chord-viewer-columns")
        bar = app.query_one("#chord-viewer-bar")
        assert viewer.region.height == 5
        assert bar.region.bottom == 10
        assert columns.max_scroll_y > 0
        # The padding stays put while the entries scroll.
        assert columns.content_region.bottom == bar.region.y - 1


async def test_a_panel_on_a_screen_that_is_not_current_stays_hidden() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        viewer = app.query_one(ChordViewer)
        await app.push_screen(Screen())
        await pilot.press("ctrl+k")
        await pilot.pause(0.2)
        assert app.pending_chord == ("ctrl+k",)
        assert not viewer.display


class NoChords(App[None]):
    def compose(self) -> ComposeResult:
        yield ChordViewer()


async def test_it_needs_a_chord_mixin_app() -> None:
    with pytest.raises(TypeError, match="ChordMixin"):
        async with NoChords().run_test():
            pass
