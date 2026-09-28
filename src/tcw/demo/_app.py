"""The demo app: a small browser over tcw's own source files, wearing every
widget and reaching every dialog tcw has."""

from __future__ import annotations

import asyncio
import logging
from fnmatch import fnmatch
from pathlib import Path
from typing import ClassVar

import textual
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Tree

import tcw
from tcw.chords import ChordMixin
from tcw.demo._browser import FileInfo, FileTable, Sidebar, scan
from tcw.demo._filter import FilterDialog
from tcw.demo._settings import AUTO_REFRESH, REFRESH_INTERVAL
from tcw.dialogs import AboutDialog, ConfirmDialog, SettingsDialog
from tcw.settings import config
from tcw.widgets import (
    OPEN_ACTION,
    TOGGLE_ACTION,
    AboutMenuItem,
    ChordViewer,
    Countdown,
    DataTable,
    Footer,
    Header,
    HeaderArea,
    LogViewer,
    Menu,
    MenuBar,
    MenuItem,
    MenuSeparator,
    SettingsMenuItem,
)

#: What the demo browses: the installed `tcw` package itself.
ROOT = Path(tcw.__file__).parent
ABOUT = Path(__file__).with_name("about.txt")

# Several loggers, so the LogViewer's source filter has something to filter.
log = logging.getLogger("tcw.demo")
refresh_log = logging.getLogger("tcw.demo.refresh")
table_log = logging.getLogger("tcw.demo.table")
dialog_log = logging.getLogger("tcw.demo.dialogs")


class BrowserScreen(Screen[None]):
    """The demo's only screen of its own."""

    DEFAULT_CSS = """
    BrowserScreen > #browser {
        height: 1fr;
    }
    """

    # Chords are ordinary bindings; `show=False` keeps them out of the footer,
    # and the ChordViewer lists them anyway once the user hesitates.
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("f2", "filter", "Filter"),
        Binding("f5", "refresh", "Refresh"),
        Binding("ctrl+k s n", "sort('name')", "Name", show=False),
        Binding("ctrl+k s s", "sort('size')", "Size", show=False),
        Binding("ctrl+k s m", "sort('modified')", "Modified", show=False),
        Binding("ctrl+k s u", "sort('')", "Unsorted", show=False),
        Binding("ctrl+k d c", "confirm", "Confirm", show=False),
        Binding("ctrl+k d d", "delete", "Delete (danger)", show=False),
        Binding("ctrl+k d f", "filter", "Filter", show=False),
        Binding("ctrl+k d a", "about", "About", show=False),
        Binding("ctrl+k d s", "settings", "Settings", show=False),
        Binding("ctrl+k r", "refresh", "Refresh now", show=False),
        Binding("ctrl+k t", "app.change_theme", "Change theme", show=False),
    ]
    CHORD_GROUPS: ClassVar[dict[str, str]] = {
        "ctrl+k": "Demo",
        "ctrl+k s": "Sort",
        "ctrl+k d": "Dialogs",
    }

    #: Seconds a refresh pretends to take. Scanning a directory this small is
    #: instant, and the countdown's spinner would never be seen.
    REFRESH_DELAY: ClassVar[float] = 0.8

    def __init__(self) -> None:
        super().__init__()
        self._directory: Path | None = None
        self._files: list[FileInfo] = []
        self._pattern = ""

    def compose(self) -> ComposeResult:
        yield Header(left="tcw demo", right=f"v{tcw.__version__}")
        with MenuBar(trailing=f"tcw {tcw.__version__}"):
            with Menu("File", id="file"):
                yield MenuItem("Refresh now", id="refresh", mnemonic="r", shortcut="F5")
                yield MenuSeparator()
                yield SettingsMenuItem(shortcut="^k d s")
                yield MenuSeparator()
                yield MenuItem(
                    "Quit", id="quit", mnemonic="q", shortcut="^q", action="app.quit"
                )
            with Menu("Dialogs", id="dialogs"):
                yield MenuItem("Confirm ...", id="confirm", mnemonic="c")
                yield MenuItem("Delete files ...", id="delete", mnemonic="d")
                yield MenuItem("Filter ...", id="filter", mnemonic="f", shortcut="F2")
            with Menu("View", id="view"):
                # `action=` strings run on this screen, like a key binding's.
                yield MenuItem("Sort by name", id="sort-name", action="sort('name')")
                yield MenuItem("Sort by size", id="sort-size", action="sort('size')")
                yield MenuItem(
                    "Sort by modified", id="sort-modified", action="sort('modified')"
                )
                yield MenuItem("Unsorted", id="sort-none", action="sort('')")
                yield MenuSeparator()
                yield MenuItem(
                    "Log", id="log", mnemonic="l", shortcut="F1", action=TOGGLE_ACTION
                )
                yield MenuItem(
                    "Theme ...", id="theme", mnemonic="t", action="app.change_theme"
                )
                yield MenuItem("Show hidden files", id="hidden", disabled=True)
            with Menu("Help", id="help"):
                yield AboutMenuItem(path=ABOUT, variables={"version": tcw.__version__})
        with Horizontal(id="browser"):
            yield Sidebar(ROOT, id="sidebar")
            yield FileTable(id="files")
        with Footer(pinned=(OPEN_ACTION, TOGGLE_ACTION, "ctrl+q"), sort=True):
            yield Countdown(id="refresh-countdown")
        yield LogViewer()
        yield ChordViewer()

    def on_mount(self) -> None:
        # Children are mounted by now, LogViewer's sink included, so none of
        # this is lost. The DEBUG line is: LogViewer starts at INFO, and a
        # level nobody had asked for yet is gone for good.
        log.info("tcw %s on Textual %s", tcw.__version__, textual.__version__)
        log.debug("browsing %s", ROOT)
        log.info("press ctrl+k and wait a moment to see every chord")
        self._browse(ROOT)
        self._apply_settings()
        self.query_one(Countdown).remaining = config.get(REFRESH_INTERVAL)
        self.set_interval(1, self._tick)

    def on_screen_resume(self) -> None:
        # Settings are read at the point of use, and coming back from the
        # settings dialog is the point at which they may have changed.
        self._apply_settings()

    def _apply_settings(self) -> None:
        countdown = self.query_one(Countdown)
        countdown.display = config.get(AUTO_REFRESH)
        interval = max(1, config.get(REFRESH_INTERVAL))
        countdown.remaining = min(countdown.remaining, interval)
        self.query_one(FileTable).restyle()

    # --------------------------------------------------------------- browsing

    @on(Tree.NodeHighlighted, "#sidebar")
    def _node_highlighted(self, event: Tree.NodeHighlighted[Path]) -> None:
        if event.node.data is not None:
            self._browse(event.node.data)

    def _browse(self, directory: Path) -> None:
        if directory == self._directory:
            return
        self._directory = directory
        # The header's middle tracks the screen title.
        self.title = directory.relative_to(ROOT.parent).as_posix()
        self._show(scan(directory))

    def _show(self, files: list[FileInfo]) -> None:
        self._files = files
        shown = [
            info
            for info in files
            if not self._pattern or fnmatch(info.path.name, self._pattern)
        ]
        self.query_one(FileTable).show(shown)
        self.query_one(Footer).status.update(
            f"{len(shown)} of {len(files)} files"
            if self._pattern
            else f"{len(files)} files"
        )
        if self._pattern and not shown:
            table_log.warning(
                "filter %r matches none of the %d files in %s",
                self._pattern,
                len(files),
                self.title,
            )

    @on(DataTable.SortChanged)
    def _sorted(self, event: DataTable.SortChanged) -> None:
        direction = "descending" if event.reverse else "ascending"
        table_log.info("sorted by %s, %s", event.column_key.value, direction)

    def action_sort(self, column: str) -> None:
        table = self.query_one(FileTable)
        if not column:
            table.sort_by(None)
            table_log.info("unsorted")
            self._show(self._files)  # back to the order the rows were added in
        elif column == table.sort_column:
            table.sort_by(column, reverse=not table.sort_reverse)
        else:
            table.sort_by(column)

    # ---------------------------------------------------------------- refresh

    def _tick(self) -> None:
        countdown = self.query_one(Countdown)
        if not config.get(AUTO_REFRESH) or countdown.refreshing:
            return
        countdown.remaining = max(0, countdown.remaining - 1)
        if countdown.remaining == 0:
            self.action_refresh()

    @work(exclusive=True, group="refresh")
    async def action_refresh(self) -> None:
        assert self._directory is not None
        directory = self._directory
        countdown = self.query_one(Countdown)
        countdown.refreshing = True
        refresh_log.debug("rescanning %s", directory)
        try:
            files = await asyncio.to_thread(scan, directory)
            await asyncio.sleep(self.REFRESH_DELAY)
        except OSError as error:
            refresh_log.error("rescanning %s failed: %s", directory, error)
            return
        finally:
            countdown.refreshing = False
            countdown.remaining = max(1, config.get(REFRESH_INTERVAL))
        if directory != self._directory:
            return  # the user moved on while this was in flight
        before = {info.path for info in self._files}
        after = {info.path for info in files}
        if before != after:
            refresh_log.info(
                "%d added, %d removed", len(after - before), len(before - after)
            )
        refresh_log.info("rescanned %s: %d files", self.title, len(files))
        self._show(files)

    # ---------------------------------------------------------------- dialogs

    @on(MenuItem.Pressed, "#refresh")
    def _refresh_pressed(self) -> None:
        self.action_refresh()

    @on(MenuItem.Pressed, "#confirm")
    def _confirm_pressed(self) -> None:
        self.action_confirm()

    @on(MenuItem.Pressed, "#delete")
    def _delete_pressed(self) -> None:
        self.action_delete()

    @on(MenuItem.Pressed, "#filter")
    def _filter_pressed(self) -> None:
        self.action_filter()

    @on(HeaderArea.Clicked, "#header-left")
    def _header_left_clicked(self) -> None:
        self.action_about()

    @on(HeaderArea.Clicked, "#header-right")
    def _header_right_clicked(self) -> None:
        versions = f"tcw {tcw.__version__}, Textual {textual.__version__}"
        log.info("header clicked: %s", versions)
        self.notify(versions, title="Versions")

    # `push_screen_wait` needs a worker: see MenuBar.md.

    @work
    async def action_confirm(self) -> None:
        if await self.app.push_screen_wait(
            ConfirmDialog(
                "Rescan the listing now?",
                title="Refresh",
                confirm_label="Refresh",
                cancel_label="Not now",
            )
        ):
            dialog_log.info("refresh confirmed")
            self.action_refresh()
        else:
            dialog_log.info("refresh declined")

    @work
    async def action_delete(self) -> None:
        count = self.query_one(FileTable).row_count
        if await self.app.push_screen_wait(
            ConfirmDialog(
                f"Delete all {count} files in {self.title}?\n\n"
                "(Nothing is actually deleted: this is a demo.)",
                title="Delete",
                confirm_label="Delete",
                cancel_label="Keep",
                danger=True,
                focus_cancel=True,
            )
        ):
            dialog_log.warning("pretended to delete %d files", count)
            self.notify(f"Pretended to delete {count} files.", severity="warning")
        else:
            dialog_log.info("kept %d files", count)

    @work
    async def action_filter(self) -> None:
        pattern = await self.app.push_screen_wait(FilterDialog(self._pattern))
        if pattern is None:
            dialog_log.debug("filter dialog cancelled")
            return
        self._pattern = pattern
        self.sub_title = pattern
        if pattern:
            dialog_log.info("filter set to %r", pattern)
        else:
            dialog_log.info("filter cleared")
        self._show(self._files)

    def action_about(self) -> None:
        self.app.push_screen(AboutDialog(ABOUT, variables={"version": tcw.__version__}))

    def action_settings(self) -> None:
        self.app.push_screen(SettingsDialog())


class DemoApp(ChordMixin, App[None]):
    """Run with `python -m tcw`."""

    TITLE = "tcw demo"

    def get_default_screen(self) -> Screen[None]:
        return BrowserScreen()
