# SPDX-FileCopyrightText: 2026 René de Hesselle <dehesselle@web.de>
#
# SPDX-License-Identifier: 0BSD

"""TreeSelect: the generic checkbox-dropdown mechanics -- open/close via click,
keyboard and blur, toggling rows, how rows inherit and display their state,
compact mode, and scrolling a tall tree. Domain-specific integration (labels,
hiding log sources) is covered in test_log_viewer.py instead."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

from textual.app import App, ComposeResult
from textual.pilot import Pilot
from textual.widgets import Button, Checkbox, Tree

from tcoda.widgets._tree_select import (
    TreeSelect,
    TreeSelectCurrent,
    TreeSelectOverlay,
)


class Harness(App[None]):
    """A `TreeSelect` plus a focusable `Button`, so tests can move focus
    elsewhere the same way a real toolbar would."""

    def __init__(
        self,
        options: Sequence[Sequence[str]] = (("a",), ("b",), ("c",)),
        *,
        compact: bool = False,
    ) -> None:
        super().__init__()
        self._options = options
        self._compact = compact

    def compose(self) -> ComposeResult:
        yield TreeSelect(
            self._options, label="Pick", compact=self._compact, id="tree-select"
        )
        yield Button("Elsewhere", id="elsewhere")


NESTED = (("a", "x"), ("a", "y"), ("b",))


async def settle(pilot: Pilot[None], rounds: int = 3) -> None:
    for _ in range(rounds):
        await pilot.pause()
        await asyncio.sleep(0.02)


async def opened(pilot: Pilot[None]) -> tuple[TreeSelect, TreeSelectOverlay]:
    await pilot.pause()
    await pilot.click("#tree-select")
    await settle(pilot)
    tree_select = pilot.app.query_one("#tree-select", TreeSelect)
    return tree_select, tree_select.query_one(TreeSelectOverlay)


def rows(overlay: TreeSelectOverlay) -> list[str]:
    """What each visible row says, guides and arrows included."""
    return [overlay.render_line(y).text.rstrip() for y in range(overlay.last_line + 1)]


# ------------------------------------------------------------------ the popup


async def test_clicking_the_trigger_opens_the_overlay() -> None:
    app = Harness()
    async with app.run_test(size=(40, 24)) as pilot:
        await pilot.pause()
        tree_select = app.query_one("#tree-select", TreeSelect)
        assert tree_select.expanded is False

        await pilot.click("#tree-select")
        await settle(pilot)
        assert tree_select.expanded is True


async def test_reclicking_the_trigger_does_not_close_it_matching_select() -> None:
    """Not a bug: a single click on the trigger while open both blurs the
    overlay (dismissing it) and re-toggles `expanded` via `SelectCurrent.
    Toggle`, netting no change -- confirmed against a real stock `Select`,
    which has the exact same quirk. Escape or clicking a genuinely different
    focusable widget are the ways to close it (see the tests below)."""
    app = Harness()
    async with app.run_test(size=(40, 24)) as pilot:
        tree_select, _ = await opened(pilot)
        assert tree_select.expanded is True

        await pilot.click("#tree-select")
        await settle(pilot)
        assert tree_select.expanded is True


async def test_escape_closes_the_overlay() -> None:
    app = Harness()
    async with app.run_test(size=(40, 24)) as pilot:
        tree_select, _ = await opened(pilot)
        assert tree_select.expanded is True

        await pilot.press("escape")
        await settle(pilot)
        assert tree_select.expanded is False


async def test_moving_focus_to_another_widget_closes_it() -> None:
    """Blur-driven, matching `Select`: no manual outside-click detection --
    moving focus to another widget dismisses the overlay for free. Tab,
    not a click, is used to move focus here: the open overlay visually (and
    hit-test-wise) sits on top of anything below it on screen, same as a
    real `Select`'s overlay would, so a click "behind" it lands on the
    overlay itself rather than the widget underneath.

    A click that lands on nothing focusable (e.g. bare screen background)
    does *not* close it either -- confirmed against a real stock `Select`,
    which behaves identically. Only Escape or focusing something else does."""
    app = Harness()
    async with app.run_test(size=(40, 24)) as pilot:
        tree_select, _ = await opened(pilot)
        assert tree_select.expanded is True

        await pilot.press("tab")
        await settle(pilot)
        assert tree_select.expanded is False


async def test_space_toggles_the_first_row_right_after_a_mouse_open() -> None:
    app = Harness()
    async with app.run_test(size=(40, 24)) as pilot:
        tree_select, _ = await opened(pilot)
        await pilot.press("space")
        await settle(pilot)
        assert tree_select.is_checked(["a"]) is False


async def test_space_toggles_a_first_row_that_arrives_while_open() -> None:
    app = Harness(())
    async with app.run_test(size=(40, 24)) as pilot:
        tree_select, _ = await opened(pilot)
        tree_select.add_option(["a"])
        await settle(pilot)

        await pilot.press("space")
        await settle(pilot)
        assert tree_select.is_checked(["a"]) is False


async def test_compact_strips_both_the_trigger_and_overlay_border() -> None:
    """Matches the real `Select`: `compact=True` removes the trigger's
    border, and -- verified against a real stock `Select` -- the overlay's
    too."""
    app = Harness(compact=True)
    async with app.run_test(size=(40, 24)) as pilot:
        await pilot.pause()
        tree_select = app.query_one("#tree-select", TreeSelect)
        current = tree_select.query_one(TreeSelectCurrent)
        assert current.styles.border_top[0] == ""

        await pilot.click("#tree-select")
        await settle(pilot)
        overlay = tree_select.query_one(TreeSelectOverlay)
        assert overlay.styles.border_top[0] == ""


class NarrowHarness(App[None]):
    CSS = "#tree-select { width: 12; }"

    def __init__(self, option: str) -> None:
        super().__init__()
        self._option = option

    def compose(self) -> ComposeResult:
        yield TreeSelect([(self._option,)], label="Pick", id="tree-select")


async def test_the_overlay_widens_for_a_long_option_added_while_open() -> None:
    """Options can be discovered live and their names are arbitrary text,
    unlike a `Select`'s usually-static, caller-sized option list -- so the
    overlay can't just inherit the trigger's fixed width the way a real
    `Select`'s does. `width: auto` (with `min-width: 1fr` so it's never narrower
    than the trigger) lets it grow to fit the longest known option, live, even
    while already open."""
    app = NarrowHarness("short")
    async with app.run_test(size=(80, 24)) as pilot:
        tree_select, overlay = await opened(pilot)
        before = overlay.region.width

        overlay.add_option(["a-much-longer-source-name"])
        await settle(pilot)
        assert overlay.region.width > before
        assert tree_select.region.width == 12


async def test_the_overlay_width_is_capped_for_an_extremely_long_option() -> None:
    """An unreasonably long single name must not push the overlay off the edge
    of the screen."""
    app = NarrowHarness("x" * 200)
    async with app.run_test(size=(80, 24)) as pilot:
        _, overlay = await opened(pilot)
        assert overlay.region.width <= 80


async def test_a_tall_tree_scrolls() -> None:
    app = Harness([(f"option-{i:02}",) for i in range(30)])
    async with app.run_test(size=(40, 24)) as pilot:
        _, overlay = await opened(pilot)
        assert overlay.scrollable_content_region.height < overlay.last_line + 1
        overlay.scroll_end(animate=False)
        await settle(pilot)
        assert overlay.scroll_y > 0


# ------------------------------------------------------------------- the tree


async def test_a_label_is_taken_literally_rather_than_as_markup() -> None:
    app = Harness([("[bold]odd[/bold]",)])
    async with app.run_test(size=(40, 24)) as pilot:
        _, overlay = await opened(pilot)
        assert "[bold]odd[/bold]" in rows(overlay)[0]


async def test_siblings_are_sorted_whatever_order_they_arrive_in() -> None:
    app = Harness([("c",), ("a",)])
    async with app.run_test(size=(40, 24)) as pilot:
        _, overlay = await opened(pilot)
        overlay.add_option(["b"])
        await settle(pilot)
        assert [row[-1] for row in rows(overlay)] == ["a", "b", "c"]


async def test_groups_start_collapsed_and_children_show_once_expanded() -> None:
    app = Harness(NESTED)
    async with app.run_test(size=(40, 24)) as pilot:
        _, overlay = await opened(pilot)
        assert [row[-1] for row in rows(overlay)] == ["a", "b"]

        await pilot.press("right")
        await settle(pilot)
        assert [row[-1] for row in rows(overlay)] == ["a", "x", "y", "b"]


async def test_a_leaf_that_gains_a_child_becomes_an_expandable_parent() -> None:
    app = Harness([("a",)])
    async with app.run_test(size=(40, 24)) as pilot:
        _, overlay = await opened(pilot)
        assert Tree.ICON_NODE not in rows(overlay)[0]

        overlay.add_option(["a", "child"])
        await settle(pilot)
        assert Tree.ICON_NODE in rows(overlay)[0]
        await pilot.press("right")
        await settle(pilot)
        assert rows(overlay)[1].endswith("child")


async def test_left_collapses_a_group_and_otherwise_moves_to_the_parent() -> None:
    app = Harness(NESTED)
    async with app.run_test(size=(40, 24)) as pilot:
        _, overlay = await opened(pilot)
        await pilot.press("right", "down")
        await settle(pilot)
        assert rows(overlay)[overlay.cursor_line].endswith("x")

        await pilot.press("left")
        await settle(pilot)
        assert rows(overlay)[overlay.cursor_line].endswith("a")
        assert len(rows(overlay)) == 4

        await pilot.press("left")
        await settle(pilot)
        assert [row[-1] for row in rows(overlay)] == ["a", "b"]


async def test_left_on_a_top_level_row_keeps_the_cursor_there() -> None:
    """The tree's root is never shown, so the cursor must not go to it."""
    app = Harness()
    async with app.run_test(size=(40, 24)) as pilot:
        _, overlay = await opened(pilot)
        await pilot.press("down", "left")
        await settle(pilot)
        assert overlay.cursor_line == 1


async def test_a_new_row_leaves_the_cursor_on_the_row_it_was_on() -> None:
    app = Harness([("b",), ("c",)])
    async with app.run_test(size=(40, 24)) as pilot:
        _, overlay = await opened(pilot)
        await pilot.press("down")
        await settle(pilot)
        assert rows(overlay)[overlay.cursor_line].endswith("c")

        overlay.add_option(["a"])
        await settle(pilot)
        assert rows(overlay)[overlay.cursor_line].endswith("c")


async def test_clicking_a_row_toggles_it_and_clicking_its_arrow_expands_it() -> None:
    app = Harness(NESTED)
    async with app.run_test(size=(40, 24)) as pilot:
        tree_select, overlay = await opened(pilot)
        arrow = rows(overlay)[0].index(Tree.ICON_NODE.strip())
        # A click's offset counts from the border, a row's from inside it.
        left, top = overlay.content_offset

        await pilot.click(overlay, offset=(left + arrow, top))
        await settle(pilot)
        assert tree_select.is_checked(["a"]) is True
        assert len(rows(overlay)) == 4

        await pilot.click(overlay, offset=(left + 1, top + 3))
        await settle(pilot)
        assert tree_select.is_checked(["b"]) is False


async def test_the_trees_own_messages_stay_inside_the_widget() -> None:
    """A host with a `Tree` of its own must not be handed these nodes."""
    leaked: list[object] = []

    class RecordingHarness(Harness):
        def on_tree_node_expanded(self, event: Tree.NodeExpanded[object]) -> None:
            leaked.append(event)

        def on_tree_node_highlighted(self, event: Tree.NodeHighlighted[object]) -> None:
            leaked.append(event)

        def on_tree_node_selected(self, event: Tree.NodeSelected[object]) -> None:
            leaked.append(event)

    app = RecordingHarness(NESTED)
    async with app.run_test(size=(40, 24)) as pilot:
        await opened(pilot)
        await pilot.press("right", "down", "space")
        await settle(pilot)
        assert leaked == []


# ------------------------------------------------------------------ the state


async def test_options_start_checked() -> None:
    app = Harness(NESTED)
    async with app.run_test(size=(40, 24)) as pilot:
        await pilot.pause()
        tree_select = app.query_one("#tree-select", TreeSelect)
        assert tree_select.is_checked(["a", "x"]) is True


async def test_toggling_a_row_posts_toggled_once_for_that_row() -> None:
    events: list[tuple[tuple[str, ...], bool]] = []

    class RecordingHarness(Harness):
        def on_tree_select_toggled(self, event: TreeSelect.Toggled) -> None:
            events.append((event.path, event.checked))

    app = RecordingHarness(NESTED)
    async with app.run_test(size=(40, 24)) as pilot:
        await opened(pilot)
        await pilot.press("space")
        await settle(pilot)
        assert events == [(("a",), False)]


async def test_setting_a_row_from_code_does_not_post_toggled() -> None:
    events: list[TreeSelect.Toggled] = []

    class RecordingHarness(Harness):
        def on_tree_select_toggled(self, event: TreeSelect.Toggled) -> None:
            events.append(event)

    app = RecordingHarness()
    async with app.run_test(size=(40, 24)) as pilot:
        await pilot.pause()
        tree_select = app.query_one("#tree-select", TreeSelect)

        tree_select.set_checked(["a"], False)
        await settle(pilot)
        assert tree_select.is_checked(["a"]) is False

        tree_select.set_checked(["a"], True)
        await settle(pilot)
        assert tree_select.is_checked(["a"]) is True
        assert events == []


async def test_toggling_a_group_sets_everything_beneath_it() -> None:
    app = Harness(NESTED)
    async with app.run_test(size=(40, 24)) as pilot:
        tree_select, _ = await opened(pilot)
        await pilot.press("space")
        await settle(pilot)
        assert tree_select.is_checked(["a", "x"]) is False
        assert tree_select.is_checked(["a", "y"]) is False
        assert tree_select.is_checked(["b"]) is True


async def test_a_new_row_takes_its_parents_flag() -> None:
    app = Harness(NESTED)
    async with app.run_test(size=(40, 24)) as pilot:
        await pilot.pause()
        tree_select = app.query_one("#tree-select", TreeSelect)
        tree_select.set_checked(["a"], False)

        tree_select.add_option(["a", "new", "deep"])
        assert tree_select.is_checked(["a", "new", "deep"]) is False
        assert tree_select.is_checked(["a", "new"]) is False

        tree_select.add_option(["c"])
        assert tree_select.is_checked(["c"]) is True


async def test_unchecking_only_child_leaves_a_later_sibling_checked() -> None:
    """Only a decision about the group covers what comes later. A group whose
    single option happens to be unchecked hasn't had one made about it."""
    app = Harness([("a", "x")])
    async with app.run_test(size=(40, 24)) as pilot:
        await pilot.pause()
        tree_select = app.query_one("#tree-select", TreeSelect)
        tree_select.set_checked(["a", "x"], False)

        tree_select.add_option(["a", "y"])
        assert tree_select.is_checked(["a", "y"]) is True


async def test_a_row_not_yet_there_answers_with_the_flag_it_would_take() -> None:
    app = Harness(NESTED)
    async with app.run_test(size=(40, 24)) as pilot:
        await pilot.pause()
        tree_select = app.query_one("#tree-select", TreeSelect)
        tree_select.set_checked(["a"], False)
        assert tree_select.is_checked(["a", "not", "there"]) is False
        assert tree_select.is_checked(["not-there"]) is True


def button(overlay: TreeSelectOverlay, line: int) -> tuple[str, str]:
    """The checkbox of a visible row: its glyph and colour. Checked and unchecked
    share a glyph, as in `SelectionList`, and differ only by colour."""
    for segment in overlay.render_line(line):
        if segment.text in (Checkbox.BUTTON_INNER, "-"):
            assert segment.style is not None
            return segment.text, str(segment.style.color)
    raise AssertionError(f"no checkbox on line {line}")


async def test_a_group_shows_the_state_of_the_options_beneath_it() -> None:
    app = Harness(NESTED)
    async with app.run_test(size=(40, 24)) as pilot:
        tree_select, overlay = await opened(pilot)
        checked = button(overlay, 0)
        assert checked[0] == Checkbox.BUTTON_INNER

        tree_select.set_checked(["a", "x"], False)
        await settle(pilot)
        mixed = button(overlay, 0)
        assert mixed[0] == "-"

        tree_select.set_checked(["a", "y"], False)
        await settle(pilot)
        unchecked = button(overlay, 0)
        assert unchecked[0] == Checkbox.BUTTON_INNER
        assert len({checked[1], mixed[1], unchecked[1]}) == 3


async def test_checking_a_child_repaints_its_expanded_parent() -> None:
    """`Tree` caches a rendered line until its node says otherwise, and the
    parent's state changed without anything happening to the parent."""
    app = Harness(NESTED)
    async with app.run_test(size=(40, 24)) as pilot:
        _, overlay = await opened(pilot)
        await pilot.press("right")
        await settle(pilot)
        assert button(overlay, 0)[0] == Checkbox.BUTTON_INNER

        await pilot.press("down", "space")
        await settle(pilot)
        assert button(overlay, 0)[0] == "-"


async def test_a_group_that_becomes_an_option_repaints() -> None:
    """Nothing is added to the tree, so `Tree` has no reason of its own to drop
    the line it cached. The row itself now counts towards what it displays."""
    app = Harness([("a", "x")])
    async with app.run_test(size=(40, 24)) as pilot:
        tree_select, overlay = await opened(pilot)
        tree_select.set_checked(["a", "x"], False)
        await settle(pilot)
        assert button(overlay, 0)[0] == Checkbox.BUTTON_INNER

        tree_select.add_option(["a"])
        await settle(pilot)
        assert button(overlay, 0)[0] == "-"


async def test_a_mixed_group_toggles_to_all_checked_then_all_unchecked() -> None:
    app = Harness(NESTED)
    async with app.run_test(size=(40, 24)) as pilot:
        tree_select, _ = await opened(pilot)
        tree_select.set_checked(["a", "x"], False)

        await pilot.press("space")
        await settle(pilot)
        assert tree_select.is_checked(["a", "x"]) is True
        assert tree_select.is_checked(["a", "y"]) is True

        await pilot.press("space")
        await settle(pilot)
        assert tree_select.is_checked(["a", "x"]) is False
        assert tree_select.is_checked(["a", "y"]) is False


async def test_a_row_can_be_rechecked_under_an_unchecked_parent() -> None:
    app = Harness(NESTED)
    async with app.run_test(size=(40, 24)) as pilot:
        tree_select, overlay = await opened(pilot)
        tree_select.set_checked(["a"], False)
        tree_select.set_checked(["a", "x"], True)
        await settle(pilot)

        assert tree_select.is_checked(["a", "x"]) is True
        assert tree_select.is_checked(["a", "y"]) is False
        assert "-" in rows(overlay)[0]
