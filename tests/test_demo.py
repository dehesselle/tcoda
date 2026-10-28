# SPDX-FileCopyrightText: 2026 René de Hesselle <dehesselle@web.de>
#
# SPDX-License-Identifier: 0BSD

"""The demo app: that it runs, and that each part of it is wired up."""

from __future__ import annotations

import time
from dataclasses import replace

import pytest
from textual.widgets import Label, Tree

from tcoda import settings as settings_module
from tcoda.demo import DemoApp
from tcoda.demo._app import BrowserScreen
from tcoda.demo._browser import FileTable, format_age, format_size
from tcoda.demo._filter import FilterDialog
from tcoda.demo._settings import AUTO_REFRESH, DEMO_SETTINGS, SIZE_UNITS
from tcoda.demo._sizes import SizesDialog, sizes_by_extension
from tcoda.demo._timeline import SHORTEST_SPAN, TimelineDialog
from tcoda.dialogs import AboutDialog, ConfirmDialog, SettingsDialog
from tcoda.plot import Plot
from tcoda.settings import config
from tcoda.widgets import ChordViewer, Countdown, Header, LogViewer, MenuBar

SIZE = (120, 36)


@pytest.fixture(autouse=True)
def demo_settings(isolated_settings: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """The demo declares its settings once, at import, but every test starts
    from an empty registry, so they are put back here."""
    settings_module._registry.update({entry.key: entry for entry in DEMO_SETTINGS})
    monkeypatch.setattr(BrowserScreen, "REFRESH_DELAY", 0)


def status_text(app: DemoApp) -> str:
    return str(app.screen.query_one("#footer-status-text").content)


def names(table: FileTable) -> list[str]:
    return [str(table.get_row_at(i)[0]) for i in range(table.row_count)]


async def test_it_lists_the_package_root() -> None:
    app = DemoApp()
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        assert isinstance(app.screen, BrowserScreen)
        table = app.screen.query_one(FileTable)
        assert "__init__.py" in names(table)
        assert str(app.screen.query_one(Header).middle.content) == "tcoda"
        assert status_text(app) == f"{table.row_count} files"


async def test_moving_in_the_tree_browses_that_directory() -> None:
    app = DemoApp()
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        tree = app.screen.query_one(Tree)
        target = next(n for n in tree.root.children if n.label.plain == "widgets")
        tree.move_cursor(target)
        await pilot.pause()
        assert app.screen.title == "tcoda/widgets"
        assert "_footer.py" in names(app.screen.query_one(FileTable))


async def test_f9_opens_the_menu_bar_and_f1_the_log() -> None:
    app = DemoApp()
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await pilot.press("f9")
        await pilot.pause()
        browser = app.screen_stack[-2]
        assert isinstance(browser, BrowserScreen)
        assert browser.query_one(MenuBar).revealed
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("f1")
        await pilot.pause()
        assert app.screen.query_one(LogViewer).revealed


async def test_a_hesitant_chord_shows_the_viewer_and_sorts() -> None:
    app = DemoApp()
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await pilot.press("ctrl+k")
        await pilot.pause(0.4)
        assert app.screen.query_one(ChordViewer).display
        await pilot.press("s", "s")
        await pilot.pause()
        table = app.screen.query_one(FileTable)
        assert table.sort_column == "size"
        sizes = [table.files[key.value].size for key in table.rows]
        ordered = [table.files[row.key.value].size for row in table.ordered_rows]
        assert ordered == sorted(sizes)
        # The same chord again flips the direction, like clicking the header.
        await pilot.press("ctrl+k", "s", "s")
        await pilot.pause()
        assert table.sort_reverse


@pytest.mark.parametrize(
    ("action", "dialog"),
    [
        ("confirm", ConfirmDialog),
        ("delete", ConfirmDialog),
        ("filter", FilterDialog),
        ("sizes", SizesDialog),
        ("timeline", TimelineDialog),
        ("about", AboutDialog),
        ("settings", SettingsDialog),
    ],
)
async def test_each_dialog_opens_and_escapes(action: str, dialog: type) -> None:
    app = DemoApp()
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await app.screen.run_action(action)
        await pilot.pause()
        assert isinstance(app.screen, dialog)
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, BrowserScreen)


async def test_the_sizes_chart_has_a_bar_per_extension() -> None:
    app = DemoApp()
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        files = app.screen._files
        await pilot.press("ctrl+k", "d", "p")
        await pilot.pause()
        assert isinstance(app.screen, SizesDialog)
        axis = "".join(app.screen.query_one(Plot).query_one("#plot-x-axis")._chars[0])
        assert axis.split() == list(sizes_by_extension(files))


async def test_the_timeline_counts_the_files_in_view_once_zooming_stops() -> None:
    app = DemoApp()
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        screen = app.screen
        # A fresh checkout gives every file about the same mtime, too close
        # together to zoom into; spread them an hour apart.
        screen._files = [
            replace(info, modified=info.modified - i * 3600)
            for i, info in enumerate(screen._files)
        ]
        total = len(screen._files)
        await pilot.press("ctrl+k", "d", "t")
        await pilot.pause()
        assert isinstance(app.screen, TimelineDialog)
        status = app.screen.query_one("#timeline-status", Label)
        assert str(status.content) == f"{total} of {total} files in view"

        plot = app.screen.query_one(Plot)
        plot.focus()
        before = plot.x_range
        await pilot.press(*["plus"] * 30)
        await pilot.pause(Plot.SETTLE_DELAY * 3)
        low, high = plot.x_range
        assert high - low < before[1] - before[0]
        in_view = sum(low <= info.modified <= high for info in app.screen._files)
        assert str(status.content) == f"{in_view} of {total} files in view"


async def test_the_timeline_opens_no_narrower_than_it_zooms() -> None:
    app = DemoApp()
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        screen = app.screen
        now = time.time()
        screen._files = [
            replace(info, modified=now - 5 + i % 3)
            for i, info in enumerate(screen._files)
        ]
        total = len(screen._files)
        await pilot.press("ctrl+k", "d", "t")
        await pilot.pause()
        assert isinstance(app.screen, TimelineDialog)
        plot = app.screen.query_one(Plot)
        low, high = plot.x_range
        assert high - low == pytest.approx(SHORTEST_SPAN)
        assert high <= time.time()
        status = app.screen.query_one("#timeline-status", Label)
        assert str(status.content) == f"{total} of {total} files in view"

        # At the floor already, so zooming in leaves it be.
        plot.focus()
        await pilot.press("plus")
        await pilot.pause()
        assert plot.x_range == (low, high)


async def test_the_timeline_reads_out_the_point_under_the_pointer() -> None:
    app = DemoApp()
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await pilot.press("ctrl+k", "d", "t")
        await pilot.pause()
        plot = app.screen.query_one(Plot)
        canvas = plot.query_one("#plot-canvas")
        await pilot.hover(canvas, offset=(10, 5))
        status = str(app.screen.query_one("#timeline-status", Label).content)
        assert status.endswith(" KiB")


async def test_the_settings_dialog_lists_the_demo_groups() -> None:
    app = DemoApp()
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await app.screen.run_action("settings")
        await pilot.pause()
        tree = app.screen.query_one("#settings-tree", Tree)
        demo = next(n for n in tree.root.children if n.label.plain == "Demo")
        assert {n.label.plain for n in demo.children} == {"Refresh", "Table"}


async def test_the_filter_narrows_the_listing() -> None:
    app = DemoApp()
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await pilot.press("f2")
        await pilot.pause()
        await pilot.press(*"*.py", "enter")
        await pilot.pause()
        table = app.screen.query_one(FileTable)
        assert names(table)
        assert all(name.endswith(".py") for name in names(table))
        assert app.screen.sub_title == "*.py"
        assert " of " in status_text(app)


async def test_the_countdown_reaching_zero_refreshes() -> None:
    app = DemoApp()
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, BrowserScreen)
        countdown = screen.query_one(Countdown)
        countdown.remaining = 1
        screen._tick()
        await pilot.pause()
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert not countdown.refreshing
        assert countdown.remaining == 30


async def test_settings_take_effect_when_the_screen_resumes() -> None:
    app = DemoApp()
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await app.screen.run_action("settings")
        await pilot.pause()
        config.set(AUTO_REFRESH, False)
        config.set(SIZE_UNITS, "decimal")
        await pilot.press("escape")
        await pilot.pause()
        screen = app.screen
        assert not screen.query_one(Countdown).display
        table = screen.query_one(FileTable)
        sizes = [str(table.get_row_at(i)[1]) for i in range(table.row_count)]
        assert any(size.endswith(" kB") for size in sizes)
        assert not any(size.endswith(" KiB") for size in sizes)


def test_format_size() -> None:
    assert format_size(0, "binary") == "0 B"
    assert format_size(1023, "binary") == "1023 B"
    assert format_size(1536, "binary") == "1.5 KiB"
    assert format_size(1500, "decimal") == "1.5 kB"
    assert format_size(3 * 1024**2, "binary") == "3.0 MiB"


def test_format_age() -> None:
    assert format_age(100, 100) == "just now"
    assert format_age(0, 60) == "1 minute ago"
    assert format_age(0, 7200) == "2 hours ago"
    assert format_age(0, 3 * 86400) == "3 days ago"
