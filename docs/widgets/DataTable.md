# Data table

Textual's `DataTable` does not sort and has no per-cell or per-header
tooltips: clicking a header posts `HeaderSelected` and stops there, and
`tooltip` is a property of the whole widget. Both halves turn out to be
mostly workarounds for the same few Textual internals. It also has no way to get
its contents back out as text, so this one adds [CSV export](#export).

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

## Export

`to_csv()` returns everything the table holds as a CSV string. Binding a key to it
and saving the result are the app's business, and `App.deliver_text` does the
saving without any dialog:

```python
self.app.deliver_text(
    io.StringIO(table.to_csv(delimiter=";", tooltips=True)),
    save_filename="files.csv",
    encoding="utf-8-sig",  # Excel only detects UTF-8 with a BOM
)
```

- **It exports what the table holds, not what fits on screen.** Rows and columns
  scrolled out of view are included, and a value is not cut to its column's width
  or its row's height. Rows come in display order, and headers without their sort
  indicator. Row labels, when shown, become a leading column under an empty header.
  The header row is always written, even with `show_header=False`, because a CSV
  is hard to use without one.
- **A value is exported whole.** A float keeps its full precision (`1.23456`, where
  the table paints `1.23`), and `None` is empty. A cell showing `7.2K` as its value
  exports `7.2K`; see `tooltips` for the full value behind it.
- **A `str` cell has its markup parsed, so its tags stay out of the CSV**:
  `[red]x[/red]` exports as `x`. That also means `[foo] bar` loses `[foo]`, as it
  does on screen. Data from outside the app belongs in a `Text` cell, which is
  taken literally on screen and in the export.
- **`tooltips=True` exports a cell's tooltip instead of its text** wherever
  `get_cell_tooltip` returns one, and the cell's text everywhere else. A column
  showing `7.2K` or `2 days ago` can export the full value behind it this way.
  Tooltips are exported as they are, so leave this off for a table whose tooltips
  say something else about the cell.
- **A tooltip that is not text counts as no tooltip.** A Rich table, say, has no
  single value to export, so the cell's own text is used. A `str` tooltip is
  parsed as markup, as it is when rendered; if that fails it stays literal, since
  an export evaluates every tooltip and one bad row must not lose the whole export.
- **A cell with no text of its own exports empty**, such as a Rich `Panel`. With
  `tooltips=True` it can still export a tooltip.
- **`delimiter` picks the column separator**: the classic comma, or a semicolon
  for Excel in locales that use a decimal comma. Quoting is left to `csv.writer`,
  so only fields containing the delimiter, a quote or a line break get quoted.
- **Lines end in a bare `\n`**, not the `\r\n` `csv` defaults to. Saving through a
  text-mode file, as `deliver_text` does, turns `\r\n` into `\r\r\n` on Windows,
  which spreadsheets show as a blank row after every line.
- **The table only knows the rows it was given.** If an app shows the first 100
  of 5,000 rows, the CSV holds those 100 and looks complete. Telling the user
  that it is partial is up to the app.
- **Nothing is escaped against formulas.** Excel evaluates a field starting with
  `=` as a formula, and one starting with `+`, `-` or `@` when an expression
  follows (`-2+3`, `@SUM(A1)`); a plain `-5` stays a number. An app exporting
  untrusted data should be aware of this. Escaping here would change the data,
  and would have to tell numbers from expressions.
