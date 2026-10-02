"""A checkbox dropdown, built the same way Textual's own `Select` is built.

`Select` (`textual.widgets._select`) is not one widget but three cooperating
pieces: `SelectCurrent` (the always-visible trigger row), `SelectOverlay` (an
`OptionList` mounted as a real DOM child, shown via a CSS class rather than a
separate screen, using `overlay: screen` to paint above sibling content), and
`Select` itself, wiring the two together. `MultiSelect` copies that shape
exactly -- down to reusing `Select`'s own CSS values -- swapping `OptionList`
for `SelectionList` so each row carries a checkbox and more than one can be
picked at once. Placed next to a `Select` in the same toolbar, it reads as
the same kind of control instead of an approximation of one.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import ClassVar

from textual import events, on
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import SelectionList, Static
from textual.widgets.selection_list import Selection

#: Matches `Select`'s own arrow glyphs (`_select.py`'s `.down-arrow`/
#: `.up-arrow`), not the smaller `▾`/`▴` -- so a `MultiSelect` sitting next to
#: a `Select` reads as the same kind of control.
_ARROW_DOWN = "▼"
_ARROW_UP = "▲"


class _NonSelectableStatic(Static):
    """Same trick as Textual's own private `NonSelectableStatic` in
    `_select.py`: keeps the label/arrow out of text-selection."""

    ALLOW_SELECT = False


class MultiSelectCurrent(Horizontal):
    """The always-visible trigger row -- mirrors `SelectCurrent` almost
    verbatim. Unlike `SelectCurrent`, there's no dim-until-a-value-is-picked
    treatment: a multi-select's label is always real content (a count),
    never a placeholder standing in for "nothing chosen yet"."""

    DEFAULT_CSS = """
    MultiSelectCurrent {
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


class MultiSelectOverlay[SelectionType](SelectionList[SelectionType]):
    """The dropdown's popped-open contents -- mirrors `SelectOverlay`,
    subclassing `SelectionList` instead of `OptionList` so each row carries a
    checkbox."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "dismiss", "Dismiss menu", show=False),
    ]

    ALLOW_SELECT = False

    @dataclass
    class Dismiss(Message):
        """Inform the owning `MultiSelect` the overlay should be dismissed."""

        lost_focus: bool = False

    def action_dismiss(self) -> None:
        self.post_message(self.Dismiss())

    def _on_blur(self, _event: events.Blur) -> None:
        # This alone is what makes "click elsewhere closes it" work: no
        # manual outside-click / region hit-testing needed, same as `Select`.
        self.post_message(self.Dismiss(lost_focus=True))
        self.suppress_click()


class MultiSelect[SelectionType](Vertical, can_focus=True):
    """A checkbox dropdown -- see module docstring."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("enter,down,space,up", "show_overlay", "Show menu", show=False),
    ]

    ALLOW_SELECT = False

    DEFAULT_CSS = """
    MultiSelect {
        height: auto;
        color: $foreground;

        &.-textual-compact > MultiSelectCurrent {
            padding: 0 1 0 0;
            border: none !important;
        }

        .up-arrow {
            display: none;
        }

        &:focus > MultiSelectCurrent {
            border: tall $border;
            background-tint: $foreground 5%;
        }

        & > MultiSelectOverlay {
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
            & > .option-list--option {
                padding: 0 1;
            }
        }

        &.-expanded {
            .down-arrow {
                display: none;
            }
            .up-arrow {
                display: block;
            }
            & > MultiSelectOverlay {
                display: block;
            }
        }
    }
    """

    expanded: reactive[bool] = reactive(False, toggle_class="-expanded", init=False)
    """True to show the overlay, otherwise False."""
    compact: reactive[bool] = reactive(False, toggle_class="-textual-compact")
    """Make the control compact -- strips the trigger's border entirely and,
    same as a compact `Select`, the overlay's too (`OptionList`'s own
    `&.-textual-compact { border: none !important; }`, inherited unchanged
    by `SelectionList`, wins over this widget's own border rule below)."""

    class OptionToggled(Message):
        """Posted when a row's checkbox is toggled by the user -- mirrors
        `Select.Changed`, wrapping the overlay's own `SelectionList.
        SelectionToggled` so callers never need to reach past `MultiSelect`
        into its overlay."""

        def __init__(
            self, multi_select: MultiSelect[SelectionType], value: SelectionType
        ) -> None:
            super().__init__()
            self.multi_select = multi_select
            self.value = value

        @property
        def control(self) -> MultiSelect[SelectionType]:
            return self.multi_select

    def __init__(
        self,
        selections: Iterable[Selection[SelectionType]] = (),
        *,
        label: str = "",
        compact: bool = False,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self._label = label
        self._initial_selections = list(selections)
        self.compact = compact

    def compose(self) -> ComposeResult:
        yield MultiSelectCurrent(self._label)
        yield MultiSelectOverlay[SelectionType](*self._initial_selections).data_bind(
            compact=MultiSelect.compact
        )

    @property
    def label(self) -> str:
        return self.query_one(MultiSelectCurrent).label

    def set_label(self, label: str) -> None:
        self.query_one(MultiSelectCurrent).update(label)

    def add_option(self, selection: Selection[SelectionType]) -> None:
        self.query_one(MultiSelectOverlay).add_option(selection)

    @property
    def selected(self) -> list[SelectionType]:
        return self.query_one(MultiSelectOverlay).selected

    def is_selected(self, value: SelectionType) -> bool:
        return value in self.selected

    def select(self, value: SelectionType) -> None:
        self.query_one(MultiSelectOverlay).select(value)

    def deselect(self, value: SelectionType) -> None:
        self.query_one(MultiSelectOverlay).deselect(value)

    def watch_expanded(self, expanded: bool) -> None:
        if expanded:
            self.query_one(MultiSelectOverlay).focus(scroll_visible=False)

    @on(MultiSelectCurrent.Toggle)
    def _current_toggle(self, event: MultiSelectCurrent.Toggle) -> None:
        event.stop()
        self.expanded = not self.expanded

    @on(MultiSelectOverlay.Dismiss)
    def _overlay_dismiss(self, event: MultiSelectOverlay.Dismiss) -> None:
        event.stop()
        self.expanded = False
        if not event.lost_focus:
            # If the overlay didn't lose focus, re-focus the control itself.
            self.focus()

    @on(SelectionList.SelectionToggled)
    def _overlay_selection_toggled(self, event: SelectionList.SelectionToggled) -> None:
        event.stop()
        self.post_message(self.OptionToggled(self, event.selection.value))

    def action_show_overlay(self) -> None:
        self.expanded = True
        overlay = self.query_one(MultiSelectOverlay)
        if overlay.highlighted is None:
            overlay.action_first()
