# SPDX-FileCopyrightText: 2026 René de Hesselle <dehesselle@web.de>
#
# SPDX-License-Identifier: 0BSD

"""The tabbed content: mnemonics, and the focus following the tab."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.content import Content
from textual.widgets import DataTable, Input
from textual.widgets import TabPane as TextualTabPane
from textual.widgets.tabbed_content import ContentTab, ContentTabs

from tcoda.widgets import TabbedContent, TabPane


class Harness(App[None]):
    def __init__(self, *, input_first: bool = False) -> None:
        super().__init__()
        self.input_first = input_first
        self.activated: list[str] = []

    def compose(self) -> ComposeResult:
        if self.input_first:
            yield Input(id="beside")
        with TabbedContent(initial="tab-columns"):
            with TabPane("Columns", mnemonic="c", id="tab-columns"):
                yield DataTable(id="columns")
            with TabPane("Data", mnemonic="d", id="tab-data"):
                yield DataTable(id="data")
            with TabPane("Grants", mnemonic="g", id="tab-grants", disabled=True):
                yield DataTable(id="grants")
            with TextualTabPane("Plain", id="tab-plain"):
                yield DataTable(id="plain")

    def on_tabbed_content_tab_activated(
        self, event: TabbedContent.TabActivated
    ) -> None:
        self.activated.append(event.pane.id or "")


async def test_the_app_starts_with_the_focus_in_the_pane() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.focused is app.query_one("#columns")


async def test_focus_beside_the_widget_is_left_alone_at_start() -> None:
    app = Harness(input_first=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.focused is app.query_one("#beside")


async def test_a_mnemonic_switches_and_the_next_one_still_works() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        await pilot.pause()
        tabs = app.query_one(TabbedContent)
        await pilot.press("d")
        await pilot.pause()
        assert tabs.active == "tab-data"
        assert app.focused is app.query_one("#data")
        await pilot.press("c")
        await pilot.pause()
        assert tabs.active == "tab-columns"
        assert app.focused is app.query_one("#columns")


async def test_the_apps_own_handler_still_runs() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()
        assert app.activated[-1] == "tab-data"


async def test_a_disabled_tab_ignores_its_mnemonic() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("g")
        await pilot.pause()
        assert app.query_one(TabbedContent).active == "tab-columns"


async def test_a_hidden_tab_ignores_its_mnemonic() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.query_one(TabbedContent).hide_tab("tab-data")
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()
        assert app.query_one(TabbedContent).active == "tab-columns"


async def test_arrow_keys_walk_the_tab_bar_without_losing_it() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        await pilot.pause()
        tabs = app.query_one(TabbedContent)
        app.query_one(ContentTabs).focus()
        await pilot.pause()
        # Grants is disabled, so the bar steps over it.
        for expected in ("tab-data", "tab-plain", "tab-columns"):
            await pilot.press("right")
            await pilot.pause()
            assert tabs.active == expected
            assert isinstance(app.focused, ContentTabs)


async def test_setting_active_takes_the_focus_along() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.query_one(TabbedContent).active = "tab-plain"
        await pilot.pause()
        assert app.focused is app.query_one("#plain")


async def test_focusing_into_a_hidden_pane_is_not_overridden() -> None:
    """Textual switches to a pane when something in it is focused; the focus
    must stay on that widget, not jump to the pane's first one."""

    class TwoWidgets(App[None]):
        def compose(self) -> ComposeResult:
            with TabbedContent():
                with TabPane("One", mnemonic="o", id="tab-one"):
                    yield DataTable()
                with TabPane("Two", mnemonic="t", id="tab-two"):
                    yield DataTable(id="first")
                    yield Input(id="find")

    app = TwoWidgets()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.query_one("#find").focus()
        await pilot.pause()
        assert app.query_one(TabbedContent).active == "tab-two"
        assert app.focused is app.query_one("#find")


async def test_a_widget_that_is_not_displayed_is_not_a_focus_target() -> None:
    """Textual's `focusable` ignores `display`, and focusing such a widget
    drops the focus: a hidden search box must not be picked, nor anything
    inside a hidden container."""

    class Hidden(App[None]):
        def compose(self) -> ComposeResult:
            with TabbedContent():
                with TabPane("One", mnemonic="o", id="tab-one"):
                    yield DataTable(id="first")
                with TabPane("Two", mnemonic="t", id="tab-two"):
                    yield Input(id="search")
                    with Vertical(id="box"):
                        yield Input(id="boxed")
                    yield DataTable(id="table")

        def on_mount(self) -> None:
            self.query_one("#search").display = False
            self.query_one("#box").display = False

    app = Hidden()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("t")
        await pilot.pause()
        assert app.focused is app.query_one("#table")


async def test_focus_target_can_be_overridden() -> None:
    class Second(TabbedContent):
        def focus_target(self, pane):
            return pane.query(DataTable).last()

    class Overridden(App[None]):
        def compose(self) -> ComposeResult:
            with Second(), TabPane("One", mnemonic="o", id="tab-one"):
                yield DataTable(id="first")
                yield DataTable(id="second")

    app = Overridden()
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.focused is app.query_one("#second")


async def test_a_textual_pane_mixes_in_without_a_key() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("p")
        await pilot.pause()
        assert app.query_one(TabbedContent).active == "tab-columns"


async def test_added_and_removed_panes_bind_and_unbind() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        await pilot.pause()
        tabs = app.query_one(TabbedContent)
        await tabs.add_pane(TabPane("Tags", DataTable(id="tags"), mnemonic="t"))
        await pilot.pause()
        await pilot.press("t")
        await pilot.pause()
        assert tabs.active_pane is not None
        assert tabs.active_pane.query_one("#tags")
        assert app.focused is app.query_one("#tags")

        pane_id = tabs.active
        await tabs.remove_pane(pane_id)
        await pilot.pause()
        assert "t" not in tabs._bindings.key_to_bindings
        assert "d" in tabs._bindings.key_to_bindings


async def test_the_mnemonic_letter_is_styled_like_a_footer_key() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        await pilot.pause()
        label = app.query_one("#--content-tab-tab-data", ContentTab).label
        assert isinstance(label, Content)
        assert [(span.start, span.end, span.style) for span in label.spans] == [
            (0, 1, "$accent bold")
        ]


def _spans(tabs: TabbedContent, pane_id: str) -> list[tuple[int, int, str]]:
    label = tabs.get_tab(pane_id).label
    return [(span.start, span.end, str(span.style)) for span in label.spans]


async def test_a_disabled_tab_does_not_color_its_letter() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        await pilot.pause()
        tabs = app.query_one(TabbedContent)
        assert _spans(tabs, "tab-grants") == []
        tabs.enable_tab("tab-grants")
        await pilot.pause()
        assert _spans(tabs, "tab-grants") == [(0, 1, "$accent bold")]
        # Through the pane rather than the tab bar: Textual's other path.
        tabs.get_pane("tab-data").disabled = True
        await pilot.pause()
        assert tabs.get_tab("tab-data").disabled
        assert _spans(tabs, "tab-data") == []
        tabs.get_pane("tab-data").disabled = False
        await pilot.pause()
        assert _spans(tabs, "tab-data") == [(0, 1, "$accent bold")]


def test_the_mnemonic_is_found_anywhere_in_a_markup_title() -> None:
    pane = TabPane("[i]My[/] Diff", mnemonic="D", id="tab-changes")
    assert pane.mnemonic == "d"
    assert (3, 4, "$accent bold") in [
        (span.start, span.end, span.style) for span in pane._title.spans
    ]


async def test_with_auto_focus_off_the_pane_gets_the_focus() -> None:
    class NoAutoFocus(Harness):
        AUTO_FOCUS = None

    app = NoAutoFocus()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.pause()
        assert app.focused is app.query_one("#columns")


async def test_an_auto_focus_aimed_into_a_pane_is_kept() -> None:
    class AimedAutoFocus(App[None]):
        AUTO_FOCUS = "#second"

        def compose(self) -> ComposeResult:
            with TabbedContent(), TabPane("One", mnemonic="o", id="tab-one"):
                yield DataTable(id="first")
                yield DataTable(id="second")

    app = AimedAutoFocus()
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.focused is app.query_one("#second")


async def test_a_tab_changed_from_outside_leaves_the_focus_outside() -> None:
    app = Harness(input_first=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.query_one(TabbedContent).active = "tab-data"
        await pilot.pause()
        assert app.focused is app.query_one("#beside")


async def test_a_letter_takes_the_focus_in_even_from_the_tab_bar() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.query_one(ContentTabs).focus()
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()
        assert app.focused is app.query_one("#data")
        # The letter of the tab already shown, too.
        app.query_one(ContentTabs).focus()
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()
        assert app.focused is app.query_one("#data")


class Loading(App[None]):
    """A second tab whose table is still loading, so nothing in it can take
    the focus yet."""

    def compose(self) -> ComposeResult:
        with TabbedContent():
            with TabPane("One", mnemonic="o", id="tab-one"):
                yield DataTable(id="first")
            with TabPane("Two", mnemonic="t", id="tab-two"):
                yield DataTable(id="second")

    def on_mount(self) -> None:
        self.query_one("#second").loading = True


async def test_with_nothing_to_focus_the_focus_parks_on_the_tab_bar() -> None:
    app = Loading()
    async with app.run_test() as pilot:
        await pilot.pause()
        tabs = app.query_one(TabbedContent)
        await pilot.press("t")
        await pilot.pause()
        assert isinstance(app.focused, ContentTabs)
        # Parked, the letters still work.
        await pilot.press("o")
        await pilot.pause()
        assert tabs.active == "tab-one"
        assert app.focused is app.query_one("#first")


async def test_focus_active_pane_takes_the_focus_in_once_ready() -> None:
    app = Loading()
    async with app.run_test() as pilot:
        await pilot.pause()
        tabs = app.query_one(TabbedContent)
        await pilot.press("t")
        await pilot.pause()
        app.query_one("#second").loading = False
        tabs.focus_active_pane()
        await pilot.pause()
        assert app.focused is app.query_one("#second")


async def test_focus_active_pane_leaves_a_walked_tab_bar_alone() -> None:
    app = Loading()
    async with app.run_test() as pilot:
        await pilot.pause()
        tabs = app.query_one(TabbedContent)
        await pilot.press("t")
        await pilot.pause()
        # Parked on the bar; the user now walks it, and comes back.
        await pilot.press("left")
        await pilot.pause()
        await pilot.press("right")
        await pilot.pause()
        assert tabs.active == "tab-two"
        app.query_one("#second").loading = False
        tabs.focus_active_pane()
        await pilot.pause()
        assert isinstance(app.focused, ContentTabs)


async def test_focus_active_pane_leaves_focus_outside_alone() -> None:
    app = Harness(input_first=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.query_one(TabbedContent).focus_active_pane()
        await pilot.pause()
        assert app.focused is app.query_one("#beside")
