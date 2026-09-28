"""Chord bindings: matching, abandoning, timing out, and staying out of the way
of widgets that type."""

from __future__ import annotations

from typing import ClassVar

from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.widgets import Input, Static

from tcw.chords import ChordMixin
from tcw.widgets import Footer, FooterBinding


class Harness(ChordMixin, App[None]):
    # Nothing focused to begin with, so the Input only takes part in the tests
    # that focus it.
    AUTO_FOCUS = None
    CHORD_TIMEOUT = None

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("ctrl+k ctrl+s", "record('save')", "Save all", id="save-all"),
        Binding("ctrl+k x y", "record('xy')", "Three steps"),
        Binding("ctrl+k ?", "record('help')", "Help"),
        Binding("ctrl+e d", "record('gated')", "Gated"),
        Binding("g g", "record('top')", "Top"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.fired: list[str] = []
        #: True enables the gated chord, None dims it, False removes it.
        self.gate: bool | None = True

    def compose(self) -> ComposeResult:
        yield Input(id="input")
        yield Footer()

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if parameters == ("gated",):
            return self.gate
        return True

    def action_record(self, name: str) -> None:
        self.fired.append(name)


async def test_a_two_step_chord_runs_its_action() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        await pilot.press("ctrl+k")
        assert app.pending_chord == ("ctrl+k",)
        assert app.fired == []
        await pilot.press("ctrl+s")
        assert app.fired == ["save"]
        assert app.pending_chord == ()


async def test_a_three_step_chord_waits_for_every_step() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        await pilot.press("ctrl+k", "x")
        assert app.pending_chord == ("ctrl+k", "x")
        await pilot.press("y")
        assert app.fired == ["xy"]


async def test_a_single_character_step_matches_its_key_name() -> None:
    # "?" arrives as the key "question_mark", which Textual does not normalise
    # inside a chord string for us.
    app = Harness()
    async with app.run_test() as pilot:
        await pilot.press("ctrl+k", "?")
        assert app.fired == ["help"]


async def test_a_key_continuing_no_chord_abandons_it_and_is_swallowed() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        app.query_one(Input).focus()
        await pilot.press("ctrl+k", "z")
        assert app.fired == []
        assert app.pending_chord == ()
        assert app.query_one(Input).value == ""


async def test_escape_abandons_a_chord() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        await pilot.press("ctrl+k", "escape", "ctrl+s")
        assert app.fired == []
        assert app.pending_chord == ()


async def test_a_chord_times_out() -> None:
    app = Harness()
    app.CHORD_TIMEOUT = 0.1
    async with app.run_test() as pilot:
        await pilot.press("ctrl+k")
        await pilot.pause(0.3)
        assert app.pending_chord == ()
        await pilot.press("ctrl+s")
        assert app.fired == []
        # Within the window it still works. A window this short is at the
        # mercy of a loaded test run, so widen it rather than race it.
        app.CHORD_TIMEOUT = 5
        await pilot.press("ctrl+k", "ctrl+s")
        assert app.fired == ["save"]


async def test_a_chord_prefix_beats_the_focused_widgets_own_binding() -> None:
    # Input binds ctrl+k to "delete everything right of the cursor".
    app = Harness()
    async with app.run_test() as pilot:
        field = app.query_one(Input)
        field.focus()
        field.value = "hello"
        field.cursor_position = 0
        await pilot.press("ctrl+k", "ctrl+s")
        assert app.fired == ["save"]
        assert field.value == "hello"


async def test_a_printable_first_step_is_left_to_a_widget_that_types() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        field = app.query_one(Input)
        field.focus()
        await pilot.press("g", "g")
        assert field.value == "gg"
        assert app.fired == []
        # With nothing focused, the same keys are a chord again.
        app.set_focus(None)
        await pilot.press("g", "g")
        assert app.fired == ["top"]


async def test_a_disabled_chord_neither_runs_nor_holds_its_prefix() -> None:
    for gate in (False, None):
        app = Harness()
        app.gate = gate
        async with app.run_test() as pilot:
            await pilot.press("ctrl+e")
            assert app.pending_chord == ()
            await pilot.press("d")
            assert app.fired == []


async def test_a_keymap_can_rebind_a_chord() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        app.set_keymap({"save-all": "ctrl+k ctrl+w"})
        await pilot.press("ctrl+k", "ctrl+s")
        assert app.fired == []
        await pilot.press("ctrl+k", "ctrl+w")
        assert app.fired == ["save"]


async def test_a_chord_is_displayed_step_by_step() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        assert app.get_key_display(Binding("ctrl+k ctrl+s", "x")) == "^k ^s"
        assert app.get_key_display(Binding("ctrl+k ?", "x")) == "^k ?"
        # An explicit key_display still wins, and single keys are untouched.
        assert (
            app.get_key_display(Binding("ctrl+k ctrl+s", "x", key_display="S")) == "S"
        )
        assert app.get_key_display(Binding("ctrl+q", "x")) == "^q"
        await pilot.pause()
        displays = {b.key_display for b in app.query(FooterBinding)}
        assert "^k ^s" in displays


async def test_clicking_a_chord_in_the_footer_runs_it() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        await pilot.pause()
        key = next(b for b in app.query(FooterBinding) if b.key == "ctrl+k ctrl+s")
        await pilot.click(key)
        await pilot.pause()
        assert app.fired == ["save"]


async def test_the_footer_shows_a_pending_chord() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        footer = app.query_one(Footer)
        footer.status.update("Online")
        label = footer.status.query_one("#footer-chord", Static)
        assert not label.display
        await pilot.press("ctrl+k")
        assert label.display
        assert str(label.content) == "(^k) waiting for next key…"
        await pilot.press("x")
        assert str(label.content) == "(^k x) waiting for next key…"
        await pilot.press("escape")
        assert not label.display
        # The app's own status text was never touched.
        text = footer.status.query_one("#footer-status-text", Static)
        assert str(text.content) == "Online"
