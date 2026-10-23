# SPDX-FileCopyrightText: 2026 René de Hesselle <dehesselle@web.de>
#
# SPDX-License-Identifier: 0BSD

"""A `DataTable` that sorts by its own headers and tooltips its own cells.

Textual's table does neither. Clicking a header posts `HeaderSelected` and
stops there; a tooltip is a property of the whole widget, not of a cell or a
header. Both halves turn out to be mostly workarounds for the same handful of
Textual internals::

    class Files(DataTable):
        def __init__(self, entries):
            super().__init__()
            self.entries = entries
            self.add_column("Name", key="name", sortable=True, tooltip="FILE_NAME")
            self.add_column("Size", key="size", sortable=True,
                            sort_key=lambda key: self.entries[key.value].size)

        def get_cell_tooltip(self, row_key, column_key):
            return self.entries[row_key.value].full_path

`sortable=True` makes a header clickable and gives it an indicator; the widget
then reorders the rows itself. `tooltip` is the header's own tooltip -- the
full name behind a header kept short to save width. `sort_key` says how a *row*
is ranked -- it is handed the `RowKey`, not the cell, so a column showing
"7.2K" or "2 days ago" ranks by the number behind it rather than by the text in
front of it. For an ordering no key function can express -- directories before
files, with the direction flipping only *within* each group -- override
`sort_rows` and return the order outright.

Two Textual details are load-bearing here, and are most of why this is a widget
rather than a recipe:

* Every sortable header always carries an indicator (`↕` when it is not the
  active column), so its rendered width never changes. `Column.content_width`
  is measured once when the column is added and is never recomputed from a
  label afterwards, so a header that only grew an arrow when active would be
  clipped. Because the width is fixed, the arrow can be flipped by writing the
  label in place -- no `clear(columns=True)`, no column rebuild, no lost widths.
* `DataTable` leaves `hover_coordinate` untouched when the mouse is over filler
  space carrying no row/column meta, so a tooltip set over a real cell would
  never get the reactive change needed to clear it again.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from rich.text import Text
from textual import events
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import DataTable as TextualDataTable
from textual.widgets.data_table import CellDoesNotExist, ColumnKey, RowKey

if TYPE_CHECKING:
    from collections.abc import Callable

    from rich.text import TextType
    from textual.coordinate import Coordinate
    from textual.visual import VisualType


def _orderable(value: Any) -> Any:
    """A cell value reduced to something `sorted` can compare.

    `rich.text.Text` is not orderable, so Textual's own `DataTable.sort` raises
    on a table whose cells are `Text` -- which is most of them, since a bare
    `str` cell is parsed as console markup and quietly eats anything in
    brackets. Casefolding is the same kind of courtesy: a column of names that
    sorts "Zebra" ahead of "apple" reads as broken, whatever Unicode says.
    """
    if isinstance(value, Text):
        return value.plain.casefold()
    if isinstance(value, str):
        return value.casefold()
    return value


class DataTable(TextualDataTable[Any]):
    """Textual's `DataTable`, plus sortable headers and per-cell and per-header
    tooltips."""

    #: The sort indicators, deliberately not configurable: one look across
    #: every app that uses this. All three are one cell wide, which is what
    #: keeps a header's width identical in every sort state -- see the module
    #: docstring.
    SORT_ASCENDING: ClassVar[str] = "↑"
    SORT_DESCENDING: ClassVar[str] = "↓"
    #: Shown on every other sortable header, so a column is visibly clickable
    #: before anyone has clicked it.
    SORT_INACTIVE: ClassVar[str] = "↕"

    #: Key of the column currently sorted on, or None for the order the rows
    #: were added in. Assignable directly, so a settings dialog driving the
    #: table does not have to fake a click.
    sort_column: reactive[str | None] = reactive(None, init=False)
    #: Direction of `sort_column`. Meaningless while that is None.
    sort_reverse: reactive[bool] = reactive(False, init=False)

    class SortChanged(Message):
        """The rows have just been reordered."""

        def __init__(
            self, data_table: DataTable, column_key: ColumnKey, reverse: bool
        ) -> None:
            self.data_table = data_table
            self.column_key = column_key
            self.reverse = reverse
            super().__init__()

        @property
        def control(self) -> DataTable:
            return self.data_table

    def __init__(self, **kwargs: Any) -> None:
        """
        Args:
            kwargs: Passed through to Textual's `DataTable`.
        """
        super().__init__(**kwargs)
        #: Sortable columns, mapped to their `sort_key` (None to rank by cell).
        self._sort_keys: dict[ColumnKey, Callable[[RowKey], Any] | None] = {}
        #: Header labels without their indicator, so redecorating is not a
        #: matter of stripping a glyph back off again.
        self._sort_labels: dict[ColumnKey, Text] = {}
        #: Header tooltips, by column. Kept here rather than on Textual's
        #: `Column`, which has no field for one.
        self._header_tooltips: dict[ColumnKey, VisualType] = {}
        #: Set when rows arrive, so an active sort is reapplied once on idle
        #: rather than once per `add_row`.
        self._resort_pending = False

    # --------------------------------------------------------------- columns

    def add_column(
        self,
        label: TextType,
        *,
        width: int | None = None,
        key: str | None = None,
        default: Any | None = None,
        sortable: bool = False,
        sort_key: Callable[[RowKey], Any] | None = None,
        tooltip: VisualType | None = None,
    ) -> ColumnKey:
        """
        Args:
            label: Column header.
            width: Width in cells, or None to fit the content.
            key: Identifies the column. Required when `sortable`.
            default: Value inserted into pre-existing rows.
            sortable: Make the header clickable and give it an indicator.
            sort_key: How to rank a row by this column. Called with a `RowKey`,
                not a cell -- look the row up in your own model. Omit it to
                rank by the cell's own value. Requires `sortable`.
            tooltip: Shown while the mouse is over the header. A plain value
                rather than a hook like `get_cell_tooltip`: a header's tooltip
                is fixed and known now, and an argument also serves a column
                with no explicit key.

        Returns:
            The key identifying the column.
        """
        if sort_key is not None and not sortable:
            # Deliberately not promoting to sortable: an explicit
            # `sortable=False` silently overridden by the presence of another
            # argument is a worse surprise than being told to pick one.
            raise ValueError("sort_key requires sortable=True")
        if not sortable:
            column_key = super().add_column(
                label, width=width, key=key, default=default
            )
            self._set_header_tooltip(column_key, tooltip)
            return column_key
        if key is None:
            # `sort_column` and `SortChanged` both identify a column by its
            # key, and an auto-generated one carries no value to identify.
            raise ValueError("a sortable column needs an explicit key")

        base = Text.from_markup(label) if isinstance(label, str) else label
        # Added already decorated, so the indicator is inside the width
        # measured here -- the only measurement this column will ever get.
        column_key = super().add_column(
            self._indicated(base, self.SORT_INACTIVE),
            width=width,
            key=key,
            default=default,
        )
        self._sort_keys[column_key] = sort_key
        self._sort_labels[column_key] = base
        self._set_header_tooltip(column_key, tooltip)
        if key == self.sort_column:
            self._redecorate()
        return column_key

    def remove_column(self, column_key: ColumnKey | str) -> None:
        key = column_key if isinstance(column_key, ColumnKey) else ColumnKey(column_key)
        self._sort_keys.pop(key, None)
        self._sort_labels.pop(key, None)
        self._header_tooltips.pop(key, None)
        super().remove_column(column_key)
        if key.value is not None and key.value == self.sort_column:
            # Leaves the rows where they are: the column that ordered them is
            # gone, and reshuffling on a removal nobody asked about would be
            # more surprising than a stale-looking order.
            self.set_reactive(DataTable.sort_column, None)

    def _set_header_tooltip(
        self, column_key: ColumnKey, tooltip: VisualType | None
    ) -> None:
        if tooltip is not None:
            self._header_tooltips[column_key] = tooltip

    def _indicated(self, label: Text, indicator: str) -> Text:
        return label.copy().append(f" {indicator}")

    def _redecorate(self) -> None:
        """Rewrite every sortable header for the current sort state.

        In place: the indicator is always present and always one cell wide, so
        the label's width is unchanged and the column never needs re-measuring.
        Bumping `_update_count` is what invalidates the render caches, which
        are keyed on it -- `refresh()` alone would redraw from the cache.
        """
        for column_key, base in self._sort_labels.items():
            if column_key.value == self.sort_column:
                indicator = (
                    self.SORT_DESCENDING if self.sort_reverse else self.SORT_ASCENDING
                )
            else:
                indicator = self.SORT_INACTIVE
            self.columns[column_key].label = self._indicated(base, indicator)
        self._update_count += 1
        self.refresh()

    # --------------------------------------------------------------- sorting

    def sort_by(self, column: str | None, *, reverse: bool = False) -> None:
        """Sort on `column`, or restore the order rows were added in with None.

        Args:
            column: Key of the column to sort on.
            reverse: Sort descending.
        """
        self.set_reactive(DataTable.sort_column, column)
        self.set_reactive(DataTable.sort_reverse, reverse)
        self._resort()

    def column_sort_key(self, column_key: ColumnKey) -> Callable[[RowKey], Any]:
        """How a row is ranked by `column_key`.

        The column's own `sort_key` if it was given one, otherwise a callable
        ranking by the cell's value. Provided so a `sort_rows` override does
        not have to work out which of the two applies.
        """
        registered = self._sort_keys.get(column_key)
        if registered is not None:
            return registered
        return lambda row_key: _orderable(self.get_cell(row_key, column_key))

    def sort_rows(
        self, row_keys: list[RowKey], column_key: ColumnKey, reverse: bool
    ) -> list[RowKey]:
        """Return `row_keys` in the order the rows should appear in.

        Override for an ordering no key function can express -- one that
        partitions the rows, say, or that does not reverse wholesale. The
        default ranks by `column_sort_key`.

        Args:
            row_keys: The rows, in their current order.
            column_key: The column being sorted on.
            reverse: Whether the user asked for descending order.

        Returns:
            The same keys, reordered.
        """
        return sorted(row_keys, key=self.column_sort_key(column_key), reverse=reverse)

    def on_data_table_header_selected(
        self, event: TextualDataTable.HeaderSelected
    ) -> None:
        # Not stopped: `HeaderSelected` bubbling out of a DataTable is stock
        # behaviour, and an app may be listening for its own reasons.
        if event.column_key not in self._sort_keys:
            return  # not a sortable column
        column = event.column_key.value
        if column == self.sort_column:
            self.sort_by(column, reverse=not self.sort_reverse)
        else:
            self.sort_by(column, reverse=False)

    def watch_sort_column(self) -> None:
        self._resort()

    def watch_sort_reverse(self) -> None:
        self._resort()

    def _resort(self) -> None:
        self._redecorate()
        self._resort_pending = False
        if self.sort_column is None:
            return
        column_key = ColumnKey(self.sort_column)
        if column_key not in self._sort_keys:
            return  # sorted on a column that has not been added yet
        order = self.sort_rows(
            [row.key for row in self.ordered_rows], column_key, self.sort_reverse
        )
        self._apply_row_order(order)
        self.post_message(self.SortChanged(self, column_key, self.sort_reverse))
        # The rows moved under a stationary mouse, so `hover_coordinate` has
        # not changed and its watcher will not fire -- without this the
        # tooltip would go on describing the row that used to be here.
        self._sync_tooltip()

    def _apply_row_order(self, row_keys: list[RowKey]) -> None:
        """Put the rows into `row_keys` order.

        Textual's own `sort` cannot be used for this: it discards the `RowKey`
        before calling the key function (`_, row_data = row`), so it can only
        ever rank by cell values. This is what `sort` itself does once it has
        an order -- remapping locations leaves the row keys untouched, so
        anything holding one (a tooltip, a cursor restore) still resolves.
        """
        two_way_dict = type(self._row_locations)
        self._row_locations = two_way_dict(
            {row_key: index for index, row_key in enumerate(row_keys)}
        )
        self._update_count += 1
        self.refresh()

    async def _on_idle(self, event: events.Idle) -> None:
        await super()._on_idle(event)
        # Rows arrive one `add_row` at a time and re-sorting per row would be
        # quadratic. Doing it here also covers an app that repopulates without
        # re-announcing the sort it already asked for.
        if self._resort_pending:
            self._resort()

    def add_row(self, *cells: Any, **kwargs: Any) -> RowKey:
        self._resort_pending = self.sort_column is not None
        return super().add_row(*cells, **kwargs)

    def remove_row(self, row_key: RowKey | str) -> None:
        super().remove_row(row_key)
        self._sync_tooltip()

    def clear(self, columns: bool = False) -> DataTable:
        if columns:
            self._sort_keys.clear()
            self._sort_labels.clear()
            self._header_tooltips.clear()
            self.set_reactive(DataTable.sort_column, None)
        super().clear(columns=columns)
        # Whatever the tooltip was describing is not there any more.
        self.tooltip = None
        return self

    # -------------------------------------------------------------- tooltips

    def get_cell_tooltip(
        self, row_key: RowKey, column_key: ColumnKey
    ) -> VisualType | None:
        """The tooltip for one cell, or None for no tooltip.

        Override this. It is handed resolved keys rather than a `Coordinate`
        so that the usual first two lines -- resolve the coordinate, guard
        against it having gone stale mid-repaint -- are not every caller's
        problem. Showing the full value of a cell that is displayed
        abbreviated is what this is for.

        Args:
            row_key: The hovered row.
            column_key: The hovered column.
        """
        return None

    def _sync_tooltip(self) -> None:
        coordinate = self.hover_coordinate
        # A negative column is the row labels, which have no tooltip; a
        # negative row is the header. Neither is a cell, and
        # `coordinate_to_cell_key` promises nothing sensible for them.
        if coordinate.column < 0:
            self.tooltip = None
            return
        if coordinate.row < 0:
            try:
                column_key = self.ordered_columns[coordinate.column].key
            except IndexError:
                self.tooltip = None
                return
            self.tooltip = self._header_tooltips.get(column_key)
            return
        try:
            row_key, column_key = self.coordinate_to_cell_key(coordinate)
        except CellDoesNotExist:
            self.tooltip = None
            return
        self.tooltip = self.get_cell_tooltip(row_key, column_key)

    def watch_hover_coordinate(self, old: Coordinate, value: Coordinate) -> None:
        super().watch_hover_coordinate(old, value)
        self._sync_tooltip()

    def _on_mouse_move(self, event: events.MouseMove) -> None:
        # The underscored form rather than `on_mouse_move`: Textual dispatches
        # one or the other per class, never both, and DataTable's own hover
        # tracking needs this one.
        super()._on_mouse_move(event)
        # DataTable returns early without touching `hover_coordinate` when the
        # mouse is over filler space carrying no meta, so the watcher above
        # never fires and a tooltip set over a real cell would stick there.
        meta = event.style.meta
        if not meta or meta.get("out_of_bounds", False):
            self.tooltip = None
