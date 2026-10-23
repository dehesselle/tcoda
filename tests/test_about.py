# SPDX-FileCopyrightText: 2026 René de Hesselle <dehesselle@web.de>
#
# SPDX-License-Identifier: 0BSD

"""The about dialog: default vs. custom text, the fixed header vs. scrollable
body split, dismissal, and the menu item that opens it."""

from __future__ import annotations

import asyncio

import pytest
from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.pilot import Pilot
from textual.widgets import Static

from tcoda.dialogs import AboutDialog
from tcoda.widgets import AboutMenuItem, Menu, MenuBar

# The only literal prose in the bundled header -- the "tcoda" above it is
# ASCII art, which spells the name without containing the string.
DEFAULT_HEADER_TEXT = "Textual coda"


class Harness(App[None]):
    """Pushes the dialog on mount, the way a menu item does."""

    def __init__(
        self,
        path: str | None = None,
        *,
        variables: dict[str, str] | None = None,
    ) -> None:
        super().__init__()
        self._path = path
        self._variables = variables

    def on_mount(self) -> None:
        self.push_screen(AboutDialog(self._path, variables=self._variables))


async def settle(pilot: Pilot[None], rounds: int = 3) -> None:
    for _ in range(rounds):
        await pilot.pause()
        await asyncio.sleep(0.02)


@pytest.fixture
def custom_text_file(tmp_path):
    lines = [f"line {n}" for n in range(1, 9)]
    path = tmp_path / "about.txt"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path, lines


async def test_the_default_placeholder_is_shown_with_no_path() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        await pilot.pause()
        header = app.screen.query_one("#about-header", Static)
        assert DEFAULT_HEADER_TEXT in str(header.render())


async def test_a_custom_path_overrides_the_bundled_text(custom_text_file) -> None:
    path, lines = custom_text_file
    app = Harness(str(path))
    async with app.run_test() as pilot:
        await pilot.pause()
        header = app.screen.query_one("#about-header", Static)
        assert lines[0] in str(header.render())


async def test_only_the_first_five_lines_are_in_the_fixed_header(
    custom_text_file,
) -> None:
    path, lines = custom_text_file
    app = Harness(str(path))
    async with app.run_test() as pilot:
        await pilot.pause()
        header_text = str(app.screen.query_one("#about-header", Static).render())
        for line in lines[:5]:
            assert line in header_text
        for line in lines[5:]:
            assert line not in header_text


async def test_the_remaining_lines_are_in_the_scrollable_body(
    custom_text_file,
) -> None:
    path, lines = custom_text_file
    app = Harness(str(path))
    async with app.run_test() as pilot:
        await pilot.pause()
        body = app.screen.query_one("#about-body", VerticalScroll)
        body_text = str(body.query_one(Static).render())
        for line in lines[5:]:
            assert line in body_text


async def test_variables_fill_in_placeholders(tmp_path) -> None:
    path = tmp_path / "about.txt"
    path.write_text("$app v$version", encoding="utf-8")
    app = Harness(str(path), variables={"app": "myapp", "version": "1.2.3"})
    async with app.run_test() as pilot:
        await pilot.pause()
        header = app.screen.query_one("#about-header", Static)
        assert "myapp v1.2.3" in str(header.render())


async def test_an_unmatched_placeholder_is_left_as_is(tmp_path) -> None:
    path = tmp_path / "about.txt"
    path.write_text("$missing", encoding="utf-8")
    app = Harness(str(path), variables={"app": "myapp"})
    async with app.run_test() as pilot:
        await pilot.pause()
        header = app.screen.query_one("#about-header", Static)
        assert "$missing" in str(header.render())


async def test_escape_dismisses_the_dialog() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, AboutDialog)


async def test_the_menu_item_opens_the_about_dialog() -> None:
    class MenuHarness(App[None]):
        def compose(self) -> ComposeResult:
            with MenuBar(auto_hide=False), Menu("Help", id="help"):
                yield AboutMenuItem()

    app = MenuHarness()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await pilot.click("#help")
        await settle(pilot)
        await pilot.press("a")
        await settle(pilot)
        assert isinstance(app.screen, AboutDialog)


async def test_the_menu_item_passes_variables_through(tmp_path) -> None:
    path = tmp_path / "about.txt"
    path.write_text("$app", encoding="utf-8")

    class MenuHarness(App[None]):
        def compose(self) -> ComposeResult:
            with MenuBar(auto_hide=False), Menu("Help", id="help"):
                yield AboutMenuItem(path=str(path), variables={"app": "myapp"})

    app = MenuHarness()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await pilot.click("#help")
        await settle(pilot)
        await pilot.press("a")
        await settle(pilot)
        header = app.screen.query_one("#about-header", Static)
        assert "myapp" in str(header.render())
