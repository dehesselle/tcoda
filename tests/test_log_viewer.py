# SPDX-FileCopyrightText: 2026 René de Hesselle <dehesselle@web.de>
#
# SPDX-License-Identifier: 0BSD

"""LogViewer: replay/live delivery, the level and source filters, the
sources popup, the self-installed toggle key, handler/logger ownership, and
that the panel actually paints above other content once revealed."""

from __future__ import annotations

import asyncio
import logging
import re
import threading
import uuid

import pytest
from textual.app import App, ComposeResult
from textual.pilot import Pilot
from textual.screen import Screen
from textual.widgets import Input, RichLog, Select, Static

from tcoda.log_sink import InMemoryLogHandler
from tcoda.widgets import TOGGLE_ACTION, LogViewer
from tcoda.widgets._log_viewer import _LAYER
from tcoda.widgets._tree_select import TreeSelect, TreeSelectOverlay


class Harness(App[None]):
    """A LogViewer on the app's own default screen, plus some body content
    it can slide over."""

    def __init__(self, **log_viewer_kwargs: object) -> None:
        super().__init__()
        self._log_viewer_kwargs = log_viewer_kwargs

    def compose(self) -> ComposeResult:
        yield LogViewer(**self._log_viewer_kwargs)
        yield Static("body", id="body")


def _lines(log: RichLog) -> list[str]:
    """Plain text of every rendered line -- `RichLog.lines` are `Strip`s, not
    the plain `str`s a `Log` widget's own `.lines` holds."""
    return [strip.text for strip in log.lines]


def _log_lines(app: App[None]) -> list[str]:
    return _lines(app.query_one("#log-viewer-log", RichLog))


def _log_text(app: App[None]) -> str:
    """Every rendered line joined into one string, for substring checks.

    Word-wrapping (`RichLog(wrap=True)`) can split a single logged message
    across several physical `Strip`s -- a long `logger_name` fixture plus
    the timestamp/level prefix routinely pushes a message past the test
    viewport's width. Joining with spaces keeps a wrapped message's
    substring checks meaningful without caring where the wrap landed; runs of
    whitespace collapse to one, since a wrap at a space keeps that space."""
    return " ".join(" ".join(_log_lines(app)).split())


def _sources_label(app: App[None]) -> str:
    return app.query_one("#log-viewer-sources", TreeSelect).label


async def settle(pilot: Pilot[None], rounds: int = 3) -> None:
    for _ in range(rounds):
        await pilot.pause()
        await asyncio.sleep(0.02)


async def reveal(pilot: Pilot[None]) -> None:
    """Reveal the panel and wait out its 400ms offset transition -- needed
    before anything inside it (the toolbar's trigger button, in particular)
    can be clicked by real screen coordinates."""
    app = pilot.app
    app.query_one(LogViewer).reveal()
    await asyncio.sleep(0.5)
    await pilot.pause()


@pytest.fixture
def logger_name() -> str:
    """A fresh, never-reused logger name per test -- isolated from every
    other test and from the real root logger, with no cleanup required."""
    return f"tcoda-test-{uuid.uuid4().hex}"


def _source(namespace: str, name: str) -> logging.Logger:
    """A child logger under `namespace`: propagates up to whatever handler
    is attached at the namespace logger, arriving there with `record.name`
    set to the child's own full name -- exactly how "source" (`record.name`)
    is meant to distinguish multiple loggers sharing one LogViewer."""
    return logging.getLogger(f"{namespace}.{name}")


# --------------------------------------------------------- replay and level


async def test_backlog_logged_before_mount_is_replayed_on_mount(
    logger_name: str,
) -> None:
    handler = InMemoryLogHandler()
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    logger.info("logged before any viewer existed")

    class GivenHandlerHarness(App[None]):
        def compose(self) -> ComposeResult:
            yield LogViewer(handler=handler)
            yield Static("body", id="body")

    app = GivenHandlerHarness()
    try:
        async with app.run_test(size=(80, 24)) as pilot:
            # RichLog defers a write until its size is known (`on_resize`),
            # unlike Log's synchronous write -- one bare pause isn't always
            # enough for that round-trip to land.
            await settle(pilot)
            assert "logged before any viewer existed" in _log_text(app)
    finally:
        logger.removeHandler(handler)


async def test_default_level_is_info_and_hides_debug_only(logger_name: str) -> None:
    app = Harness(logger=logger_name)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        logger = logging.getLogger(logger_name)
        logger.debug("debug-line")
        logger.info("info-line")
        await settle(pilot)
        assert "debug-line" not in _log_text(app)
        assert "info-line" in _log_text(app)


async def test_selecting_a_level_re_renders_to_that_minimum(logger_name: str) -> None:
    app = Harness(logger=logger_name)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        logger = logging.getLogger(logger_name)
        select = app.query_one("#log-viewer-level", Select)

        select.value = logging.DEBUG
        await settle(pilot)
        logger.debug("debug-line")
        logger.info("info-line")
        await settle(pilot)
        assert "debug-line" in _log_text(app)
        assert "info-line" in _log_text(app)

        select.value = logging.ERROR
        await settle(pilot)
        assert "debug-line" not in _log_text(app)
        assert "info-line" not in _log_text(app)


async def test_min_level_can_start_below_info(logger_name: str) -> None:
    app = Harness(logger=logger_name, min_level=logging.DEBUG)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        logger = logging.getLogger(logger_name)
        assert logger.level == logging.DEBUG
        assert app.query_one("#log-viewer-level", Select).value == logging.DEBUG
        logger.debug("debug-line")
        await settle(pilot)
        assert "debug-line" in _log_text(app)


async def test_setting_min_level_moves_the_dropdown_and_the_logger(
    logger_name: str,
) -> None:
    app = Harness(logger=logger_name)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        logger = logging.getLogger(logger_name)
        logger.warning("warning-line")
        await settle(pilot)

        app.query_one(LogViewer).min_level = logging.ERROR
        await settle(pilot)
        assert app.query_one("#log-viewer-level", Select).value == logging.ERROR
        assert logger.level == logging.ERROR
        assert "warning-line" not in _log_text(app)


async def test_the_dropdown_moves_min_level(logger_name: str) -> None:
    app = Harness(logger=logger_name)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        app.query_one("#log-viewer-level", Select).value = logging.WARNING
        await settle(pilot)
        assert app.query_one(LogViewer).min_level == logging.WARNING


def test_min_level_must_be_one_the_dropdown_offers() -> None:
    with pytest.raises(ValueError, match="min_level"):
        LogViewer(min_level=15)


async def test_level_and_above_semantics_are_inclusive(logger_name: str) -> None:
    app = Harness(logger=logger_name)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        logger = logging.getLogger(logger_name)
        logger.warning("warning-line")
        logger.error("error-line")
        logger.critical("critical-line")
        await settle(pilot)

        app.query_one("#log-viewer-level", Select).value = logging.WARNING
        await settle(pilot)
        assert "warning-line" in _log_text(app)
        assert "error-line" in _log_text(app)
        assert "critical-line" in _log_text(app)


# ---------------------------------------------------------- display format


async def test_display_line_carries_timestamp_level_and_source(
    logger_name: str,
) -> None:
    app = Harness(logger=logger_name)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        logging.getLogger(logger_name).warning("boom")
        await settle(pilot)
        [line] = [line for line in _log_lines(app) if "boom" in line]
        assert re.match(
            rf"^\d\d:\d\d:\d\d\.\d\d\d WARNING  {re.escape(logger_name)}: boom$",
            line,
        )


async def test_a_long_statement_wraps_across_multiple_screen_lines(
    logger_name: str,
) -> None:
    """The entire point of using RichLog over Log: a long message must be
    readable in full without horizontal scrolling."""
    app = Harness(logger=logger_name)
    async with app.run_test(size=(40, 24)) as pilot:
        await pilot.pause()
        log = app.query_one("#log-viewer-log", RichLog)
        assert log.wrap is True
        before = len(log.lines)
        logging.getLogger(logger_name).info("x" * 200)
        await settle(pilot)
        assert len(log.lines) - before > 1


# ------------------------------------------------------------------ sources


async def test_a_newly_discovered_source_defaults_to_visible(logger_name: str) -> None:
    app = Harness(logger=logger_name)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        _source(logger_name, "brand-new").info("hello-from-new-source")
        await settle(pilot)
        assert "hello-from-new-source" in _log_text(app)


async def test_unchecking_a_source_hides_its_existing_and_future_lines(
    logger_name: str,
) -> None:
    app = Harness(logger=logger_name)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        source_a = _source(logger_name, "a")
        source_a.info("existing-line")
        await settle(pilot)

        viewer = app.query_one(LogViewer)
        viewer.set_source_hidden(f"{logger_name}.a", True)
        await settle(pilot)
        assert "existing-line" not in _log_text(app)

        source_a.info("future-line")
        await settle(pilot)
        assert "future-line" not in _log_text(app)


async def test_an_explicit_uncheck_survives_a_new_unrelated_source_appearing(
    logger_name: str,
) -> None:
    app = Harness(logger=logger_name)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        _source(logger_name, "a").info("from-a")
        await settle(pilot)

        viewer = app.query_one(LogViewer)
        viewer.set_source_hidden(f"{logger_name}.a", True)
        await settle(pilot)

        _source(logger_name, "b").info("from-b")
        await settle(pilot)

        assert "from-a" not in _log_text(app)
        assert "from-b" in _log_text(app)


async def test_rechecking_a_source_restores_its_buffered_lines_on_next_render(
    logger_name: str,
) -> None:
    app = Harness(logger=logger_name)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        _source(logger_name, "a").info("from-a")
        await settle(pilot)

        viewer = app.query_one(LogViewer)
        viewer.set_source_hidden(f"{logger_name}.a", True)
        await settle(pilot)
        viewer.set_source_hidden(f"{logger_name}.a", False)
        await settle(pilot)

        assert "from-a" in _log_text(app)


async def test_a_filtered_out_live_entry_never_reaches_the_log_widget(
    logger_name: str,
) -> None:
    """A source hidden before an entry arrives keeps it out of the Log
    widget entirely -- but it's still in the sink's buffer, so un-hiding the
    source later picks it up on the next re-render."""
    app = Harness(logger=logger_name)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        hidden_source = _source(logger_name, "hidden")
        viewer = app.query_one(LogViewer)
        viewer.set_source_hidden(f"{logger_name}.hidden", True)
        await settle(pilot)

        hidden_source.info("should-stay-hidden-for-now")
        await settle(pilot)
        assert "should-stay-hidden-for-now" not in _log_text(app)

        viewer.set_source_hidden(f"{logger_name}.hidden", False)
        await settle(pilot)
        assert "should-stay-hidden-for-now" in _log_text(app)


async def test_hiding_a_parent_hides_its_existing_sources_and_later_ones(
    logger_name: str,
) -> None:
    app = Harness(logger=logger_name)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        _source(logger_name, "lib.a").info("from-a")
        _source(logger_name, "ours").info("from-ours")
        await settle(pilot)

        app.query_one(LogViewer).set_source_hidden(f"{logger_name}.lib", True)
        await settle(pilot)
        assert "from-a" not in _log_text(app)

        _source(logger_name, "lib.b").info("from-b")
        _source(logger_name, "lib.deep.er").info("from-deeper")
        _source(logger_name, "ours").info("more-from-ours")
        await settle(pilot)
        assert "from-b" not in _log_text(app)
        assert "from-deeper" not in _log_text(app)
        assert "from-ours" in _log_text(app)
        assert "more-from-ours" in _log_text(app)


async def test_a_prefix_can_be_hidden_before_any_of_its_sources_appear(
    logger_name: str,
) -> None:
    app = Harness(logger=logger_name)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        viewer = app.query_one(LogViewer)
        viewer.set_source_hidden(f"{logger_name}.lib", True)
        assert viewer.is_source_hidden(f"{logger_name}.lib.a")

        _source(logger_name, "lib.a").info("from-a")
        await settle(pilot)
        assert "from-a" not in _log_text(app)
        assert _sources_label(app) == "Sources (0/1)"


async def test_a_re_render_keeps_a_new_source_of_a_hidden_parent_hidden(
    logger_name: str,
) -> None:
    """The buffer has the entry before the panel has heard of its source, so a
    re-render can reach it first."""
    app = Harness(logger=logger_name)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        viewer = app.query_one(LogViewer)
        viewer.set_source_hidden(f"{logger_name}.lib", True)

        _source(logger_name, "lib.late").info("from-late")
        viewer.set_source_hidden(f"{logger_name}.other", True)
        await settle(pilot)
        assert "from-late" not in _log_text(app)


async def test_rechecking_one_child_of_a_hidden_parent_shows_only_that_child(
    logger_name: str,
) -> None:
    app = Harness(logger=logger_name)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        _source(logger_name, "lib.a").info("from-a")
        _source(logger_name, "lib.b").info("from-b")
        await settle(pilot)

        viewer = app.query_one(LogViewer)
        viewer.set_source_hidden(f"{logger_name}.lib", True)
        viewer.set_source_hidden(f"{logger_name}.lib.a", False)
        await settle(pilot)
        assert "from-a" in _log_text(app)
        assert "from-b" not in _log_text(app)


async def test_a_source_that_is_also_a_parent_filters_its_own_lines_too(
    logger_name: str,
) -> None:
    """A logger can both write and have children, as `tcoda.demo` does."""
    app = Harness(logger=logger_name)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        _source(logger_name, "lib").info("from-parent")
        _source(logger_name, "lib.child").info("from-child")
        await settle(pilot)

        viewer = app.query_one(LogViewer)
        viewer.set_source_hidden(f"{logger_name}.lib", True)
        await settle(pilot)
        assert "from-parent" not in _log_text(app)
        assert "from-child" not in _log_text(app)

        viewer.set_source_hidden(f"{logger_name}.lib.child", False)
        await settle(pilot)
        assert "from-parent" not in _log_text(app)
        assert "from-child" in _log_text(app)


async def test_toggling_a_group_row_filters_the_log(logger_name: str) -> None:
    app = Harness(logger=logger_name)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        _source(logger_name, "a").info("from-a")
        await settle(pilot)
        await reveal(pilot)
        await pilot.click("#log-viewer-sources")
        await settle(pilot)

        # The cursor starts on the only top-level row, the group `logger_name`.
        await pilot.press("space")
        await settle(pilot)
        assert "from-a" not in _log_text(app)
        assert _sources_label(app) == "Sources (0/1)"


async def test_a_replayed_source_appears_in_the_tree(logger_name: str) -> None:
    """Logged before `LogViewer` existed, through a sink it is handed."""
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    handler = InMemoryLogHandler()
    logger.addHandler(handler)
    _source(logger_name, "early.bird").info("from-before-mount")

    class HandlerHarness(App[None]):
        def compose(self) -> ComposeResult:
            yield LogViewer(handler=handler)

    app = HandlerHarness()
    try:
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            viewer = app.query_one(LogViewer)
            viewer.set_source_hidden(f"{logger_name}.early", True)
            await settle(pilot)
            assert "from-before-mount" not in _log_text(app)
            assert _sources_label(app) == "Sources (0/1)"
    finally:
        logger.removeHandler(handler)


async def test_log_entries_arriving_off_the_ui_thread_still_render(
    logger_name: str,
) -> None:
    app = Harness(logger=logger_name)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        logger = logging.getLogger(logger_name)
        thread = threading.Thread(
            target=logger.warning, args=("from-a-background-thread",)
        )
        thread.start()
        thread.join()
        await settle(pilot)
        assert "from-a-background-thread" in _log_text(app)


# ------------------------------------------------------------------- popup


async def test_a_newly_discovered_source_is_added_to_the_open_popup_checked(
    logger_name: str,
) -> None:
    app = Harness(logger=logger_name)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        _source(logger_name, "a").info("first-source-line")
        await settle(pilot)
        await reveal(pilot)
        await pilot.click("#log-viewer-sources")
        await settle(pilot)
        sources = app.query_one("#log-viewer-sources", TreeSelect)
        assert sources.expanded is True

        _source(logger_name, "b").info("second-source-line")
        await settle(pilot)
        assert sources.is_checked([logger_name, "b"])


async def test_the_popup_stays_open_across_multiple_toggles(logger_name: str) -> None:
    app = Harness(logger=logger_name)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        _source(logger_name, "a").info("from-a")
        _source(logger_name, "b").info("from-b")
        await settle(pilot)
        await reveal(pilot)
        await pilot.click("#log-viewer-sources")
        await settle(pilot)

        sources = app.query_one("#log-viewer-sources", TreeSelect)
        overlay = sources.query_one(TreeSelectOverlay)
        await pilot.press("right", "down", "space")
        await settle(pilot)
        assert not overlay.is_checked([logger_name, "a"])
        assert sources.expanded is True

        await pilot.press("down", "space")
        await settle(pilot)
        assert not overlay.is_checked([logger_name, "b"])
        assert sources.expanded is True


async def test_escape_closes_the_popup_without_changing_selection(
    logger_name: str,
) -> None:
    app = Harness(logger=logger_name)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        _source(logger_name, "a").info("from-a")
        await settle(pilot)
        await reveal(pilot)
        await pilot.click("#log-viewer-sources")
        await settle(pilot)
        sources = app.query_one("#log-viewer-sources", TreeSelect)
        assert sources.expanded is True

        await pilot.press("escape")
        await settle(pilot)
        assert sources.expanded is False
        assert "from-a" in _log_text(app)


async def test_clicking_a_different_toolbar_control_closes_the_popup(
    logger_name: str,
) -> None:
    """Blur-driven, matching a real `Select`: moving focus to another
    control (here, the Loglevel dropdown) closes the popup for free -- a
    click that lands on nothing focusable would not (same as real `Select`),
    so this exercises the actual mechanism rather than a blank click."""
    app = Harness(logger=logger_name)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await reveal(pilot)
        await pilot.click("#log-viewer-sources")
        await settle(pilot)
        sources = app.query_one("#log-viewer-sources", TreeSelect)
        assert sources.expanded is True

        await pilot.click("#log-viewer-level")
        await settle(pilot)
        assert sources.expanded is False


async def test_the_trigger_label_shows_visible_over_known_count(
    logger_name: str,
) -> None:
    app = Harness(logger=logger_name)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        _source(logger_name, "a").info("line-a")
        _source(logger_name, "b").info("line-b")
        _source(logger_name, "c").info("line-c")
        await settle(pilot)

        app.query_one(LogViewer).set_source_hidden(f"{logger_name}.a", True)
        await settle(pilot)
        assert _sources_label(app) == "Sources (2/3)"


async def test_the_trigger_label_counts_sources_rather_than_group_rows(
    logger_name: str,
) -> None:
    """The `logger_name` and `lib` rows exist only to hold the two below."""
    app = Harness(logger=logger_name)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        _source(logger_name, "lib.a").info("line-a")
        _source(logger_name, "lib.b").info("line-b")
        await settle(pilot)
        assert _sources_label(app) == "Sources (2/2)"


async def test_the_trigger_arrow_points_up_only_while_the_popup_is_open(
    logger_name: str,
) -> None:
    """Matches Textual's own Select: a down arrow when closed, up while
    open -- not a fixed glyph regardless of state."""
    app = Harness(logger=logger_name)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await reveal(pilot)
        sources = app.query_one("#log-viewer-sources", TreeSelect)
        assert sources.has_class("-expanded") is False

        await pilot.click("#log-viewer-sources")
        await settle(pilot)
        assert sources.has_class("-expanded") is True

        await pilot.press("escape")
        await settle(pilot)
        assert sources.has_class("-expanded") is False


# --------------------------------------------------------------- toggle key


async def test_toggle_key_reveals_and_conceals_panel(logger_name: str) -> None:
    app = Harness(logger=logger_name)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        viewer = app.query_one(LogViewer)
        assert viewer.revealed is False

        await pilot.press("f1")
        await settle(pilot)
        assert viewer.revealed is True

        await pilot.press("f1")
        await settle(pilot)
        assert viewer.revealed is False


async def test_custom_toggle_key_overrides_default(logger_name: str) -> None:
    app = Harness(logger=logger_name, key="f4")
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        viewer = app.query_one(LogViewer)

        await pilot.press("f4")
        await settle(pilot)
        assert viewer.revealed is True
        assert "f1" not in app.screen.active_bindings


async def test_toggle_key_none_installs_no_binding(logger_name: str) -> None:
    app = Harness(logger=logger_name, key=None)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert "f1" not in app.screen.active_bindings


async def test_toggle_key_none_still_installs_the_action(logger_name: str) -> None:
    app = Harness(logger=logger_name, key=None)
    async with app.run_test(size=(80, 24)) as pilot:
        await app.run_action(f"screen.{TOGGLE_ACTION}")
        await settle(pilot)
        assert app.query_one(LogViewer).revealed is True


async def test_removing_the_panel_unbinds_its_key(logger_name: str) -> None:
    app = Harness(logger=logger_name)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await app.query_one(LogViewer).remove()
        await pilot.pause()
        assert "f1" not in app.screen.active_bindings
        assert not hasattr(app.screen, f"action_{TOGGLE_ACTION}")


async def test_a_second_panel_asking_for_a_key_is_refused_at_mount(
    logger_name: str,
) -> None:
    class TwoKeyed(App[None]):
        def compose(self) -> ComposeResult:
            yield LogViewer(logger=f"{logger_name}.a")
            yield LogViewer(logger=f"{logger_name}.b", key="f2")

    app = TwoKeyed()
    with pytest.raises(ValueError, match="already owns"):
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()


async def test_a_second_panel_without_a_key_leaves_the_key_to_the_first(
    logger_name: str,
) -> None:
    class SecondKeyless(App[None]):
        def compose(self) -> ComposeResult:
            yield LogViewer(logger=f"{logger_name}.a", id="first")
            yield LogViewer(logger=f"{logger_name}.b", id="second", key=None)

    app = SecondKeyless()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("f1")
        await settle(pilot)
        assert app.query_one("#first", LogViewer).revealed is True
        assert app.query_one("#second", LogViewer).revealed is False


# ------------------------------------------------------------- focus chain


async def test_concealed_panel_contributes_nothing_to_the_focus_chain(
    logger_name: str,
) -> None:
    app = Harness(logger=logger_name)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        chain = app.screen.focus_chain
        assert app.query_one("#log-viewer-level") not in chain
        assert app.query_one("#log-viewer-sources") not in chain
        assert app.query_one("#log-viewer-log") not in chain


async def test_revealed_panel_puts_its_controls_back_in_the_focus_chain(
    logger_name: str,
) -> None:
    app = Harness(logger=logger_name)
    async with app.run_test(size=(80, 24)) as pilot:
        await reveal(pilot)
        chain = app.screen.focus_chain
        assert app.query_one("#log-viewer-level") in chain
        assert app.query_one("#log-viewer-sources") in chain
        assert app.query_one("#log-viewer-log") in chain


class FieldScreen(Screen[None]):
    """A LogViewer composed ahead of something else that can take the focus,
    so it would come first wherever the first focusable widget is wanted."""

    def __init__(self, logger_name: str) -> None:
        super().__init__()
        self._logger_name = logger_name

    def compose(self) -> ComposeResult:
        yield LogViewer(logger=self._logger_name)
        yield Input(id="field")


class FieldHarness(App[None]):
    """Pushes that screen rather than composing on the default one: auto-focus
    runs again as a pushed screen resumes, when the panel's own controls exist.
    On the default screen it only ever runs before they do."""

    def __init__(self, logger_name: str) -> None:
        super().__init__()
        self._logger_name = logger_name

    def on_mount(self) -> None:
        self.push_screen(FieldScreen(self._logger_name))


async def test_a_concealed_panel_does_not_take_the_initial_focus(
    logger_name: str,
) -> None:
    app = FieldHarness(logger_name)
    async with app.run_test(size=(80, 24)) as pilot:
        await settle(pilot)
        assert app.focused is app.screen.query_one("#field", Input)


async def test_a_concealed_panel_leaves_nothing_focused_if_it_is_all_there_is(
    logger_name: str,
) -> None:
    app = Harness(logger=logger_name)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert app.focused is None


async def test_a_concealed_panels_controls_cannot_be_focused_from_code(
    logger_name: str,
) -> None:
    app = FieldHarness(logger_name)
    async with app.run_test(size=(80, 24)) as pilot:
        await settle(pilot)
        app.screen.query_one("#log-viewer-level", Select).focus()
        await pilot.pause()
        assert app.focused is app.screen.query_one("#field", Input)


@pytest.mark.parametrize("control", ["#log-viewer-level", "#log-viewer-log"])
async def test_concealing_takes_the_focus_away_from_the_panels_controls(
    logger_name: str, control: str
) -> None:
    """Left there, keys would go to a widget the user can no longer see. Nothing
    has the focus afterwards, as Textual leaves it when a focused widget goes out
    of reach, and Tab carries on from the rest of the screen."""
    app = FieldHarness(logger_name)
    async with app.run_test(size=(80, 24)) as pilot:
        await settle(pilot)
        panel = app.screen.query_one(LogViewer)
        panel.reveal()
        await settle(pilot)
        panel.query_one(control).focus()
        await pilot.pause()
        assert app.focused is panel.query_one(control)

        panel.conceal()
        await settle(pilot)
        assert app.focused is None

        await pilot.press("tab")
        await pilot.pause()
        assert app.focused is app.screen.query_one("#field", Input)


@pytest.mark.parametrize("disabled", [False, True])
async def test_concealing_and_revealing_leave_the_panels_disabled_alone(
    logger_name: str, disabled: bool
) -> None:
    """`disabled` is the host's switch. Concealing is a different reason for
    the controls to be out of reach, and must not overwrite it."""
    app = Harness(logger=logger_name, disabled=disabled)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        panel = app.query_one(LogViewer)
        assert panel.disabled is disabled
        panel.reveal()
        await settle(pilot)
        assert panel.disabled is disabled
        panel.conceal()
        await settle(pilot)
        assert panel.disabled is disabled


async def test_a_revealed_panel_the_host_disabled_stays_out_of_the_focus_chain(
    logger_name: str,
) -> None:
    app = Harness(logger=logger_name, disabled=True)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        app.query_one(LogViewer).reveal()
        await settle(pilot)
        assert app.query_one("#log-viewer-level") not in app.screen.focus_chain


async def test_a_concealed_panel_keeps_up_with_the_log(logger_name: str) -> None:
    """Being out of reach only concerns the user. Whatever is logged and
    whatever the host sets while it is concealed is there when it is revealed."""
    app = Harness(logger=logger_name)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        logging.getLogger(logger_name).warning("logged while concealed")
        app.query_one(LogViewer).min_level = logging.WARNING
        await settle(pilot)
        assert "logged while concealed" in _log_text(app)
        assert app.query_one("#log-viewer-level", Select).value == logging.WARNING
        assert _sources_label(app) == "Sources (1/1)"


# --------------------------------------------------------- handler/logger


async def test_owned_handler_is_attached_on_mount_and_detached_on_unmount(
    logger_name: str,
) -> None:
    app = Harness(logger=logger_name)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        logger = logging.getLogger(logger_name)
        assert len(logger.handlers) == 1

        await app.query_one(LogViewer).remove()
        await pilot.pause()
        assert len(logger.handlers) == 0


async def test_changing_the_level_dropdown_resyncs_the_owned_loggers_level(
    logger_name: str,
) -> None:
    app = Harness(logger=logger_name)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        logger = logging.getLogger(logger_name)
        assert logger.level == logging.INFO

        select = app.query_one("#log-viewer-level", Select)
        select.value = logging.DEBUG
        await settle(pilot)
        assert logger.level == logging.DEBUG

        select.value = logging.WARNING
        await settle(pilot)
        assert logger.level == logging.WARNING


async def test_given_handler_is_never_attached_or_touched_by_viewer(
    logger_name: str,
) -> None:
    handler = InMemoryLogHandler()
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)

    class GivenHandlerHarness(App[None]):
        def compose(self) -> ComposeResult:
            yield LogViewer(handler=handler)
            yield Static("body", id="body")

    app = GivenHandlerHarness()
    try:
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            assert logger.level == logging.DEBUG
            assert handler in logger.handlers

            await app.query_one(LogViewer).remove()
            await pilot.pause()
            assert handler in logger.handlers
    finally:
        logger.removeHandler(handler)


def test_handler_and_logger_together_raises_valueerror() -> None:
    with pytest.raises(ValueError):
        LogViewer(handler=InMemoryLogHandler(), logger="some-logger")


async def test_unmounting_detaches_the_sink_subscription(logger_name: str) -> None:
    app = Harness(logger=logger_name)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        logger = logging.getLogger(logger_name)

        await app.query_one(LogViewer).remove()
        await pilot.pause()

        logger.info("after unmount")  # must not raise
        await settle(pilot)


# -------------------------------------------------------------- layering


async def test_panel_paints_above_body_content_when_revealed(
    logger_name: str,
) -> None:
    app = Harness(logger=logger_name)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        # The 400ms offset transition needs to actually finish before the
        # panel's on-screen region -- and therefore hit-testing over it --
        # reflects its revealed position.
        await reveal(pilot)
        widget, _ = app.screen.get_widget_at(1, 1)
        assert isinstance(widget, RichLog)


async def test_two_log_viewers_do_not_double_register_the_layer(
    logger_name: str,
) -> None:
    class TwoViewers(App[None]):
        def compose(self) -> ComposeResult:
            yield LogViewer(logger=logger_name, id="first")
            # A second viewer cannot also own the key -- see the key tests.
            yield LogViewer(logger=logger_name + "-second", id="second", key=None)
            yield Static("body", id="body")

    app = TwoViewers()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert list(app.screen.styles.layers).count(_LAYER) == 1
