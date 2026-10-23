# SPDX-FileCopyrightText: 2026 René de Hesselle <dehesselle@web.de>
#
# SPDX-License-Identifier: 0BSD

"""Resize a widget by dragging one of its own borders.

Every resizable pane needs the same three mouse handlers and the same drag
flag, whichever axis it resizes along. There is no separate handle widget
and no splitter: the border the widget already draws *is* the grab area, which
is why this is a mixin over any widget rather than a container to wrap things
in::

    class Sidebar(Resizable, Tree):
        RESIZE_EDGE = "right"
        RESIZE_MIN = 15
        RESIZE_MIN_SIBLING = 20

Mix it in **ahead** of the widget class. Textual dispatches a mouse handler
once per class in the MRO -- taking `_on_mouse_move` or `on_mouse_move` from
each class's own `__dict__`, so a widget's private handler and this one both
run -- and mixing in first is what puts this one first. That ordering is what
lets a drag in progress call `prevent_default()`, which stops the MRO walk and
so keeps the widget's own hover handling from running on top of the drag.

The sibling that gives up the space needs no code at all: give this widget a
starting size in `fr` and the sibling `1fr`, and switching this one to a fixed
cell size on drag leaves the sibling's `1fr` to claim the remainder.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Literal

if TYPE_CHECKING:
    from textual import events

#: Pointer shape shown while each edge is being dragged.
_POINTERS: dict[str, str] = {"right": "ew-resize", "bottom": "ns-resize"}


class Resizable:
    """Drag-to-resize behaviour for a widget with a border.

    Mixed in ahead of the widget class -- see the module docstring.
    """

    #: Which border is the grab area. "right" resizes the width, "bottom" the
    #: height.
    RESIZE_EDGE: ClassVar[Literal["right", "bottom"]] = "right"
    #: Cells this widget is never shrunk below.
    RESIZE_MIN: ClassVar[int] = 15
    #: Cells left to whatever shares the parent with this widget, so neither
    #: side can be dragged into uselessness.
    RESIZE_MIN_SIBLING: ClassVar[int] = 20

    #: Class-level default rather than an `__init__`: a mixin that had one
    #: would have to cooperate with the signature of every widget it is mixed
    #: into, and there is nothing here worth that.
    _resize_dragging: bool = False

    def on_mouse_down(self, event: events.MouseDown) -> None:
        # Coordinates are relative to this widget's own region, border
        # included, so the last row/column is exactly where the border is
        # drawn.
        size = self.outer_size  # type: ignore[attr-defined]
        if self.RESIZE_EDGE == "right":
            on_border = event.x == size.width - 1
        else:
            on_border = event.y == size.height - 1
        if not on_border:
            return
        self._resize_dragging = True
        self.capture_mouse()  # type: ignore[attr-defined]
        self.styles.pointer = _POINTERS[self.RESIZE_EDGE]  # type: ignore[attr-defined]
        event.stop()
        event.prevent_default()

    def on_mouse_move(self, event: events.MouseMove) -> None:
        if not self._resize_dragging:
            return
        # The dragged edge is the far one, so the near one stays put and the
        # captured coordinate -- still measured from it -- is the new size
        # directly. No delta to track.
        if self.RESIZE_EDGE == "right":
            self.styles.width = max(  # type: ignore[attr-defined]
                self.RESIZE_MIN, min(event.x + 1, self._resize_limit())
            )
        else:
            self.styles.height = max(  # type: ignore[attr-defined]
                self.RESIZE_MIN, min(event.y + 1, self._resize_limit())
            )
        event.stop()
        # Stops the MRO walk here, so the widget's own hover tracking does not
        # also run while the pointer is dragging a border around.
        event.prevent_default()

    def on_mouse_up(self, event: events.MouseUp) -> None:
        if not self._resize_dragging:
            return
        self._resize_dragging = False
        self.release_mouse()  # type: ignore[attr-defined]
        self.styles.pointer = "default"  # type: ignore[attr-defined]
        event.stop()
        event.prevent_default()

    def _resize_limit(self) -> int:
        """Largest size this widget may take, leaving the sibling its minimum.

        Measured against the parent rather than the screen: siblings share the
        parent's box, and for a pane stacked inside a container the screen's
        own height counts rows that a header and footer have already taken.
        Where a widget sits directly on the screen the two are the same
        number anyway.
        """
        container = self.parent  # type: ignore[attr-defined]
        size = container.size if container is not None else self.screen.size  # type: ignore[attr-defined]
        extent = size.width if self.RESIZE_EDGE == "right" else size.height
        return max(self.RESIZE_MIN, extent - self.RESIZE_MIN_SIBLING)
