"""The settings dialog: a tree of groups on the left, the selected group's
editable entries on the right.

Enumerates whatever has been declared -- see `tcw.settings` -- so adding a
setting needs no wiring here at all.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, ClassVar

from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Input, Label, Rule, Select, Switch, Tree
from textual.widgets.tree import TreeNode

from tcw._text import marker_text
from tcw.screens._confirm import ConfirmScreen
from tcw.screens._dialog import DialogScreen
from tcw.settings import Setting, SettingAction, SettingsEntry, all_settings, config

ValueWidget = Input | Switch | Select | Button


def _group_paths(entries: list[SettingsEntry]) -> set[str]:
    """Every group path that must exist as a tree node: each group itself,
    plus every ancestor prefix it implies -- so a dot-separated group like
    "Updates.Runner" still produces an "Updates" node to hang it off, even
    with no entries directly assigned to "Updates"."""
    paths: set[str] = set()
    for entry in entries:
        segments = entry.group.split(".")
        for i in range(1, len(segments) + 1):
            paths.add(".".join(segments[:i]))
    return paths


class SettingsScreen(DialogScreen[None]):
    """Tree of setting groups on the left, the selected group's editable
    entries on the right. Edits to the visible group are unsaved until
    Apply/OK; navigating to a different group with unsaved edits confirms
    before discarding them.
    """

    DEFAULT_CSS = """
    SettingsScreen > #dialog { width: 90%; height: 80%; }

    SettingsScreen #settings-body { height: 1fr; }

    SettingsScreen #settings-tree {
        width: 1fr;
        border-right: solid $panel;
        padding: 0 1;
    }

    SettingsScreen #settings-content { width: 3fr; padding: 1 2; }

    SettingsScreen #settings-placeholder,
    SettingsScreen .settings-empty { color: $text-muted; }

    SettingsScreen .settings-item { height: auto; }

    SettingsScreen .settings-item-description { width: 1fr; margin-bottom: 1; }

    /* Separates entries; its own default margin (1 0) is the only spacing
       between one entry and the next. */
    SettingsScreen #settings-content Rule { color: $panel; }

    SettingsScreen .settings-item-field { height: auto; }

    /* Input/Switch are both 3 cells tall (bordered), so the label's top
       margin lines it up with their middle row. A compact Button is 1 cell
       tall, so it needs the same margin to sit on that row too. */
    SettingsScreen .settings-item-field Label { width: auto; margin: 1 1 0 0; }
    SettingsScreen .settings-item-field Input { width: 1fr; }
    SettingsScreen .settings-item-field Button { margin: 1 0 0 0; }
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    #: Marks a row whose value is scoped to `ConfigStore.current_instance`
    #: rather than stored globally. That such rows are marked at all is the
    #: library's business -- the value really does differ elsewhere, and the
    #: reader has to be able to tell. What the mark looks like is the app's,
    #: so both of these are here to be overridden in a subclass.
    INSTANCE_GLYPH: ClassVar[str] = "◐"
    #: A Rich style for that glyph, or None for the running theme's accent --
    #: the same highlight the menu bar gives a mnemonic.
    INSTANCE_STYLE: ClassVar[str | None] = None

    def __init__(self) -> None:
        super().__init__()
        self._current_node: TreeNode[str] | None = None
        self._current_group: str | None = None
        #: {setting.key: config.get(setting)} as of when the current group's
        #: entries were last (re)rendered or applied -- what "dirty" compares
        #: against. Actions have no value and never appear here.
        self._baseline: dict[str, Any] = {}

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label("Settings", id="title")
            with Horizontal(id="settings-body"):
                yield Tree("Settings", id="settings-tree")
                with VerticalScroll(id="settings-content"):
                    yield Label("Select a settings group.", id="settings-placeholder")
            with Horizontal(id="buttons"):
                yield Button("Apply", compact=True, id="settings-apply")
                yield Button("OK", variant="primary", compact=True, id="settings-ok")
                yield Button("Cancel", compact=True, id="settings-cancel")

    def on_mount(self) -> None:
        tree = self.query_one("#settings-tree", Tree)
        tree.show_root = False
        self._build_tree(tree)
        tree.focus()
        first = next(iter(tree.root.children), None)
        if first is not None:
            # A just-built node's _line is still -1 until the next refresh, so
            # selecting immediately would silently land on line 0 instead.
            self.call_after_refresh(tree.select_node, first)

    # --------------------------------------------------------------- entries

    def _visible_entries(self) -> list[SettingsEntry]:
        """Everything the current context can show: every global entry, plus
        instance-scoped ones only once an instance is active -- otherwise
        there is no instance to read or write their values under."""
        return [
            entry
            for entry in all_settings()
            if not entry.per_instance or config.current_instance is not None
        ]

    def _entries_for(self, group: str) -> list[SettingsEntry]:
        return [entry for entry in self._visible_entries() if entry.group == group]

    def _build_tree(self, tree: Tree[str]) -> None:
        paths = _group_paths(self._visible_entries())
        children_of: dict[str, list[str]] = defaultdict(list)
        for path in paths:
            parent = path.rsplit(".", 1)[0] if "." in path else ""
            children_of[parent].append(path)
        for kids in children_of.values():
            kids.sort(key=lambda p: p.rsplit(".", 1)[-1])

        def add_children(parent_node: TreeNode[str], parent_path: str) -> None:
            for path in children_of.get(parent_path, []):
                label = path.rsplit(".", 1)[-1]  # verbatim, no case change
                node = parent_node.add(label, data=path, expand=True)
                add_children(node, path)

        add_children(tree.root, "")

    # --------------------------------------------------------------- widgets

    def _marker(self, entry: SettingsEntry) -> Text:
        style = self.INSTANCE_STYLE or self.app.theme_variables["accent"]
        return marker_text(self.INSTANCE_GLYPH, style, present=entry.per_instance)

    def _widget_for(self, entry: SettingsEntry) -> ValueWidget:
        widget = self.query_one(f"#value-{entry.key}")
        assert isinstance(widget, Input | Switch | Select | Button)
        return widget

    def _make_value_widget(self, entry: SettingsEntry) -> ValueWidget:
        if isinstance(entry, SettingAction):
            return Button(entry.button_label, compact=True, id=f"value-{entry.key}")
        if isinstance(entry.default, bool):
            return Switch(value=config.get(entry), id=f"value-{entry.key}")
        if entry.choices is not None:
            current = config.get(entry)
            # Select requires its initial value to be one of the options --
            # a hand-edited settings.json, or an old default no longer
            # offered, must not crash the dialog, so it's shown as an extra
            # trailing choice rather than dropped.
            values = list(entry.choices)
            if current not in values:
                values.append(current)
            return Select(
                [(entry.format(v), v) for v in values],
                value=current,
                allow_blank=False,
                id=f"value-{entry.key}",
            )
        return Input(
            value=entry.format(config.get(entry)),
            placeholder=entry.format(entry.default),
            id=f"value-{entry.key}",
        )

    async def _render_group(self, group: str) -> None:
        content = self.query_one("#settings-content", VerticalScroll)
        await content.remove_children()
        entries = self._entries_for(group)
        if not entries:
            # An ancestor node implied by a dotted group (e.g. "Updates" for
            # "Updates.Runner") has no entries of its own directly on it.
            await content.mount(
                Label("No settings in this group.", classes="settings-empty")
            )
            return
        for i, entry in enumerate(entries):
            if i > 0:
                await content.mount(Rule.horizontal())
            item = Vertical(
                Label(entry.description, classes="settings-item-description"),
                Horizontal(
                    Label(Text.assemble(self._marker(entry), " ", entry.label)),
                    self._make_value_widget(entry),
                    classes="settings-item-field",
                ),
                classes="settings-item",
            )
            await content.mount(item)

    async def _select_group(self, node: TreeNode[str]) -> None:
        group = node.data
        assert group is not None
        await self._render_group(group)
        self._current_node = node
        self._current_group = group
        self._baseline = {
            entry.key: config.get(entry)
            for entry in self._entries_for(group)
            if isinstance(entry, Setting)
        }

    # --------------------------------------------------------------- editing

    def _current_value(self, setting: Setting[Any]) -> Any:
        """The value the visible widget currently represents, or raises
        ValueError if typed text does not parse. Empty text means "reset to
        the default", which `ConfigStore.set` turns into a removal."""
        widget = self._widget_for(setting)
        if isinstance(widget, Switch | Select):
            return widget.value
        assert isinstance(widget, Input)
        text = widget.value.strip()
        if not text:
            return setting.default
        return setting.parse(text)

    def _editable(self, group: str) -> list[Setting[Any]]:
        return [e for e in self._entries_for(group) if isinstance(e, Setting)]

    def _is_dirty(self) -> bool:
        if self._current_group is None:
            return False
        for setting in self._editable(self._current_group):
            try:
                current = self._current_value(setting)
            except ValueError:
                # Can't prove it's unchanged; treat unparsed input as dirty
                # rather than silently letting it be discarded.
                return True
            if current != self._baseline[setting.key]:
                return True
        return False

    def _apply(self) -> bool:
        if self._current_group is None:
            return True
        settings = self._editable(self._current_group)
        parsed: dict[str, Any] = {}
        for setting in settings:
            try:
                parsed[setting.key] = self._current_value(setting)
            except ValueError as e:
                self.notify(
                    f"Invalid value for {setting.label}: {e}", severity="warning"
                )
                return False
        for setting in settings:
            config.set(setting, parsed[setting.key])
        self._baseline = parsed
        return True

    def _run_action(self, key: str) -> None:
        if self._current_group is None:
            return
        for entry in self._entries_for(self._current_group):
            if isinstance(entry, SettingAction) and entry.key == key:
                entry.callback()
                return

    # ---------------------------------------------------------------- events

    def on_tree_node_selected(self, event: Tree.NodeSelected[str]) -> None:
        event.stop()
        node = event.node
        if node.data is None or node is self._current_node:
            return
        self._handle_selection(node)

    @work(exclusive=True)
    async def _handle_selection(self, node: TreeNode[str]) -> None:
        # push_screen_wait requires an active worker context (that's what this
        # decorator provides) -- it cannot be awaited from a plain handler.
        if self._is_dirty():
            discard = await self.app.push_screen_wait(
                ConfirmScreen("You are about to lose unsaved changes!")
            )
            if not discard:
                if self._current_node is not None:
                    self.query_one("#settings-tree", Tree).move_cursor(
                        self._current_node
                    )
                return
        await self._select_group(node)

    def on_input_submitted(self) -> None:
        self._apply()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        button_id = event.button.id
        if button_id == "settings-cancel":
            self.action_cancel()
        elif button_id == "settings-apply":
            self._apply()
        elif button_id == "settings-ok":
            if self._apply():
                self.dismiss(None)
        elif button_id is not None and button_id.startswith("value-"):
            # A SettingAction's own button. It fires immediately rather than
            # waiting for Apply: it has no value to save, so there is nothing
            # for Apply to do with it.
            self._run_action(button_id.removeprefix("value-"))

    def action_cancel(self) -> None:
        self._cancel()

    @work(exclusive=True)
    async def _cancel(self) -> None:
        # Same worker-context reason as _handle_selection above.
        if self._is_dirty():
            discard = await self.app.push_screen_wait(
                ConfirmScreen("You are about to lose unsaved changes!")
            )
            if not discard:
                return
        self.dismiss(None)
