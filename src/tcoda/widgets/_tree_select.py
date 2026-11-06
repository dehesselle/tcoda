# SPDX-FileCopyrightText: 2026 René de Hesselle <dehesselle@web.de>
#
# SPDX-License-Identifier: 0BSD

"""A checkbox dropdown whose rows form a tree, built the way Textual's own
`Select` is built.

`Select` (`textual.widgets._select`) is not one widget but three cooperating
pieces: `SelectCurrent` (the always-visible trigger row), `SelectOverlay` (an
`OptionList` mounted as a real DOM child, shown via a CSS class rather than a
separate screen, using `overlay: screen` to paint above sibling content), and
`Select` itself, wiring the two together. `TreeSelect` copies that shape --
down to reusing `Select`'s own CSS values -- swapping `OptionList` for a `Tree`
whose rows carry a checkbox. Placed next to a `Select` in the same toolbar, it
reads as the same kind of control instead of an approximation of one.

Options are identified by their path, such as `("a", "b", "c")`. Missing
parents become group rows, which can be toggled but are not options themselves.

Each row keeps its own checked flag and a new row takes its parent's, the way
a logger takes its parent's level (`logging.Logger.getEffectiveLevel`).
Unchecking a parent therefore also covers children that do not exist yet, which
a set of unchecked options could not do. What a row displays is worked out from
the options beneath it instead, so that it tells the truth about them.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from typing import ClassVar

from rich.cells import cell_len
from rich.style import Style
from rich.text import Text
from textual import events, on
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Checkbox, Static, Tree
from textual.widgets.tree import TreeNode

#: Matches `Select`'s own arrow glyphs (`_select.py`'s `.down-arrow`/
#: `.up-arrow`), not the smaller `▾`/`▴` -- so a `TreeSelect` sitting next to a
#: `Select` reads as the same kind of control.
_ARROW_DOWN = "▼"
_ARROW_UP = "▲"

#: What a row's checkbox shows when the options beneath it disagree.
_MIXED_INNER = "-"


class _NonSelectableStatic(Static):
    """Same trick as Textual's own private `NonSelectableStatic` in
    `_select.py`: keeps the label/arrow out of text-selection."""

    ALLOW_SELECT = False


class TreeSelectCurrent(Horizontal):
    """The always-visible trigger row -- mirrors `SelectCurrent` almost
    verbatim. Unlike `SelectCurrent`, there's no dim-until-a-value-is-picked
    treatment: this label is always real content (a count), never a placeholder
    standing in for "nothing chosen yet"."""

    DEFAULT_CSS = """
    TreeSelectCurrent {
        border: tall $border-blurred;
        color: $foreground;
        background: $surface;
        width: 1fr;
        height: auto;
        padding: 0 2;
        pointer: pointer;

        &.-textual-compact {
            border: none !important;
        }

        &:ansi {
            border: tall $border-blurred;
            color: ansi_default;
            background: ansi_default;
            &:focus {
                border: tall $border;
            }
        }

        Static#label {
            width: 1fr;
            height: auto;
            color: $foreground;
            background: transparent;
        }

        .arrow {
            box-sizing: content-box;
            width: 1;
            height: 1;
            padding: 0 0 0 1;
            color: $foreground 50%;
            background: transparent;
        }
    }
    """

    ALLOW_SELECT = False

    class Toggle(Message):
        """Request to toggle the overlay -- mirrors `SelectCurrent.Toggle`."""

    def __init__(self, label: str) -> None:
        super().__init__()
        self._label = label

    def compose(self) -> ComposeResult:
        yield _NonSelectableStatic(self._label, id="label")
        yield _NonSelectableStatic(_ARROW_DOWN, classes="arrow down-arrow")
        yield _NonSelectableStatic(_ARROW_UP, classes="arrow up-arrow")

    @property
    def label(self) -> str:
        return self._label

    def update(self, label: str) -> None:
        self._label = label
        self.query_one("#label", Static).update(label)

    def _on_click(self, event: events.Click) -> None:
        event.stop()
        self.post_message(self.Toggle())


@dataclass(slots=True)
class _Row:
    """What a tree node carries."""

    path: tuple[str, ...]
    checked: bool
    is_option: bool = False


def _row(node: TreeNode[_Row]) -> _Row:
    assert node.data is not None
    return node.data


def _option_flags(node: TreeNode[_Row]) -> Iterator[bool]:
    """The checked flag of every option at or beneath `node`."""
    row = _row(node)
    if row.is_option:
        yield row.checked
    for child in node.children:
        yield from _option_flags(child)


def _displayed_state(node: TreeNode[_Row]) -> bool | None:
    """Checked, unchecked or, as `None`, mixed. A group with no option beneath
    it has only its own flag to go by."""
    flags = set(_option_flags(node))
    if not flags:
        return _row(node).checked
    return flags.pop() if len(flags) == 1 else None


class TreeSelectOverlay(Tree[_Row]):
    """The dropdown's popped-open contents -- mirrors `SelectOverlay`,
    subclassing `Tree` instead of `OptionList` so rows can nest."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "dismiss", "Dismiss menu", show=False),
        # `Tree` gives space to expanding, but a row here is a checkbox first,
        # and `SelectionList` and `Checkbox` both toggle on space. It goes
        # through the same action as enter and a click, so there is one path.
        Binding("space", "select_cursor", "Toggle", show=False),
        Binding("right", "expand_cursor", "Expand", show=False),
        Binding("left", "collapse_cursor", "Collapse", show=False),
    ]

    COMPONENT_CLASSES: ClassVar[set[str]] = {
        "tree-select--button",
        "tree-select--button-checked",
        "tree-select--button-mixed",
    }

    ALLOW_SELECT = False

    DEFAULT_CSS = """
    TreeSelectOverlay {
        &.-textual-compact {
            border: none !important;
        }

        & > .tree-select--button {
            color: $panel-darken-2;
            background: $panel;
        }

        & > .tree-select--button-checked {
            color: $text-success;
            background: $panel;
        }

        & > .tree-select--button-mixed {
            color: $text-warning;
            background: $panel;
        }
    }
    """

    compact: reactive[bool] = reactive(False, toggle_class="-textual-compact")
    """Strips the border, as `OptionList`'s own `compact` does for a `Select`."""

    @dataclass
    class Dismiss(Message):
        """Inform the owning `TreeSelect` the overlay should be dismissed."""

        lost_focus: bool = False

    def __init__(self, options: Iterable[Sequence[str]] = ()) -> None:
        super().__init__("", _Row((), True))
        self.show_root = False
        # A row's main verb is its checkbox: expanding has its own key and arrow.
        self.auto_expand = False
        self.guide_depth = 2
        self._by_path: dict[tuple[str, ...], TreeNode[_Row]] = {(): self.root}
        for path in options:
            self.add_option(path)

    def _node(self, path: tuple[str, ...]) -> TreeNode[_Row]:
        """The node at `path`, created along with any missing parents."""
        node = self._by_path.get(path)
        if node is not None:
            return node
        parent = self._node(path[:-1])
        # A label is arbitrary text, so `Text` rather than `str`, which `Tree`
        # would parse as markup.
        node = parent.add(
            Text(path[-1]),
            _Row(path, _row(parent).checked),
            before=next(
                (c for c in parent.children if _row(c).path[-1] > path[-1]), None
            ),
            allow_expand=False,
        )
        parent.allow_expand = True
        self._by_path[path] = node
        # The first row, arriving while open. Otherwise `TreeSelect` sees to it
        # on opening.
        if self.has_focus and self.cursor_line == -1:
            self.cursor_line = 0
        return node

    def _refresh_rows(self) -> None:
        """Repaint every visible row. A change to one row also changes what its
        ancestors display, and `Tree` caches a rendered line until its node says
        otherwise."""
        for line in range(self.last_line + 1):
            node = self.get_node_at_line(line)
            if node is not None:
                node.refresh()

    def add_option(self, path: Sequence[str]) -> None:
        path = tuple(path)
        # A new row makes `Tree` drop its cached lines, an existing one doesn't.
        exists = path in self._by_path
        _row(self._node(path)).is_option = True
        if exists:
            self._refresh_rows()

    def is_checked(self, path: Sequence[str]) -> bool:
        """The row's own flag or, for a row that doesn't exist yet, the flag it
        would take."""
        path = tuple(path)
        while (node := self._by_path.get(path)) is None:
            path = path[:-1]
        return _row(node).checked

    def set_checked(self, path: Sequence[str], checked: bool) -> None:
        """Set a row and everything beneath it, creating the row if need be."""

        def set_subtree(node: TreeNode[_Row]) -> None:
            _row(node).checked = checked
            for child in node.children:
                set_subtree(child)

        set_subtree(self._node(tuple(path)))
        self._refresh_rows()

    def toggle(self, path: Sequence[str]) -> bool:
        """Toggle a row and everything beneath it. A mixed row becomes checked.
        Returns the row's new state."""
        checked = _displayed_state(self._node(tuple(path))) is not True
        self.set_checked(path, checked)
        return checked

    def render_label(
        self, node: TreeNode[_Row], base_style: Style, style: Style
    ) -> Text:
        match _displayed_state(node):
            case True:
                component, inner = "button-checked", Checkbox.BUTTON_INNER
            case False:
                component, inner = "button", Checkbox.BUTTON_INNER
            case None:
                component, inner = "button-mixed", _MIXED_INNER
        button = self.get_component_rich_style(f"tree-select--{component}")
        # The half-block sides take the button's background as their colour,
        # the same way `SelectionList` and `ToggleButton` draw them.
        side = Style.from_color(button.bgcolor, (base_style + style).bgcolor)
        return Text.assemble(
            (Checkbox.BUTTON_LEFT, base_style + side),
            (inner, base_style + button),
            (Checkbox.BUTTON_RIGHT, base_style + side),
            (" ", base_style),
            super().render_label(node, base_style, style),
        )

    def get_label_width(self, node: TreeNode[_Row]) -> int:
        # The default renders the label, but `Tree` also measures before the
        # stylesheet has reached this widget, when the button styles above
        # don't exist yet. The checkbox is the same width in any state.
        button = cell_len(
            Checkbox.BUTTON_LEFT + Checkbox.BUTTON_INNER + Checkbox.BUTTON_RIGHT + " "
        )
        return button + super().render_label(node, Style(), Style()).cell_len

    def action_dismiss(self) -> None:
        self.post_message(self.Dismiss())

    def action_expand_cursor(self) -> None:
        node = self.cursor_node
        if node is not None and node.allow_expand:
            node.expand()

    def action_collapse_cursor(self) -> None:
        node = self.cursor_node
        if node is None:
            return
        if node.allow_expand and node.is_expanded:
            node.collapse()
        # The root is never shown, so the cursor can't go there.
        elif node.parent is not self.root:
            self.action_cursor_parent()

    def _on_blur(self, _event: events.Blur) -> None:
        # This alone is what makes "click elsewhere closes it" work: no
        # manual outside-click / region hit-testing needed, same as `Select`.
        self.post_message(self.Dismiss(lost_focus=True))
        self.suppress_click()


class TreeSelect(Vertical, can_focus=True):
    """A checkbox dropdown whose rows form a tree -- see module docstring."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("enter,down,space,up", "show_overlay", "Show menu", show=False),
    ]

    ALLOW_SELECT = False

    DEFAULT_CSS = """
    TreeSelect {
        height: auto;
        color: $foreground;

        &.-textual-compact > TreeSelectCurrent {
            padding: 0 1 0 0;
            border: none !important;
        }

        .up-arrow {
            display: none;
        }

        &:focus > TreeSelectCurrent {
            border: tall $border;
            background-tint: $foreground 5%;
        }

        & > TreeSelectOverlay {
            width: auto;
            min-width: 1fr;
            max-width: 60vw;
            display: none;
            height: auto;
            max-height: 12;
            overlay: screen;
            constrain: none inside;
            color: $foreground;
            border: tall $border-blurred;
            background: $surface;
            &:focus {
                background-tint: $foreground 5%;
            }
        }

        &.-expanded {
            .down-arrow {
                display: none;
            }
            .up-arrow {
                display: block;
            }
            & > TreeSelectOverlay {
                display: block;
            }
        }
    }
    """

    expanded: reactive[bool] = reactive(False, toggle_class="-expanded", init=False)
    """True to show the overlay, otherwise False."""
    compact: reactive[bool] = reactive(False, toggle_class="-textual-compact")
    """Make the control compact -- strips the border of both the trigger and,
    same as a compact `Select`, the overlay."""

    class Toggled(Message):
        """Posted when the user toggles a row -- mirrors `Select.Changed`, so
        callers never need to reach past `TreeSelect` into its overlay. Fires
        once for the row itself, whatever else toggling it changed beneath."""

        def __init__(
            self, tree_select: TreeSelect, path: tuple[str, ...], checked: bool
        ) -> None:
            super().__init__()
            self.tree_select = tree_select
            self.path = path
            self.checked = checked

        @property
        def control(self) -> TreeSelect:
            return self.tree_select

    def __init__(
        self,
        options: Iterable[Sequence[str]] = (),
        *,
        label: str = "",
        compact: bool = False,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self._label = label
        self._initial_options = list(options)
        self.compact = compact

    def compose(self) -> ComposeResult:
        yield TreeSelectCurrent(self._label)
        yield TreeSelectOverlay(self._initial_options).data_bind(
            compact=TreeSelect.compact
        )

    @property
    def label(self) -> str:
        return self.query_one(TreeSelectCurrent).label

    def set_label(self, label: str) -> None:
        self.query_one(TreeSelectCurrent).update(label)

    def add_option(self, path: Sequence[str]) -> None:
        self.query_one(TreeSelectOverlay).add_option(path)

    def is_checked(self, path: Sequence[str]) -> bool:
        return self.query_one(TreeSelectOverlay).is_checked(path)

    def set_checked(self, path: Sequence[str], checked: bool) -> None:
        self.query_one(TreeSelectOverlay).set_checked(path, checked)

    def watch_expanded(self, expanded: bool) -> None:
        if expanded:
            overlay = self.query_one(TreeSelectOverlay)
            overlay.focus(scroll_visible=False)
            # So that space works straight away, however it was opened.
            if overlay.cursor_line == -1:
                overlay.cursor_line = 0

    @on(TreeSelectCurrent.Toggle)
    def _current_toggle(self, event: TreeSelectCurrent.Toggle) -> None:
        event.stop()
        self.expanded = not self.expanded

    @on(TreeSelectOverlay.Dismiss)
    def _overlay_dismiss(self, event: TreeSelectOverlay.Dismiss) -> None:
        event.stop()
        self.expanded = False
        if not event.lost_focus:
            # If the overlay didn't lose focus, re-focus the control itself.
            self.focus()

    @on(Tree.NodeSelected)
    def _overlay_node_selected(self, event: Tree.NodeSelected[_Row]) -> None:
        event.stop()
        path = _row(event.node).path
        checked = self.query_one(TreeSelectOverlay).toggle(path)
        self.post_message(self.Toggled(self, path, checked))

    @on(Tree.NodeHighlighted)
    @on(Tree.NodeExpanded)
    @on(Tree.NodeCollapsed)
    def _keep_tree_messages_inside(self, event: Message) -> None:
        # That the overlay is a `Tree` is this widget's business. A host's own
        # `on_tree_node_expanded` shouldn't be handed nodes from in here.
        event.stop()

    def action_show_overlay(self) -> None:
        self.expanded = True
