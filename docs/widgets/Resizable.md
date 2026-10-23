# Resizable

Dragging a pane's border to resize it, along either axis. There is no handle
widget and no splitter: the border the widget already draws *is* the grab
area.

```python
from textual.widgets import Tree

from tcoda.widgets import Resizable


class Sidebar(Resizable, Tree):
    RESIZE_EDGE = "right"  # or "bottom"
    RESIZE_MIN = 15
    RESIZE_MIN_SIBLING = 20
```

- **Mix it in ahead of the widget class.** Textual dispatches a mouse handler
  once per class in the MRO — taking `_on_mouse_move` or `on_mouse_move` from
  each class's own `__dict__` — so the mixin's handler and the widget's own
  private one both run, and mixing in first is what puts the mixin first. The
  "one form per class, never both" rule that bites people applies *within* a
  class, not across the MRO.
- **A drag in progress calls `prevent_default()`**, which ends the MRO walk, so
  the widget underneath does not chase the pointer while a border is being
  dragged. Without it, dragging a tree's border would also drive the tree's
  hover highlight.
- **The sibling needs no code at all.** Give this widget a starting size in
  `fr` and the sibling `1fr`; switching this one to a fixed cell size on drag
  leaves the sibling's `1fr` to claim the rest.
- **Limits are measured against the parent, not the screen.** Siblings share
  the parent's box, and for a pane stacked inside a container the screen's own
  height counts rows a header and footer already took. Where a widget sits
  directly on the screen the two numbers are the same anyway, so one rule
  covers both.
- **`RESIZE_MIN` and `RESIZE_MIN_SIBLING` are the guard rails**, so neither
  side can be dragged into uselessness.
- **The mixin has no `__init__`**; the drag flag is a class-level default
  instead. See [DESIGN.md](../DESIGN.md#mixins-go-first-and-have-no-__init__).
