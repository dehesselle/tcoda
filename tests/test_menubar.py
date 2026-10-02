"""The menu bar: composition, auto-hide, the staged bar/dropdown flow,
mnemonics, and how a chosen item reaches the app."""

from __future__ import annotations

import asyncio
from typing import ClassVar

from textual import events, on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.pilot import Pilot
from textual.screen import Screen
from textual.widgets import OptionList, Static

from tcoda.widgets import (
    OPEN_ACTION,
    Footer,
    Menu,
    MenuBar,
    MenuItem,
    MenuSeparator,
)
from tcoda.widgets._dropdown import MenuBarOverlay, MenuDropdown


def _menus() -> ComposeResult:
    with MenuBar(trailing="harness 1.0"):
        with Menu("File", id="file"):
            yield MenuItem("Open...", id="open", mnemonic="o")
            yield MenuSeparator()
            yield MenuItem("Save", id="save", mnemonic="s", shortcut="Ctrl+S")
            yield MenuItem("Locked", id="locked", mnemonic="l", disabled=True)
        with Menu("Help", id="help"):
            yield MenuItem("About", id="about", mnemonic="a")


class Harness(App[None]):
    """The bar on the app's own default screen."""

    def __init__(self) -> None:
        super().__init__()
        self.pressed: list[str] = []
        self.pressed_menus: list[str] = []

    def compose(self) -> ComposeResult:
        yield from _menus()
        yield Static("body", id="body")

    @on(MenuItem.Pressed)
    def _record(self, event: MenuItem.Pressed) -> None:
        self.pressed.append(event.item.id or "")
        self.pressed_menus.append(event.menu.id or "")


class PushedScreen(Screen[None]):
    def compose(self) -> ComposeResult:
        yield from _menus()
        yield Static("body", id="body")


class PushedHarness(App[None]):
    """The bar on a screen that was explicitly pushed -- `app.query_one`
    cannot see it, which is what used to make this case special."""

    def __init__(self) -> None:
        super().__init__()
        self.pressed: list[str] = []

    def on_mount(self) -> None:
        self.push_screen(PushedScreen())

    @on(MenuItem.Pressed)
    def _record(self, event: MenuItem.Pressed) -> None:
        self.pressed.append(event.item.id or "")


async def settle(pilot: Pilot[None], rounds: int = 3) -> None:
    """The flow is a chain of workers and pushed screens, so a single pause
    is not always enough to land on the next stage."""
    for _ in range(rounds):
        await pilot.pause()
        await asyncio.sleep(0.02)


# ------------------------------------------------------------------ compose


async def test_menus_and_their_items_compose_with_a_with_statement() -> None:
    app = Harness()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        bar = app.query_one(MenuBar)
        assert [menu.id for menu in bar.menus] == ["file", "help"]
        assert [entry.id for entry in bar.menu("file").entries] == [
            "open",
            None,
            "save",
            "locked",
        ]


async def test_items_never_render_in_the_bar() -> None:
    app = Harness()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert app.query_one("#open", MenuItem).display is False


async def test_a_title_is_as_wide_as_its_label_despite_hidden_children() -> None:
    app = Harness()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        app.query_one(MenuBar).auto_hide = False
        await pilot.pause()
        # "File" plus the 2-cell padding either side. Auto width would
        # otherwise be measured from the hidden children and collapse to the
        # padding alone.
        assert app.query_one("#file", Menu).region.width == 8


async def test_the_trailing_label_fills_the_rest_of_the_bar() -> None:
    app = Harness()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        app.query_one(MenuBar).auto_hide = False
        await pilot.pause()
        trailing = app.query_one("#menubar-trailing", Static)
        assert trailing.region.x == app.query_one("#help", Menu).region.right
        assert trailing.region.right == 80


# ---------------------------------------------------------------- auto-hide


async def test_the_bar_is_hidden_until_a_menu_is_opened() -> None:
    app = Harness()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert app.query_one(MenuBar).display is False


async def test_auto_hide_off_keeps_the_bar_visible() -> None:
    class AlwaysOn(App[None]):
        def compose(self) -> ComposeResult:
            with MenuBar(auto_hide=False), Menu("File", id="file"):
                yield MenuItem("Open...", id="open")

    app = AlwaysOn()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert app.query_one(MenuBar).display is True


async def test_escaping_the_bar_stage_hides_it_again() -> None:
    app = Harness()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("f9")
        await settle(pilot)
        assert app.query_one(MenuBar).display is True
        await pilot.press("escape")
        await settle(pilot)
        assert app.query_one(MenuBar).display is False


async def test_turning_auto_hide_on_after_using_the_menu_hides_the_bar() -> None:
    """The bar stops being "in use" when its menu closes, whatever auto_hide
    said at the time -- otherwise an entry that switches auto_hide on (a
    settings dialog opened from the menu) leaves the bar stranded on screen.
    """
    app = Harness()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        bar = app.query_one(MenuBar)
        bar.auto_hide = False
        await pilot.pause()
        await pilot.press("f9")
        await settle(pilot)
        await pilot.press("escape")
        await settle(pilot)
        assert bar.display is True
        bar.auto_hide = True
        await pilot.pause()
        assert bar.display is False


# ------------------------------------------------------------- staged flow


async def test_f9_opens_the_bar_only_stage_armed_on_the_first_menu() -> None:
    app = Harness()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("f9")
        await settle(pilot)
        assert isinstance(app.screen, MenuBarOverlay)
        assert app.query_one("#file", Menu).armed is True
        assert app.query_one("#help", Menu).armed is False


async def test_arrowing_moves_the_armed_title_without_opening_it() -> None:
    app = Harness()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("f9")
        await settle(pilot)
        await pilot.press("right")
        await settle(pilot)
        assert isinstance(app.screen, MenuBarOverlay)
        assert app.query_one("#help", Menu).armed is True


async def test_enter_drops_the_armed_menu() -> None:
    app = Harness()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("f9")
        await settle(pilot)
        await pilot.press("enter")
        await settle(pilot)
        assert isinstance(app.screen, MenuDropdown)


async def test_a_top_level_mnemonic_opens_that_menu_directly() -> None:
    app = Harness()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("f9")
        await settle(pilot)
        await pilot.press("h")
        await settle(pilot)
        assert isinstance(app.screen, MenuDropdown)
        assert app.query_one("#help", Menu).armed is True


async def test_clicking_a_title_opens_its_menu() -> None:
    app = Harness()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        app.query_one(MenuBar).auto_hide = False
        await pilot.pause()
        await pilot.click("#help")
        await settle(pilot)
        assert isinstance(app.screen, MenuDropdown)
        assert app.query_one("#help", Menu).armed is True


async def test_left_right_switches_to_the_neighbouring_menu() -> None:
    app = Harness()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("f9")
        await settle(pilot)
        await pilot.press("enter")
        await settle(pilot)
        await pilot.press("right")
        await settle(pilot)
        assert isinstance(app.screen, MenuDropdown)
        assert app.query_one("#help", Menu).armed is True


# ---------------------------------------------------------- mouse over the bar


async def test_hovering_a_title_in_the_bar_only_stage_arms_it() -> None:
    """`app.screen.query_one` cannot resolve the bar's titles once a modal
    stage is pushed -- they live on the screen underneath -- so every mouse
    test below hovers/clicks by screen offset instead of by selector."""
    app = Harness()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("f9")
        await settle(pilot)
        help_region = app.query_one("#help", Menu).region
        await pilot.hover(offset=(help_region.x, help_region.y))
        await settle(pilot)
        assert app.query_one("#help", Menu).armed is True
        assert app.query_one("#file", Menu).armed is False


async def test_clicking_a_different_title_in_the_bar_only_stage_opens_it() -> None:
    app = Harness()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("f9")
        await settle(pilot)
        help_region = app.query_one("#help", Menu).region
        await pilot.click(offset=(help_region.x, help_region.y))
        await settle(pilot)
        assert isinstance(app.screen, MenuDropdown)
        assert app.query_one("#help", Menu).armed is True


async def test_clicking_off_every_title_in_the_bar_only_stage_closes_it() -> None:
    app = Harness()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("f9")
        await settle(pilot)
        await pilot.click(offset=(0, 10))
        await settle(pilot)
        assert app.query_one(MenuBar).display is False


async def test_hovering_another_title_while_a_dropdown_is_open_switches_menus() -> None:
    app = Harness()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("f9")
        await settle(pilot)
        await pilot.press("enter")
        await settle(pilot)
        assert isinstance(app.screen, MenuDropdown)
        help_region = app.query_one("#help", Menu).region
        await pilot.hover(offset=(help_region.x, help_region.y))
        await settle(pilot)
        assert isinstance(app.screen, MenuDropdown)
        assert app.query_one("#help", Menu).armed is True


def _burst[EventT: events.MouseEvent](
    screen: Screen, event_type: type[EventT], x: int, y: int
) -> None:
    """Queue two `event_type` events at screen position (x, y) on `screen`
    before it gets to handle either.

    `pilot.hover`/`click` let each event be handled before sending the next,
    which can never reproduce a burst. Each is marked forwarded, as Textual's
    own delivery does: otherwise it bubbles back up to the App, which forwards
    it again to whatever screen is on top by then.
    """
    for _ in range(2):
        event = event_type(None, x, y, 0, 0, 0, False, False, False, x, y)
        event._set_forwarded()
        screen.post_message(event)


async def test_a_burst_of_moves_over_another_title_switches_menus_only_once() -> None:
    """A fast sweep can queue several moves on the dropdown before it handles
    the first; the ones still queued after it dismissed must not pop again."""
    app = Harness()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("f9")
        await settle(pilot)
        await pilot.press("enter")
        await settle(pilot)
        dropdown = app.screen
        help_region = app.query_one("#help", Menu).region
        _burst(dropdown, events.MouseMove, help_region.x, help_region.y)
        await settle(pilot)
        assert isinstance(app.screen, MenuDropdown)
        assert app.screen is not dropdown
        assert len(app.screen_stack) == 2
        assert app.query_one("#help", Menu).armed is True


async def test_a_burst_of_clicks_in_the_bar_only_stage_opens_the_menu_only_once() -> (
    None
):
    app = Harness()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("f9")
        await settle(pilot)
        overlay = app.screen
        assert isinstance(overlay, MenuBarOverlay)
        help_region = app.query_one("#help", Menu).region
        _burst(overlay, events.Click, help_region.x, help_region.y)
        await settle(pilot)
        assert isinstance(app.screen, MenuDropdown)
        assert len(app.screen_stack) == 2
        assert app.query_one("#help", Menu).armed is True


async def test_clicking_the_open_menus_own_title_closes_it() -> None:
    app = Harness()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("f9")
        await settle(pilot)
        await pilot.press("enter")
        await settle(pilot)
        file_region = app.query_one("#file", Menu).region
        await pilot.click(offset=(file_region.x, file_region.y))
        await settle(pilot)
        assert app.query_one(MenuBar).display is False


async def test_clicking_off_the_bar_and_the_dropdown_closes_it() -> None:
    app = Harness()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("f9")
        await settle(pilot)
        await pilot.press("enter")
        await settle(pilot)
        await pilot.click(offset=(70, 20))
        await settle(pilot)
        assert app.query_one(MenuBar).display is False


# ------------------------------------------------------------------- items


async def test_a_separator_is_a_divider_rather_than_a_selectable_row() -> None:
    app = Harness()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("f9")
        await settle(pilot)
        await pilot.press("enter")
        await settle(pilot)
        option_list = app.screen.query_one(OptionList)
        assert [option.id for option in option_list.options] == [
            "open",
            "save",
            "locked",
        ]


async def test_moving_down_skips_the_separator() -> None:
    app = Harness()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("f9")
        await settle(pilot)
        await pilot.press("enter")
        await settle(pilot)
        await pilot.press("down")
        await pilot.pause()
        option_list = app.screen.query_one(OptionList)
        assert (
            option_list.get_option_at_index(option_list.highlighted or 0).id == "save"
        )


async def test_a_shortcut_is_shown_right_aligned() -> None:
    app = Harness()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("f9")
        await settle(pilot)
        await pilot.press("enter")
        await settle(pilot)
        prompt = app.screen.query_one(OptionList).get_option("save").prompt
        rendered = "".join(
            segment.text
            for segment in app.screen.query_one(OptionList).app.console.render(prompt)
        )
        assert "Save" in rendered
        assert "Ctrl+S" in rendered
        assert rendered.index("Save") < rendered.index("Ctrl+S")


async def test_a_disabled_item_cannot_be_chosen_by_its_mnemonic() -> None:
    app = Harness()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("f9")
        await settle(pilot)
        await pilot.press("enter")
        await settle(pilot)
        await pilot.press("l")
        await settle(pilot)
        assert isinstance(app.screen, MenuDropdown)
        assert app.pressed == []


async def test_pressing_a_disabled_item_directly_does_nothing() -> None:
    app = Harness()
    async with app.run_test(size=(80, 24)) as pilot:
        app.query_one("#locked", MenuItem).press()
        await pilot.pause()
        assert app.pressed == []


async def test_a_disabled_items_mnemonic_is_not_colored() -> None:
    app = Harness()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("f9")
        await settle(pilot)
        await pilot.press("enter")
        await settle(pilot)
        option_list = app.screen.query_one(OptionList)
        assert option_list.get_option("open").prompt.spans
        assert not option_list.get_option("locked").prompt.spans


# ------------------------------------------------------------- notification


async def test_choosing_an_item_posts_pressed_and_closes_the_menu() -> None:
    app = Harness()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("f9")
        await settle(pilot)
        await pilot.press("enter")
        await settle(pilot)
        await pilot.press("o")
        await settle(pilot)
        assert app.pressed == ["open"]
        assert app.pressed_menus == ["file"]
        assert app.query_one(MenuBar).display is False


async def test_pressed_can_be_matched_by_the_menu_it_came_from() -> None:
    class TwoPanes(App[None]):
        def __init__(self) -> None:
            super().__init__()
            self.hits: list[str] = []

        def compose(self) -> ComposeResult:
            with MenuBar(auto_hide=False):
                with Menu("Left", id="left"):
                    yield MenuItem("Rescan", id="rescan", mnemonic="r")
                with Menu("Right", id="right"):
                    yield MenuItem("Rescan", id="rescan", mnemonic="r")

        @on(MenuItem.Pressed, "#rescan", menu="#right")
        def _right(self) -> None:
            self.hits.append("right")

    app = TwoPanes()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await pilot.click("#right")
        await settle(pilot)
        await pilot.press("r")
        await settle(pilot)
        assert app.hits == ["right"]


async def test_an_action_string_runs_as_well() -> None:
    class WithAction(App[None]):
        def __init__(self) -> None:
            super().__init__()
            self.ran = 0

        def compose(self) -> ComposeResult:
            with MenuBar(auto_hide=False), Menu("File", id="file"):
                yield MenuItem("Go", id="go", mnemonic="g", action="app.go")

        def action_go(self) -> None:
            self.ran += 1

    app = WithAction()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await pilot.click("#file")
        await settle(pilot)
        await pilot.press("g")
        await settle(pilot)
        assert app.ran == 1


# ------------------------------------------------------------ key install


async def test_the_key_is_bound_on_the_screen_the_bar_is_mounted_on() -> None:
    """The bar cannot own the binding itself -- Textual only consults the
    focus chain, the screen and the app -- so it installs one. If a Textual
    upgrade breaks that, this fails rather than F9 quietly going dead."""
    app = Harness()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert "f9" in app.screen.active_bindings


async def test_the_key_can_be_pinned_to_the_head_of_the_footer() -> None:
    """Where the key *appears* is the app's call, not the bar's.

    `MenuBar` used to re-insert its key at the front of the screen's own
    binding map so a stock footer would render it first. That only ever
    reordered the screen's bindings, so anything on the focused widget still
    sorted ahead of it -- which is the case exercised here, and the reason
    pinning replaced the trick outright.
    """

    class Focusable(Static, can_focus=True):
        BINDINGS: ClassVar[list[Binding]] = [Binding("r", "refresh", "Refresh")]

        def action_refresh(self) -> None:
            pass

    class WithBindings(App[None]):
        def compose(self) -> ComposeResult:
            with MenuBar(), Menu("File", id="file"):
                yield MenuItem("Open...", id="open")
            yield Focusable("body")
            yield Footer(pinned=(OPEN_ACTION,))

    app = WithBindings()
    async with app.run_test(size=(80, 24)) as pilot:
        await settle(pilot)
        app.query_one(Focusable).focus()
        await settle(pilot)
        footer = app.query_one(Footer)
        assert [
            widget.key_display
            for widget in footer.query("#footer-pinned FooterBinding")
        ] == ["f9"]
        # The focused widget's own key is present, and behind the pin.
        assert "r" in [
            widget.key_display for widget in footer.query("#footer-keys FooterBinding")
        ]


async def test_f9_works_when_the_bar_is_on_a_pushed_screen() -> None:
    app = PushedHarness()
    async with app.run_test(size=(80, 24)) as pilot:
        await settle(pilot)
        await pilot.press("f9")
        await settle(pilot)
        await pilot.press("enter")
        await settle(pilot)
        await pilot.press("o")
        await settle(pilot)
        assert app.pressed == ["open"]


async def test_key_none_leaves_the_screen_unbound() -> None:
    class NoKey(App[None]):
        def compose(self) -> ComposeResult:
            with MenuBar(key=None), Menu("File", id="file"):
                yield MenuItem("Open...", id="open")

    app = NoKey()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert "f9" not in app.screen.active_bindings
