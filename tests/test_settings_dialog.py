# SPDX-FileCopyrightText: 2026 René de Hesselle <dehesselle@web.de>
#
# SPDX-License-Identifier: 0BSD

"""The settings dialog: what it lists, what it saves, and what it refuses."""

from __future__ import annotations

import asyncio
import json

import pytest
from rich.cells import cell_len
from textual.app import App
from textual.pilot import Pilot
from textual.widgets import Button, Input, Label, Select, Switch, Tree

from tcoda.dialogs import ConfirmDialog, SettingsDialog
from tcoda.settings import Setting, SettingAction, config


class Harness(App[None]):
    """Pushes the dialog on mount, the way a menu item does."""

    def on_mount(self) -> None:
        self.push_screen(SettingsDialog())


async def settle(pilot: Pilot[None], rounds: int = 3) -> None:
    """The dialog defers its first selection by a refresh and does its
    group switching in a worker, so one pause is not enough."""
    for _ in range(rounds):
        await pilot.pause()
        await asyncio.sleep(0.02)


@pytest.fixture
def declared() -> dict[str, object]:
    """A representative spread: two groups, an int, a bool, and a group that
    only exists as an ancestor of a dotted one."""
    ttl = Setting(
        key="cache_ttl",
        label="cache age",
        description="How long cached data stays fresh.",
        group="Cache",
        default=900,
    )
    pages = Setting(
        key="page_size",
        label="fetch page size",
        description="How many rows one fetch asks for.",
        group="Cache",
        default=1000,
    )
    verbose = Setting(
        key="verbose",
        label="verbose",
        description="Log more.",
        group="Updates.Runner",
        default=False,
    )
    return {"ttl": ttl, "pages": pages, "verbose": verbose}


def _tree_labels(app: App[None]) -> list[str]:
    tree = app.screen.query_one("#settings-tree", Tree)
    return [str(node.label) for node in tree.root.children]


async def test_the_first_group_is_selected_on_open(declared) -> None:
    app = Harness()
    async with app.run_test(size=(100, 40)) as pilot:
        await settle(pilot)
        assert _tree_labels(app) == ["Cache", "Updates"]
        assert app.screen.query_one("#value-cache_ttl", Input).value == "900"


async def test_a_group_lists_its_settings_with_descriptions(declared) -> None:
    app = Harness()
    async with app.run_test(size=(100, 40)) as pilot:
        await settle(pilot)
        content = app.screen.query_one("#settings-content")
        labels = [str(label.render()) for label in content.query(Label)]
        assert any("How long cached data stays fresh." in text for text in labels)
        assert app.screen.query_one("#value-page_size", Input) is not None


async def test_ok_writes_the_edited_value_and_closes(declared) -> None:
    app = Harness()
    async with app.run_test(size=(100, 40)) as pilot:
        await settle(pilot)
        field = app.screen.query_one("#value-cache_ttl", Input)
        field.value = "60"
        await pilot.click("#settings-ok")
        await settle(pilot)
        assert json.loads(config.path.read_text(encoding="utf-8")) == {"cache_ttl": 60}
        assert not isinstance(app.screen, SettingsDialog)


async def test_apply_persists_without_closing(declared) -> None:
    app = Harness()
    async with app.run_test(size=(100, 40)) as pilot:
        await settle(pilot)
        app.screen.query_one("#value-cache_ttl", Input).value = "60"
        await pilot.click("#settings-apply")
        await settle(pilot)
        assert json.loads(config.path.read_text(encoding="utf-8")) == {"cache_ttl": 60}
        assert isinstance(app.screen, SettingsDialog)


async def test_clearing_a_field_resets_it_to_its_default(declared) -> None:
    config.set(declared["ttl"], 60)
    app = Harness()
    async with app.run_test(size=(100, 40)) as pilot:
        await settle(pilot)
        assert app.screen.query_one("#value-cache_ttl", Input).value == "60"
        app.screen.query_one("#value-cache_ttl", Input).value = ""
        await pilot.click("#settings-ok")
        await settle(pilot)
        assert json.loads(config.path.read_text(encoding="utf-8")) == {}


async def test_an_unparsable_value_blocks_ok_and_saves_nothing(declared) -> None:
    app = Harness()
    async with app.run_test(size=(100, 40)) as pilot:
        await settle(pilot)
        app.screen.query_one("#value-cache_ttl", Input).value = "soon"
        await pilot.click("#settings-ok")
        await settle(pilot)
        assert isinstance(app.screen, SettingsDialog)
        assert not config.path.exists()


async def test_leaving_a_group_with_edits_asks_before_discarding(declared) -> None:
    app = Harness()
    async with app.run_test(size=(100, 40)) as pilot:
        await settle(pilot)
        app.screen.query_one("#value-cache_ttl", Input).value = "60"
        tree = app.screen.query_one("#settings-tree", Tree)
        tree.select_node(list(tree.root.children)[1])
        await settle(pilot)
        assert isinstance(app.screen, ConfirmDialog)


async def test_cancelling_without_edits_just_closes(declared) -> None:
    app = Harness()
    async with app.run_test(size=(100, 40)) as pilot:
        await settle(pilot)
        await pilot.click("#settings-cancel")
        await settle(pilot)
        assert not isinstance(app.screen, SettingsDialog)


async def test_cancelling_with_edits_asks_first(declared) -> None:
    app = Harness()
    async with app.run_test(size=(100, 40)) as pilot:
        await settle(pilot)
        app.screen.query_one("#value-cache_ttl", Input).value = "60"
        await pilot.click("#settings-cancel")
        await settle(pilot)
        assert isinstance(app.screen, ConfirmDialog)


async def test_a_boolean_setting_gets_a_switch(declared) -> None:
    app = Harness()
    async with app.run_test(size=(100, 40)) as pilot:
        await settle(pilot)
        tree = app.screen.query_one("#settings-tree", Tree)
        updates = list(tree.root.children)[1]
        tree.select_node(next(iter(updates.children)))
        await settle(pilot)
        assert isinstance(app.screen.query_one("#value-verbose"), Switch)


def _declare_pool_size(default: int = 3) -> Setting[int]:
    return Setting(
        key="pool_size",
        label="pool size",
        description="How many connections.",
        group="Connection",
        default=default,
        choices=(1, 2, 3, 4, 5),
    )


async def test_a_choice_setting_renders_a_select() -> None:
    _declare_pool_size()
    app = Harness()
    async with app.run_test(size=(100, 40)) as pilot:
        await settle(pilot)
        select = app.screen.query_one("#value-pool_size", Select)
        assert select.value == 3


async def test_selecting_a_choice_and_clicking_ok_persists_it() -> None:
    setting = _declare_pool_size()
    app = Harness()
    async with app.run_test(size=(100, 40)) as pilot:
        await settle(pilot)
        app.screen.query_one("#value-pool_size", Select).value = 5
        await pilot.click("#settings-ok")
        await settle(pilot)
        assert json.loads(config.path.read_text(encoding="utf-8")) == {"pool_size": 5}
        assert config.get(setting) == 5


async def test_a_stored_value_outside_choices_is_still_shown() -> None:
    """A hand-edited settings.json, or an old default no longer offered,
    must not crash the dialog -- Select requires its initial value to be one
    of its options, so an out-of-range value is added as an extra one."""
    setting = _declare_pool_size()
    config.set(setting, 9)
    app = Harness()
    async with app.run_test(size=(100, 40)) as pilot:
        await settle(pilot)
        select = app.screen.query_one("#value-pool_size", Select)
        assert select.value == 9


async def test_an_ancestor_group_says_it_has_nothing_of_its_own(declared) -> None:
    app = Harness()
    async with app.run_test(size=(100, 40)) as pilot:
        await settle(pilot)
        tree = app.screen.query_one("#settings-tree", Tree)
        tree.select_node(list(tree.root.children)[1])  # "Updates"
        await settle(pilot)
        assert app.screen.query_one(".settings-empty") is not None


# ------------------------------------------------------------------ actions


async def test_an_action_renders_a_button_that_fires_immediately() -> None:
    fired: list[int] = []
    SettingAction(
        key="clear",
        label="clear state",
        description="Forget everything.",
        group="Cache",
        button_label="Clear",
        callback=lambda: fired.append(1),
    )
    app = Harness()
    async with app.run_test(size=(100, 40)) as pilot:
        await settle(pilot)
        assert isinstance(app.screen.query_one("#value-clear"), Button)
        await pilot.click("#value-clear")
        await settle(pilot)
        assert fired == [1]
        # It has no value, so it neither closes the dialog nor dirties it.
        assert isinstance(app.screen, SettingsDialog)


# ----------------------------------------------------------------- instance


def _declare_instance_setting() -> Setting[str]:
    return Setting(
        key="runners",
        label="runner ids",
        description="Which runners to seed from.",
        group="Instance",
        default="",
        per_instance=True,
    )


async def test_an_instance_setting_is_hidden_with_no_instance_active() -> None:
    Setting(key="ttl", label="ttl", description="", group="Cache", default=900)
    _declare_instance_setting()
    app = Harness()
    async with app.run_test(size=(100, 40)) as pilot:
        await settle(pilot)
        # The whole group goes with it -- it had nothing else in it.
        assert _tree_labels(app) == ["Cache"]


async def test_an_instance_setting_appears_once_an_instance_is_active() -> None:
    Setting(key="ttl", label="ttl", description="", group="Cache", default=900)
    setting = _declare_instance_setting()
    config.current_instance = "host.a"
    app = Harness()
    async with app.run_test(size=(100, 40)) as pilot:
        await settle(pilot)
        assert _tree_labels(app) == ["Cache", "Instance"]
        tree = app.screen.query_one("#settings-tree", Tree)
        tree.select_node(list(tree.root.children)[1])
        await settle(pilot)
        app.screen.query_one("#value-runners", Input).value = "1,2"
        await pilot.click("#settings-ok")
        await settle(pilot)
        assert json.loads(config.path.read_text(encoding="utf-8")) == {
            "instances": {"host.a": {"runners": "1,2"}}
        }
        assert config.get(setting) == "1,2"


# ------------------------------------------------------------------ markers


async def test_a_per_instance_row_is_marked_and_a_global_one_is_padded() -> None:
    """The mark says "this value differs per instance"; the blank keeps the
    two kinds of row aligned with each other."""
    Setting(key="ttl", label="ttl", description="", group="G", default=900)
    Setting(
        key="runners",
        label="runner ids",
        description="",
        group="G",
        default="",
        per_instance=True,
    )
    config.current_instance = "host.a"
    app = Harness()
    async with app.run_test(size=(100, 40)) as pilot:
        await settle(pilot)
        rendered = [
            str(label.render()) for label in app.screen.query("#settings-content Label")
        ]
        marked = next(t for t in rendered if t.strip() == "◐ runner ids")
        plain = next(t for t in rendered if t.strip() == "ttl")
        assert marked.startswith("◐ ")
        # Same indent either way, which is the whole point of the blank.
        assert cell_len(marked) - cell_len("runner ids") == cell_len(plain) - cell_len(
            "ttl"
        )


async def test_the_marker_can_be_restyled_by_the_app() -> None:
    """tcoda owns *that* there is a marker; the app owns what it looks like."""

    class Restyled(SettingsDialog):
        INSTANCE_GLYPH = "*"
        INSTANCE_STYLE = "bold magenta"

    class RestyledHarness(App[None]):
        def on_mount(self) -> None:
            self.push_screen(Restyled())

    Setting(
        key="runners",
        label="runner ids",
        description="",
        group="G",
        default="",
        per_instance=True,
    )
    config.current_instance = "host.a"
    app = RestyledHarness()
    async with app.run_test(size=(100, 40)) as pilot:
        await settle(pilot)
        rendered = [
            str(label.render()) for label in app.screen.query("#settings-content Label")
        ]
        assert any(text.startswith("* runner ids") for text in rendered)
