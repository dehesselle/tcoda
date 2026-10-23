# Data table

Textual's `DataTable` does not sort and has no per-cell or per-header
tooltips: clicking a header posts `HeaderSelected` and stops there, and
`tooltip` is a property of the whole widget. Both halves turn out to be
mostly workarounds for the same few Textual internals.

```python
from tcoda.widgets import DataTable


class Files(DataTable):
    def __init__(self, entries):
        super().__init__()
        self.entries = entries
        self.add_column("Name", key="name", sortable=True, tooltip="FILE_NAME")
        self.add_column(
            "Size",
            key="size",
            sortable=True,
            sort_key=lambda key: self.entries[key.value].size,
        )
        self.add_column("Note", key="note")

    def get_cell_tooltip(self, row_key, column_key):
        if column_key.value == "name":
            return self.entries[row_key.value].full_path
        return None
```

## Sorting

- **`sortable=True` makes a header clickable, indicates it, and sorts it.**
  Clicking the active column toggles direction; clicking another switches to it
  ascending. An unsortable header is a silent no-op. A table with no sortable
  column behaves exactly like Textual's.
- **`sort_key` ranks a *row*, not a cell** — it is handed the `RowKey`, so you
  look the row up in your own model. This is a deliberate divergence from
  `sorted(key=)`: a column showing `7.2K` or `2 days ago` has to rank by the
  number behind it, and re-parsing the rendered text is exactly the bug worth
  designing out. Omit it to rank by the cell's own value.
- **`sort_key` requires `sortable=True`, and a sortable column requires an
  explicit `key`.** Both raise rather than guessing. An implied `sortable`
  would mean a passed `sortable=False` was silently overridden, and
  `sort_column` names a column by its key, which an auto-generated one has
  nothing to name.
- **Override `sort_rows` for an ordering no key function can express** —
  directories before files, with the direction flipping only *within* each
  group. It is handed the row keys and the direction and returns the order
  outright; `column_sort_key()` gives back the ranking the column would have
  used. There is one sorting mechanism, and it goes all the way down.
- **Every sortable header always carries an indicator** — `↕` when it is not
  the active column — so its rendered width never changes. This is
  load-bearing rather than decorative: `Column.content_width` is measured once
  at `add_column` and never recomputed from a label, so a header that only grew
  an arrow when active would be clipped. Because the width is fixed, sorting
  rewrites the label in place: no `clear(columns=True)`, no column rebuild, no
  lost widths, and the `ColumnKey`s survive.
- **The glyphs are not configurable.** One look across every app using this.
- **`sort_column` and `sort_reverse` are ordinary reactives**, so a settings
  dialog can drive the table without faking a click. `sort_by(column,
  reverse=...)` sets both at once and sorts once.
- **Rows added after a sort are folded into it** on the next idle, so an app
  that repopulates does not have to re-announce the sort the user already
  asked for.
- **`SortChanged` is posted after every reorder**, for a status line or for
  persisting the choice — reacting to it is not how you sort.
- **Cell ranking handles `rich.text.Text` and casefolds.** `Text` is not
  orderable, so stock `DataTable.sort()` raises on it — which is most tables,
  since a bare `str` cell is parsed as console markup and eats anything in
  brackets.

## Tooltips

- **`add_column(tooltip=...)` gives a header its own tooltip**: the full name
  behind a header kept short to save width. It is a plain value rather than a
  hook, because a header's tooltip is fixed and known when the column is added,
  and an argument also serves a column with no explicit key. It is held by
  column key, so it survives sorting rewriting the header's indicator, and
  `remove_column` / `clear(columns=True)` drop it along with the column.
- **`get_cell_tooltip` is handed resolved keys, not a `Coordinate`.** Resolving
  the coordinate and guarding against it going stale mid-repaint is the
  boilerplate this exists to absorb. Return `None` for no tooltip; rendering
  and placement stay Textual's.
- **A tooltip is recomputed when the rows move under a stationary mouse.**
  `hover_coordinate` has not changed, so its watcher does not fire, and without
  this the tooltip would go on describing the row that used to be there.
- **A tooltip is cleared over filler space.** `DataTable` returns early without
  touching `hover_coordinate` when the mouse is over space carrying no
  row/column meta, so one set over a real cell would otherwise stick forever.
- **Tooltips need a shown cursor.** Cell and header tooltips alike follow
  `hover_coordinate`, which Textual only tracks while `show_cursor` is on and
  `cursor_type` is not `"none"`.
