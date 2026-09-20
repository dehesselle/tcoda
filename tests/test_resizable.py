"""Dragging a border: which presses start a drag, what the size becomes, and
what the widget underneath is allowed to do while one is in progress.

The last of those is the reason this is a mixin and not three copied handlers.
Textual dispatches a mouse handler once per class in the MRO, so the widget's
own handling runs alongside this -- which is fine until a drag is in progress,
and is what `prevent_default` is for.
"""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widgets import Tree

from tcw.widgets import DataTable, Resizable


class Sidebar(Resizable, Tree[None]):
    RESIZE_MIN = 10
    RESIZE_MIN_SIBLING = 20


class BottomPane(Resizable, DataTable):
    RESIZE_EDGE = "bottom"
    RESIZE_MIN = 4
    RESIZE_MIN_SIBLING = 5

    #: Every cell the widget's own hover tracking has been told about, so a
    #: test can show that a drag does not feed it.
    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.hovered: list[tuple[int, int]] = []

    def watch_hover_coordinate(self, old: object, value: object) -> None:
        super().watch_hover_coordinate(old, value)  # type: ignore[arg-type]
        self.hovered.append((value.row, value.column))  # type: ignore[attr-defined]


class Harness(App[None]):
    CSS = """
    Screen { layout: horizontal; }
    Sidebar { width: 30; }
    /* Shorter than the screen on purpose: it is what makes the parent and
       the screen disagree about how much room there is. */
    #right { width: 1fr; height: 24; }
    BottomPane { height: 10; }
    #filler { height: 1fr; }
    """

    def compose(self) -> ComposeResult:
        yield Sidebar("root", id="sidebar")
        with Vertical(id="right"):
            table = BottomPane(id="pane")
            # More than one cell on purpose: the hover coordinate starts at
            # (0, 0), so a one-cell table could never record a change and the
            # hover assertions below would hold whatever the mixin did.
            table.add_column("Name", key="name")
            table.add_column("Size", key="size")
            for name in ("one", "two", "three"):
                table.add_row(name, "1", key=name)
            yield table
            yield Tree("filler", id="filler")


# ------------------------------------------------------------------- starting


async def test_pressing_the_right_border_starts_a_drag() -> None:
    app = Harness()
    async with app.run_test(size=(100, 30)) as pilot:
        sidebar = app.query_one(Sidebar)
        await pilot.mouse_down(sidebar, offset=(sidebar.outer_size.width - 1, 2))
        await pilot.pause()
        assert sidebar._resize_dragging is True


async def test_pressing_anywhere_else_does_not() -> None:
    """The border is the whole grab area, so the rest of the widget has to go
    on working as it always did."""
    app = Harness()
    async with app.run_test(size=(100, 30)) as pilot:
        sidebar = app.query_one(Sidebar)
        await pilot.mouse_down(sidebar, offset=(2, 2))
        await pilot.pause()
        assert sidebar._resize_dragging is False


async def test_moving_without_a_drag_leaves_the_size_alone() -> None:
    app = Harness()
    async with app.run_test(size=(100, 30)) as pilot:
        sidebar = app.query_one(Sidebar)
        before = sidebar.outer_size.width
        await pilot.hover(sidebar, offset=(5, 2))
        await pilot.pause()
        assert sidebar.outer_size.width == before


# -------------------------------------------------------------------- resizing


async def test_dragging_the_right_border_sets_the_width() -> None:
    app = Harness()
    async with app.run_test(size=(100, 30)) as pilot:
        sidebar = app.query_one(Sidebar)
        await pilot.mouse_down(sidebar, offset=(sidebar.outer_size.width - 1, 2))
        await pilot.pause()
        await pilot.hover(sidebar, offset=(39, 2))
        await pilot.pause()
        assert sidebar.outer_size.width == 40


async def test_a_drag_stops_at_this_widgets_own_minimum() -> None:
    app = Harness()
    async with app.run_test(size=(100, 30)) as pilot:
        sidebar = app.query_one(Sidebar)
        await pilot.mouse_down(sidebar, offset=(sidebar.outer_size.width - 1, 2))
        await pilot.pause()
        await pilot.hover(sidebar, offset=(0, 2))
        await pilot.pause()
        assert sidebar.outer_size.width == Sidebar.RESIZE_MIN


async def test_a_drag_leaves_the_sibling_its_minimum() -> None:
    """Neither side can be dragged into uselessness."""
    app = Harness()
    async with app.run_test(size=(100, 30)) as pilot:
        sidebar = app.query_one(Sidebar)
        await pilot.mouse_down(sidebar, offset=(sidebar.outer_size.width - 1, 2))
        await pilot.pause()
        await pilot.hover(sidebar, offset=(99, 2))
        await pilot.pause()
        assert sidebar.outer_size.width == 100 - Sidebar.RESIZE_MIN_SIBLING


async def test_releasing_ends_the_drag() -> None:
    app = Harness()
    async with app.run_test(size=(100, 30)) as pilot:
        sidebar = app.query_one(Sidebar)
        await pilot.mouse_down(sidebar, offset=(sidebar.outer_size.width - 1, 2))
        await pilot.pause()
        await pilot.mouse_up(sidebar, offset=(40, 2))
        await pilot.pause()
        assert sidebar._resize_dragging is False
        settled = sidebar.outer_size.width
        await pilot.hover(sidebar, offset=(5, 2))
        await pilot.pause()
        assert sidebar.outer_size.width == settled


# ---------------------------------------------------------------- bottom edge


async def test_dragging_the_bottom_border_sets_the_height() -> None:
    app = Harness()
    async with app.run_test(size=(100, 30)) as pilot:
        pane = app.query_one(BottomPane)
        await pilot.mouse_down(pane, offset=(3, pane.outer_size.height - 1))
        await pilot.pause()
        await pilot.hover(pane, offset=(3, 14))
        await pilot.pause()
        assert pane.outer_size.height == 15


async def test_the_vertical_limit_is_measured_against_the_parent() -> None:
    """Not the screen: a header, a footer or anything else outside this
    widget's own container has already taken those rows."""
    app = Harness()
    async with app.run_test(size=(100, 30)) as pilot:
        pane = app.query_one(BottomPane)
        parent_height = pane.parent.size.height
        assert parent_height < 30, "the container should be shorter than the screen"
        # Clamping against the screen instead would allow 30 - 5 = 25.
        await pilot.mouse_down(pane, offset=(3, pane.outer_size.height - 1))
        await pilot.pause()
        await pilot.hover(pane, offset=(3, 29))
        await pilot.pause()
        assert pane.outer_size.height == parent_height - BottomPane.RESIZE_MIN_SIBLING


# ------------------------------------------------- living with the host widget


async def test_the_host_widget_still_tracks_hover_when_nothing_is_dragging() -> None:
    """The mixin is additive: Textual runs a handler per class in the MRO, so
    the table's own hover tracking is untouched."""
    app = Harness()
    async with app.run_test(size=(100, 30)) as pilot:
        pane = app.query_one(BottomPane)
        pane.hovered.clear()
        await pilot.hover(pane, offset=(2, 2))
        await pilot.pause()
        assert pane.hovered


async def test_a_drag_does_not_feed_the_host_widgets_hover_tracking() -> None:
    """`prevent_default` stops the MRO walk, so the table does not chase the
    pointer around while it is dragging a border."""
    app = Harness()
    async with app.run_test(size=(100, 30)) as pilot:
        pane = app.query_one(BottomPane)
        await pilot.mouse_down(pane, offset=(3, pane.outer_size.height - 1))
        await pilot.pause()
        pane.hovered.clear()
        # The same cell the test above proves is tracked when no drag is in
        # progress, so this is a difference the mixin makes and not a spot
        # where the table had nothing to say anyway.
        await pilot.hover(pane, offset=(2, 2))
        await pilot.pause()
        assert pane.hovered == []


async def test_a_resizable_table_still_sorts_and_tooltips() -> None:
    """The combination that had no working example before this: nothing about
    being resizable disturbs what the table itself does."""

    class Both(Resizable, DataTable):
        RESIZE_EDGE = "bottom"

        def get_cell_tooltip(self, row_key, column_key) -> str | None:
            return f"full {row_key.value}"

    class BothHarness(App[None]):
        def compose(self) -> ComposeResult:
            table = Both(id="both")
            table.add_column("Name", key="name", sortable=True)
            for name in ("charlie", "alpha", "bravo"):
                table.add_row(name, key=name)
            yield table

    app = BothHarness()
    async with app.run_test(size=(60, 20)) as pilot:
        table = app.query_one(Both)
        table.sort_by("name")
        await pilot.pause()
        assert [row.key.value for row in table.ordered_rows] == [
            "alpha",
            "bravo",
            "charlie",
        ]
        name_column = next(iter(table.columns))
        assert (
            table.get_cell_tooltip(table.ordered_rows[0].key, name_column)
            == "full alpha"
        )
