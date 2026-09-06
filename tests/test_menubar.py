"""The menu bar: composition, auto-hide, the staged bar/dropdown flow,
mnemonics, and how a chosen item reaches the app."""

from __future__ import annotations

import asyncio
from typing import ClassVar

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.pilot import Pilot
from textual.screen import Screen
from textual.widgets import OptionList, Static

from tcw.widgets import (
    Menu,
    MenuBar,
    MenuItem,
    MenuSeparator,
)
from tcw.widgets._dropdown import MenuBarSelectScreen, MenuDropdown


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
        assert isinstance(app.screen, MenuBarSelectScreen)
        assert app.query_one("#file", Menu).armed is True
        assert app.query_one("#help", Menu).armed is False


async def test_arrowing_moves_the_armed_title_without_opening_it() -> None:
    app = Harness()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("f9")
        await settle(pilot)
        await pilot.press("right")
        await settle(pilot)
        assert isinstance(app.screen, MenuBarSelectScreen)
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


async def test_the_key_leads_the_footer() -> None:
    """Installed at mount, so it would otherwise land after every binding the
    screen declared -- and a menu key belongs at the head of a footer."""

    class WithBindings(App[None]):
        BINDINGS: ClassVar[list[Binding]] = [Binding("r", "refresh", "Refresh")]

        def compose(self) -> ComposeResult:
            with MenuBar(), Menu("File", id="file"):
                yield MenuItem("Open...", id="open")

        def action_refresh(self) -> None:
            pass

    app = WithBindings()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert next(iter(app.screen.active_bindings)) == "f9"


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
