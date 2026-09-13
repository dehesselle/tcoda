"""The footer: pinned keys, the dynamic run, sorting, dividers, and a status
area whose widgets survive a bindings refresh."""

from __future__ import annotations

from typing import ClassVar

from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.pilot import Pilot
from textual.screen import Screen
from textual.widgets import Static

from tcw.widgets import Countdown, Footer, FooterBinding


class Body(Static, can_focus=True):
    """Something focusable with bindings of its own, so the focus chain has
    more than one level to reorder."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("f5", "reload", "Reload"),
    ]


class Harness(App[None]):
    # Nothing focused to begin with, so `Body.focus()` in a test is a real
    # change to the focus chain rather than a no-op on what Textual already
    # focused for us.
    AUTO_FOCUS = None

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("f2", "find", "Find"),
        Binding("f10", "tree", "Tree"),
        Binding("f1", "log", "Log"),
        Binding("f3", "ided", "Ided", id="my.ided"),
        Binding("ctrl+s", "save", "Save"),
        Binding("x", "invisible", "Invisible", show=False),
        Binding("f4,f6", "dup", "Dup"),
        Binding("d", "gated", "Gated"),
    ]

    def __init__(self, *status: object, **footer_kwargs: object) -> None:
        super().__init__()
        self._status = status
        self._footer_kwargs = footer_kwargs
        self.fired: list[str] = []
        #: True shows the gated binding, None dims it, False removes it.
        self.gate: bool | None = True

    def compose(self) -> ComposeResult:
        yield Body("body", id="body")
        yield Footer(*self._status, **self._footer_kwargs)

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action == "gated":
            return self.gate
        return True

    def action_find(self) -> None:
        self.fired.append("find")

    def action_gated(self) -> None:
        self.fired.append("gated")


class PushedScreen(Screen[None]):
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("f7", "close", "Close"),
        Binding("f8", "other", "Other"),
    ]

    def compose(self) -> ComposeResult:
        yield Body("body")
        yield Footer(pinned=("close",))


class PushedHarness(App[None]):
    """The footer on an explicitly pushed screen -- `app.query_one` cannot see
    it, which is what used to make this case special."""

    def on_mount(self) -> None:
        self.push_screen(PushedScreen())


async def settle(pilot: Pilot[None], rounds: int = 3) -> None:
    """A bindings change costs a turn for the signal and another for the
    mounts, so a single pause is not enough to see the result."""
    for _ in range(rounds):
        await pilot.pause()


def area_keys(footer: Footer, area: str = "#footer-keys") -> list[str]:
    return [widget.key_display for widget in footer.query(f"{area} FooterBinding")]


def area_text(footer: Footer, area: str = "#footer-keys") -> list[str]:
    return [widget.description for widget in footer.query(f"{area} FooterBinding")]


# --------------------------------------------------------------- stock parity


async def test_active_bindings_render_as_key_and_description() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        await settle(pilot)
        footer = app.query_one(Footer)
        assert "Find" in area_text(footer)
        assert "f2" in area_keys(footer)


async def test_a_binding_marked_show_false_is_left_out() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        await settle(pilot)
        assert "Invisible" not in area_text(app.query_one(Footer))


async def test_several_keys_on_one_action_show_as_the_first_key() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        await settle(pilot)
        keys = area_keys(app.query_one(Footer))
        assert "f4" in keys
        assert "f6" not in keys


async def test_the_key_is_displayed_the_way_the_app_formats_it() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        await settle(pilot)
        assert "^s" in area_keys(app.query_one(Footer))


async def test_clicking_a_binding_runs_its_action() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        await settle(pilot)
        footer = app.query_one(Footer)
        target = next(
            widget for widget in footer.query(FooterBinding) if widget.action == "find"
        )
        await pilot.click(target)
        await settle(pilot)
        assert app.fired == ["find"]


async def test_a_binding_its_action_has_disabled_renders_dim_and_does_nothing() -> None:
    app = Harness()
    app.gate = None
    async with app.run_test() as pilot:
        await settle(pilot)
        footer = app.query_one(Footer)
        target = next(
            widget for widget in footer.query(FooterBinding) if widget.action == "gated"
        )
        assert target.has_class("-disabled")
        await pilot.click(target)
        await settle(pilot)
        assert app.fired == []


async def test_focusing_a_widget_brings_its_own_bindings_in() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        await settle(pilot)
        footer = app.query_one(Footer)
        assert "Reload" not in area_text(footer)
        app.query_one(Body).focus()
        await settle(pilot)
        assert "Reload" in area_text(footer)


# ----------------------------------------------------------------- pinned area


async def test_pins_render_leftmost_in_the_order_they_were_declared() -> None:
    app = Harness(pinned=("f10", "f1"))
    async with app.run_test() as pilot:
        await settle(pilot)
        footer = app.query_one(Footer)
        assert area_keys(footer, "#footer-pinned") == ["f10", "f1"]


async def test_a_pinned_binding_is_not_also_in_the_dynamic_run() -> None:
    app = Harness(pinned=("f1",))
    async with app.run_test() as pilot:
        await settle(pilot)
        footer = app.query_one(Footer)
        assert "f1" not in area_keys(footer)


async def test_a_pin_token_matches_a_binding_id() -> None:
    app = Harness(pinned=("my.ided",))
    async with app.run_test() as pilot:
        await settle(pilot)
        assert area_keys(app.query_one(Footer), "#footer-pinned") == ["f3"]


async def test_a_pin_token_matches_an_action_name() -> None:
    """Which is how `pinned=(OPEN_ACTION,)` pins a MenuBar whose key the app
    changed."""
    app = Harness(pinned=("tree",))
    async with app.run_test() as pilot:
        await settle(pilot)
        assert area_keys(app.query_one(Footer), "#footer-pinned") == ["f10"]


async def test_a_pin_token_matches_a_key() -> None:
    app = Harness(pinned=("f2",))
    async with app.run_test() as pilot:
        await settle(pilot)
        assert area_keys(app.query_one(Footer), "#footer-pinned") == ["f2"]


async def test_pinning_shows_a_binding_that_declared_itself_hidden() -> None:
    """Textual's own Quit is `show=False`, so a stock footer never shows it.
    Naming a key in `pinned=` is an explicit request that outranks that."""
    app = Harness(pinned=("ctrl+q",))
    async with app.run_test() as pilot:
        await settle(pilot)
        footer = app.query_one(Footer)
        assert area_keys(footer, "#footer-pinned") == ["^q"]
        assert area_text(footer, "#footer-pinned") == ["Quit"]


async def test_the_command_palette_key_is_absent_until_it_is_pinned() -> None:
    """It gets no special treatment here: it is an app binding like any other,
    and it happens to be declared `show=False`."""
    app = Harness()
    async with app.run_test() as pilot:
        await settle(pilot)
        assert "^p" not in area_keys(app.query_one(Footer))

    pinned = Harness(pinned=("ctrl+p",))
    async with pinned.run_test() as pilot:
        await settle(pilot)
        assert area_keys(pinned.query_one(Footer), "#footer-pinned") == ["^p"]


async def test_pins_hold_their_place_when_focus_changes_the_rest() -> None:
    app = Harness(pinned=("f10", "f1"))
    async with app.run_test() as pilot:
        await settle(pilot)
        footer = app.query_one(Footer)
        before_pins = area_keys(footer, "#footer-pinned")
        before_keys = area_keys(footer)
        app.query_one(Body).focus()
        await settle(pilot)
        assert area_keys(footer, "#footer-pinned") == before_pins
        assert area_keys(footer) != before_keys


async def test_a_pin_whose_binding_goes_away_keeps_its_slot_dim() -> None:
    """Letting it vanish would shift every pin after it, which is the movement
    pinning exists to stop."""
    app = Harness(pinned=("gated", "f1"))
    async with app.run_test() as pilot:
        await settle(pilot)
        footer = app.query_one(Footer)
        assert area_keys(footer, "#footer-pinned") == ["d", "f1"]
        app.gate = False
        app.screen.refresh_bindings()
        await settle(pilot)
        assert area_keys(footer, "#footer-pinned") == ["d", "f1"]
        held = footer.query("#footer-pinned FooterBinding").first()
        assert held.has_class("-disabled")


async def test_a_bare_string_is_one_pin_not_one_per_character() -> None:
    """Regression: `pinned=(OPEN_ACTION)` is a tuple that lost its trailing
    comma, i.e. a plain string. Iterating it would pin nothing that was asked
    for -- and could pin a single-character binding that wasn't."""
    app = Harness(pinned="tree")
    async with app.run_test() as pilot:
        await settle(pilot)
        footer = app.query_one(Footer)
        assert footer.pinned == ("tree",)
        assert area_keys(footer, "#footer-pinned") == ["f10"]
        # "d" is a real binding here, and a character of "tree" is not enough
        # to claim it.
        assert "d" in area_keys(footer)


async def test_assigning_a_bare_string_to_pinned_is_normalised_too() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        await settle(pilot)
        footer = app.query_one(Footer)
        footer.pinned = "f2"
        await settle(pilot)
        assert footer.pinned == ("f2",)
        assert area_keys(footer, "#footer-pinned") == ["f2"]


async def test_a_pin_that_has_never_been_active_renders_nothing() -> None:
    """There is no description to show yet -- the documented edge of holding
    a slot from cache."""
    app = Harness(pinned=("never-bound-anywhere",))
    async with app.run_test() as pilot:
        await settle(pilot)
        assert area_keys(app.query_one(Footer), "#footer-pinned") == []


# ---------------------------------------------------------------- status area


async def test_a_yielded_widget_lands_in_the_status_area() -> None:
    app = Harness(Countdown(id="cd"))
    async with app.run_test() as pilot:
        await settle(pilot)
        countdown = app.query_one(Countdown)
        assert countdown.parent is app.query_one(Footer).status


async def test_a_status_widget_survives_a_bindings_change_with_its_state() -> None:
    """The headline: no mirrored reactives, no `data_bind` through the footer.
    Stock's `recompose()` would have thrown this widget away and rebuilt it."""
    app = Harness(Countdown(id="cd"))
    async with app.run_test() as pilot:
        await settle(pilot)
        countdown = app.query_one(Countdown)
        countdown.remaining = 17
        app.query_one(Body).focus()
        await settle(pilot)
        assert app.query_one(Countdown) is countdown
        assert countdown.remaining == 17


async def test_the_key_widgets_are_rebuilt_when_the_keys_really_change() -> None:
    """The other half of the test above: composing once must not mean never
    updating."""
    app = Harness()
    async with app.run_test() as pilot:
        await settle(pilot)
        footer = app.query_one(Footer)
        before = list(footer.query("#footer-keys FooterBinding"))
        app.query_one(Body).focus()
        await settle(pilot)
        after = list(footer.query("#footer-keys FooterBinding"))
        assert all(widget not in before for widget in after)


async def test_nothing_is_rebuilt_when_the_rendered_keys_are_unchanged() -> None:
    """`refresh_bindings` fires far more often than the keys actually change;
    without this the status widgets survive but the bar flickers."""
    app = Harness()
    async with app.run_test() as pilot:
        await settle(pilot)
        footer = app.query_one(Footer)
        before = list(footer.query("#footer-keys FooterBinding"))
        app.screen.refresh_bindings()
        await settle(pilot)
        after = list(footer.query("#footer-keys FooterBinding"))
        assert [id(widget) for widget in after] == [id(widget) for widget in before]


async def test_status_update_is_visible_at_once_and_additive() -> None:
    app = Harness(Countdown(id="cd"))
    async with app.run_test() as pilot:
        await settle(pilot)
        footer = app.query_one(Footer)
        footer.status.update("Online")
        label = footer.status.query_one("#footer-status-text", Static)
        assert str(label.content) == "Online"
        assert app.query_one(Countdown).parent is footer.status
        app.query_one(Body).focus()
        await settle(pilot)
        assert str(label.content) == "Online"


async def test_an_empty_status_text_takes_no_room() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        await settle(pilot)
        footer = app.query_one(Footer)
        label = footer.status.query_one("#footer-status-text", Static)
        assert label.display is False
        footer.status.update("Online")
        assert label.display is True
        footer.status.update("")
        assert label.display is False


# -------------------------------------------------------------------- sorting


async def test_sorting_compares_digits_as_numbers() -> None:
    app = Harness(sort=True)
    async with app.run_test() as pilot:
        await settle(pilot)
        keys = area_keys(app.query_one(Footer))
        assert keys.index("f2") < keys.index("f10")


async def test_sorting_leaves_the_pinned_order_alone() -> None:
    app = Harness(pinned=("f10", "f1"), sort=True)
    async with app.run_test() as pilot:
        await settle(pilot)
        assert area_keys(app.query_one(Footer), "#footer-pinned") == ["f10", "f1"]


async def test_a_custom_sort_key_is_used() -> None:
    app = Harness(sort=lambda entry: entry.description)
    async with app.run_test() as pilot:
        await settle(pilot)
        descriptions = area_text(app.query_one(Footer))
        assert descriptions == sorted(descriptions)


# ------------------------------------------------------------------- dividers


async def test_no_divider_when_only_the_dynamic_run_has_content() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        await settle(pilot)
        footer = app.query_one(Footer)
        assert not footer.query_one("#footer-keys").has_class("-divider")
        assert not footer.status.has_class("-divider")


async def test_the_keys_area_is_divided_from_the_pins() -> None:
    app = Harness(pinned=("f1",))
    async with app.run_test() as pilot:
        await settle(pilot)
        footer = app.query_one(Footer)
        assert footer.query_one("#footer-keys").has_class("-divider")


async def test_the_status_area_is_divided_once_it_has_something_to_show() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        await settle(pilot)
        footer = app.query_one(Footer)
        assert not footer.status.has_class("-divider")
        footer.status.update("Online")
        await settle(pilot)
        assert footer.status.has_class("-divider")


async def test_the_divider_is_textuals_own_vertical_key_border() -> None:
    app = Harness(pinned=("f1",))
    async with app.run_test() as pilot:
        await settle(pilot)
        footer = app.query_one(Footer)
        assert footer.query_one("#footer-keys").styles.border_left[0] == "vkey"


async def test_hiding_the_only_status_widget_drops_its_divider() -> None:
    """`display` is the hiding mechanism, so the divider has to follow it --
    a widget does not get an "am I empty" convention of its own."""
    app = Harness(Countdown(id="cd"))
    async with app.run_test() as pilot:
        await settle(pilot)
        footer = app.query_one(Footer)
        assert footer.status.has_class("-divider")
        app.query_one(Countdown).display = False
        await settle(pilot)
        assert not footer.status.has_class("-divider")


# ---------------------------------------------------------------------- misc


async def test_compact_reaches_every_key() -> None:
    app = Harness(compact=True)
    async with app.run_test() as pilot:
        await settle(pilot)
        footer = app.query_one(Footer)
        assert footer.has_class("-compact")
        bindings = list(footer.query(FooterBinding))
        assert bindings
        assert all(widget.has_class("-compact") for widget in bindings)


async def test_it_refreshes_even_while_the_terminal_lacks_os_focus() -> None:
    """Stock's `bindings_changed` skips its recompose whenever `app_focus` is
    false, and on Windows Terminal that flag can lag reality by tens of
    seconds -- leaving a stale footer."""
    app = Harness()
    async with app.run_test() as pilot:
        await settle(pilot)
        footer = app.query_one(Footer)
        app.app_focus = False
        app.query_one(Body).focus()
        await settle(pilot)
        assert "Reload" in area_text(footer)


async def test_it_works_on_a_screen_that_was_pushed() -> None:
    app = PushedHarness()
    async with app.run_test() as pilot:
        await settle(pilot)
        footer = app.screen.query_one(Footer)
        assert area_keys(footer, "#footer-pinned") == ["f7"]
        assert "f8" in area_keys(footer)
