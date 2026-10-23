# SPDX-FileCopyrightText: 2026 René de Hesselle <dehesselle@web.de>
#
# SPDX-License-Identifier: 0BSD

"""The table: sort state and its indicators, who orders the rows, and the
per-cell and per-header tooltips.

The hover tests go through a real mouse position rather than assigning to
`hover_coordinate`, because two of the things worth pinning down here -- a
tooltip surviving a reorder, and a tooltip being cleared over filler space --
are precisely the cases where the coordinate does *not* change.
"""

from __future__ import annotations

import pytest
from rich.cells import cell_len
from rich.text import Text
from textual.app import App, ComposeResult
from textual.coordinate import Coordinate
from textual.widgets.data_table import ColumnKey, RowKey

from tcoda.widgets import DataTable

#: Rows used by most of the tests: deliberately neither in key order nor in
#: name order, so a passing sort cannot be the order they went in.
ROWS = [
    ("c", "charlie", "100 B", 100),
    ("a", "Alpha", "30 B", 30),
    ("b", "bravo", "2 B", 2),
]


class Harness(App[None]):
    CSS = """
    DataTable {
        width: 60;
        height: 10;
    }
    """

    def __init__(self, table: DataTable | None = None) -> None:
        super().__init__()
        self._table = table if table is not None else DataTable()
        self.sort_changes: list[tuple[str | None, bool]] = []

    def compose(self) -> ComposeResult:
        yield self._table

    def on_data_table_sort_changed(self, event: DataTable.SortChanged) -> None:
        self.sort_changes.append((event.column_key.value, event.reverse))


def populate(table: DataTable) -> None:
    """Two sortable columns -- one ranked by cell, one by the model -- and one
    that is not sortable at all."""
    sizes = {key: size for key, _, _, size in ROWS}
    table.add_column("Name", key="name", sortable=True)
    table.add_column(
        "Size", key="size", sortable=True, sort_key=lambda row_key: sizes[row_key.value]
    )
    table.add_column("Note", key="note")
    for key, name, size, _ in ROWS:
        table.add_row(Text(name), Text(size), Text("note"), key=key)


def order(table: DataTable) -> list[str | None]:
    return [row.key.value for row in table.ordered_rows]


def labels(table: DataTable) -> list[str]:
    return [column.label.plain for column in table.ordered_columns]


async def hover_cell(pilot, table: DataTable, row: int, column: int) -> None:
    # `_get_cell_region` is relative to the table's content area, which is
    # what `pilot.hover`'s offset is measured against too.
    region = table._get_cell_region(Coordinate(row, column))
    await pilot.hover(table, offset=(region.x + 1, region.y))
    await pilot.pause()


async def hover_header(pilot, table: DataTable, column: int) -> None:
    # `_get_cell_region` resolves body rows only; the header is the first
    # line, and a column starts where the ones before it end.
    x = sum(c.get_render_width(table) for c in table.ordered_columns[:column])
    await pilot.hover(table, offset=(x + 1, 0))
    await pilot.pause()


# ------------------------------------------------------------------ indicators


async def test_every_sortable_header_is_indicated_before_anything_is_clicked() -> None:
    """A dot rather than nothing: a column being clickable should not have to
    be discovered by trial and error."""
    app = Harness()
    async with app.run_test() as pilot:
        table = app.query_one(DataTable)
        populate(table)
        await pilot.pause()
        assert labels(table) == [
            f"Name {DataTable.SORT_INACTIVE}",
            f"Size {DataTable.SORT_INACTIVE}",
            "Note",
        ]


async def test_the_active_column_shows_a_direction_and_the_others_revert() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        table = app.query_one(DataTable)
        populate(table)
        table.sort_by("name")
        await pilot.pause()
        assert labels(table)[0] == f"Name {DataTable.SORT_ASCENDING}"
        table.sort_by("name", reverse=True)
        await pilot.pause()
        assert labels(table)[0] == f"Name {DataTable.SORT_DESCENDING}"
        table.sort_by("size")
        await pilot.pause()
        assert labels(table)[0] == f"Name {DataTable.SORT_INACTIVE}"
        assert labels(table)[1] == f"Size {DataTable.SORT_ASCENDING}"


def test_all_three_indicators_are_one_cell_wide() -> None:
    """The whole in-place relabelling scheme rests on this: a header that
    changed width when sorted would need a column re-measure, which Textual
    only ever does at `add_column` time."""
    for indicator in (
        DataTable.SORT_ASCENDING,
        DataTable.SORT_DESCENDING,
        DataTable.SORT_INACTIVE,
    ):
        assert cell_len(indicator) == 1


async def test_sorting_does_not_resize_or_rebuild_the_columns() -> None:
    """The reserved indicator slot is what lets the arrow be written in place.
    Identity of the ColumnKeys is part of the assertion: a rebuild would mint
    new ones and quietly break anything holding the old."""
    app = Harness()
    async with app.run_test() as pilot:
        table = app.query_one(DataTable)
        populate(table)
        await pilot.pause()
        before_widths = [c.content_width for c in table.ordered_columns]
        before_keys = [id(c.key) for c in table.ordered_columns]
        before_cells = [cell_len(label) for label in labels(table)]

        table.sort_by("name")
        await pilot.pause()
        table.sort_by("name", reverse=True)
        await pilot.pause()

        assert [c.content_width for c in table.ordered_columns] == before_widths
        assert [id(c.key) for c in table.ordered_columns] == before_keys
        assert [cell_len(label) for label in labels(table)] == before_cells


# --------------------------------------------------------------------- sorting


async def test_a_column_with_no_sort_key_ranks_by_its_cell() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        table = app.query_one(DataTable)
        populate(table)
        table.sort_by("name")
        await pilot.pause()
        assert order(table) == ["a", "b", "c"]


async def test_cell_ranking_is_case_insensitive_and_survives_text_cells() -> None:
    """Textual's own `sort` raises on `Text`, which is what a table holding
    app-supplied strings has to use. "Alpha" sorting after "charlie" would be
    the other half of the same surprise."""
    app = Harness()
    async with app.run_test() as pilot:
        table = app.query_one(DataTable)
        populate(table)
        table.sort_by("name")
        await pilot.pause()
        assert [
            table.get_cell(RowKey(k), ColumnKey("name")).plain for k in order(table)
        ] == [
            "Alpha",
            "bravo",
            "charlie",
        ]


async def test_a_sort_key_ranks_by_the_model_not_the_rendered_cell() -> None:
    """The Size column reads "100 B", "30 B", "2 B" -- ascending by text puts
    "100 B" first, which is the trap `sort_key` exists to avoid."""
    app = Harness()
    async with app.run_test() as pilot:
        table = app.query_one(DataTable)
        populate(table)
        table.sort_by("size")
        await pilot.pause()
        assert order(table) == ["b", "a", "c"]


async def test_the_sort_key_is_handed_row_keys() -> None:
    seen: list[object] = []
    table = DataTable()
    app = Harness(table)
    async with app.run_test() as pilot:
        table.add_column(
            "Name",
            key="name",
            sortable=True,
            sort_key=lambda row_key: seen.append(row_key) or 0,
        )
        table.add_row(Text("only"), key="only")
        table.sort_by("name")
        await pilot.pause()
        assert seen and all(isinstance(item, RowKey) for item in seen)


async def test_reverse_flips_the_order() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        table = app.query_one(DataTable)
        populate(table)
        table.sort_by("name", reverse=True)
        await pilot.pause()
        assert order(table) == ["c", "b", "a"]


async def test_sorting_keeps_the_row_keys_resolvable() -> None:
    """Reordering remaps locations rather than rebuilding rows, so anything
    holding a key -- a tooltip, a cursor restore -- still resolves."""
    app = Harness()
    async with app.run_test() as pilot:
        table = app.query_one(DataTable)
        populate(table)
        table.sort_by("size", reverse=True)
        await pilot.pause()
        for key, _, _, _ in ROWS:
            assert table.get_row_index(key) >= 0


async def test_sort_changed_is_posted_after_the_rows_have_moved() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        table = app.query_one(DataTable)
        populate(table)
        await pilot.pause()
        app.sort_changes.clear()
        table.sort_by("size", reverse=True)
        await pilot.pause()
        assert app.sort_changes == [("size", True)]


async def test_rows_added_after_a_sort_are_folded_into_it() -> None:
    """An app that repopulates should not have to re-announce the sort the
    user already asked for."""
    app = Harness()
    async with app.run_test() as pilot:
        table = app.query_one(DataTable)
        populate(table)
        table.sort_by("name")
        await pilot.pause()
        table.add_row(Text("bravissimo"), Text("1 B"), Text("note"), key="z")
        await pilot.pause()
        assert order(table) == ["a", "z", "b", "c"]


# ------------------------------------------------------------ header clicking


async def test_clicking_a_header_sorts_then_toggles_direction() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        table = app.query_one(DataTable)
        populate(table)
        await pilot.pause()
        table.post_message(
            DataTable.HeaderSelected(table, ColumnKey("name"), 0, Text("Name"))
        )
        await pilot.pause()
        assert (table.sort_column, table.sort_reverse) == ("name", False)
        table.post_message(
            DataTable.HeaderSelected(table, ColumnKey("name"), 0, Text("Name"))
        )
        await pilot.pause()
        assert (table.sort_column, table.sort_reverse) == ("name", True)


async def test_switching_column_starts_ascending_again() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        table = app.query_one(DataTable)
        populate(table)
        table.sort_by("name", reverse=True)
        await pilot.pause()
        table.post_message(
            DataTable.HeaderSelected(table, ColumnKey("size"), 1, Text("Size"))
        )
        await pilot.pause()
        assert (table.sort_column, table.sort_reverse) == ("size", False)


async def test_clicking_an_unsortable_header_does_nothing() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        table = app.query_one(DataTable)
        populate(table)
        table.sort_by("name")
        await pilot.pause()
        app.sort_changes.clear()
        table.post_message(
            DataTable.HeaderSelected(table, ColumnKey("note"), 2, Text("Note"))
        )
        await pilot.pause()
        assert (table.sort_column, table.sort_reverse) == ("name", False)
        assert app.sort_changes == []


# ------------------------------------------------------------------ sort_rows


class Grouped(DataTable):
    """Rows whose key starts with "d" sort first, whatever the direction --
    the shape of a file panel listing directories before files, which no
    key-plus-reverse can express."""

    def sort_rows(
        self, row_keys: list[RowKey], column_key: ColumnKey, reverse: bool
    ) -> list[RowKey]:
        rank = self.column_sort_key(column_key)
        first = [k for k in row_keys if str(k.value).startswith("d")]
        rest = [k for k in row_keys if not str(k.value).startswith("d")]
        return sorted(first, key=rank, reverse=reverse) + sorted(
            rest, key=rank, reverse=reverse
        )


async def test_a_sort_rows_override_decides_the_order_outright() -> None:
    table = Grouped()
    app = Harness(table)
    async with app.run_test() as pilot:
        table.add_column("Name", key="name", sortable=True)
        for key in ("f2", "d2", "f1", "d1"):
            table.add_row(Text(key), key=key)
        table.sort_by("name")
        await pilot.pause()
        assert order(table) == ["d1", "d2", "f1", "f2"]


async def test_reverse_reaches_a_sort_rows_override_unmodified() -> None:
    """The group stays on top; only the order within each group flips."""
    table = Grouped()
    app = Harness(table)
    async with app.run_test() as pilot:
        table.add_column("Name", key="name", sortable=True)
        for key in ("f2", "d2", "f1", "d1"):
            table.add_row(Text(key), key=key)
        table.sort_by("name", reverse=True)
        await pilot.pause()
        assert order(table) == ["d2", "d1", "f2", "f1"]


# -------------------------------------------------------------------- columns


async def test_a_sort_key_without_sortable_is_refused() -> None:
    """An explicit `sortable=False` quietly overridden by the presence of
    another argument would be the worse of the two surprises."""
    app = Harness()
    async with app.run_test() as pilot:
        table = app.query_one(DataTable)
        await pilot.pause()
        with pytest.raises(ValueError, match="sortable=True"):
            table.add_column("Nope", key="nope", sort_key=lambda row_key: 0)


async def test_a_sortable_column_without_a_key_is_refused() -> None:
    """`sort_column` and `SortChanged` both name a column by its key, and an
    auto-generated one carries no value to name it with."""
    app = Harness()
    async with app.run_test() as pilot:
        table = app.query_one(DataTable)
        await pilot.pause()
        with pytest.raises(ValueError, match="explicit key"):
            table.add_column("Nope", sortable=True)


# ------------------------------------------------------------------- tooltips


class Tipped(DataTable):
    def get_cell_tooltip(self, row_key: RowKey, column_key: ColumnKey) -> str | None:
        if column_key.value != "name":
            return None
        return f"full {row_key.value}"


async def test_hovering_a_cell_tooltips_it() -> None:
    table = Tipped()
    app = Harness(table)
    async with app.run_test() as pilot:
        populate(table)
        await pilot.pause()
        await hover_cell(pilot, table, 0, 0)
        assert table.tooltip == f"full {order(table)[0]}"


async def test_a_column_with_no_tooltip_clears_the_previous_one() -> None:
    table = Tipped()
    app = Harness(table)
    async with app.run_test() as pilot:
        populate(table)
        await pilot.pause()
        await hover_cell(pilot, table, 0, 0)
        assert table.tooltip is not None
        await hover_cell(pilot, table, 0, 2)
        assert table.tooltip is None


async def test_moving_onto_filler_space_clears_the_tooltip() -> None:
    """DataTable leaves `hover_coordinate` alone over space carrying no
    row/column meta, so the watcher never fires there and a tooltip set over a
    real cell would stay put."""
    table = Tipped()
    app = Harness(table)
    async with app.run_test() as pilot:
        populate(table)
        await pilot.pause()
        await hover_cell(pilot, table, 0, 0)
        assert table.tooltip is not None
        await pilot.hover(table, offset=(55, 1))
        await pilot.pause()
        assert table.tooltip is None


async def test_a_tooltip_follows_the_rows_when_they_are_reordered() -> None:
    """The mouse has not moved, so `hover_coordinate` is unchanged and its
    watcher will not fire -- but a different row is under the cursor now."""
    table = Tipped()
    app = Harness(table)
    async with app.run_test() as pilot:
        populate(table)
        table.sort_by("name")
        await pilot.pause()
        await hover_cell(pilot, table, 0, 0)
        assert table.tooltip == "full a"
        table.sort_by("name", reverse=True)
        await pilot.pause()
        assert table.tooltip == "full c"


async def test_a_sortable_column_still_tooltips_once_it_carries_a_glyph() -> None:
    """Identifying a column by its header text rather than its key breaks the
    moment that header grows an indicator; this is the regression."""
    table = Tipped()
    app = Harness(table)
    async with app.run_test() as pilot:
        populate(table)
        table.sort_by("name")
        await pilot.pause()
        assert labels(table)[0] != "Name"
        await hover_cell(pilot, table, 0, 0)
        assert table.tooltip == "full a"


async def test_clearing_the_table_drops_the_tooltip() -> None:
    table = Tipped()
    app = Harness(table)
    async with app.run_test() as pilot:
        populate(table)
        await pilot.pause()
        await hover_cell(pilot, table, 0, 0)
        assert table.tooltip is not None
        table.clear()
        await pilot.pause()
        assert table.tooltip is None


async def test_the_default_tooltip_is_none() -> None:
    """A plain tcoda DataTable behaves exactly as Textual's does."""
    app = Harness()
    async with app.run_test() as pilot:
        table = app.query_one(DataTable)
        populate(table)
        await pilot.pause()
        await hover_cell(pilot, table, 0, 0)
        assert table.tooltip is None


def populate_with_header_tooltips(table: DataTable) -> None:
    """`populate`'s columns, with tooltips on the two sortable headers only."""
    table.add_column("Name", key="name", sortable=True, tooltip="FULL_NAME")
    table.add_column("Size", key="size", sortable=True, tooltip="BYTES")
    table.add_column("Note", key="note")
    for key, name, size, _ in ROWS:
        table.add_row(Text(name), Text(size), Text("note"), key=key)


async def test_hovering_a_header_shows_its_tooltip() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        table = app.query_one(DataTable)
        populate_with_header_tooltips(table)
        await pilot.pause()
        await hover_header(pilot, table, 1)
        assert table.tooltip == "BYTES"


async def test_an_unsortable_header_can_have_a_tooltip_without_a_key() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        table = app.query_one(DataTable)
        table.add_column("Plain", tooltip="PLAIN_FIELD")
        table.add_row(Text("x"))
        await pilot.pause()
        await hover_header(pilot, table, 0)
        assert table.tooltip == "PLAIN_FIELD"


async def test_a_header_with_no_tooltip_clears_the_previous_one() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        table = app.query_one(DataTable)
        populate_with_header_tooltips(table)
        await pilot.pause()
        await hover_header(pilot, table, 0)
        assert table.tooltip == "FULL_NAME"
        await hover_header(pilot, table, 2)
        assert table.tooltip is None


async def test_a_header_keeps_its_tooltip_once_sorting_rewrites_its_glyph() -> None:
    """Sorting rewrites the label in place; the tooltip is held by key, so
    it must not care."""
    app = Harness()
    async with app.run_test() as pilot:
        table = app.query_one(DataTable)
        populate_with_header_tooltips(table)
        table.sort_by("name", reverse=True)
        await pilot.pause()
        assert labels(table)[0] == f"Name {DataTable.SORT_DESCENDING}"
        await hover_header(pilot, table, 0)
        assert table.tooltip == "FULL_NAME"


async def test_the_header_filler_right_of_the_last_column_clears_the_tooltip() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        table = app.query_one(DataTable)
        populate_with_header_tooltips(table)
        await pilot.pause()
        await hover_header(pilot, table, 0)
        assert table.tooltip is not None
        await pilot.hover(table, offset=(55, 0))
        await pilot.pause()
        assert table.tooltip is None


async def test_moving_from_a_header_onto_a_cell_shows_the_cells_tooltip() -> None:
    table = Tipped()
    app = Harness(table)
    async with app.run_test() as pilot:
        populate_with_header_tooltips(table)
        await pilot.pause()
        await hover_header(pilot, table, 0)
        assert table.tooltip == "FULL_NAME"
        await hover_cell(pilot, table, 0, 0)
        assert table.tooltip == f"full {order(table)[0]}"


async def test_removing_a_column_drops_its_header_tooltip() -> None:
    """Re-added under the same key without one, it must not inherit the old
    column's tooltip."""
    app = Harness()
    async with app.run_test() as pilot:
        table = app.query_one(DataTable)
        populate_with_header_tooltips(table)
        table.remove_column("size")
        table.add_column("Size", key="size")
        await pilot.pause()
        await hover_header(pilot, table, table.get_column_index("size"))
        assert table.tooltip is None


async def test_clearing_the_columns_drops_every_header_tooltip() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        table = app.query_one(DataTable)
        populate_with_header_tooltips(table)
        table.clear(columns=True)
        populate(table)
        await pilot.pause()
        for column in range(3):
            await hover_header(pilot, table, column)
            assert table.tooltip is None
