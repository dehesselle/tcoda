# SPDX-FileCopyrightText: 2026 René de Hesselle <dehesselle@web.de>
#
# SPDX-License-Identifier: 0BSD

"""The footer: pinned keys, then whatever else is active, then app status.

Textual's own `Footer` renders `screen.active_bindings` in focus-chain order,
so every key shifts whenever focus moves, and there is nowhere to put anything
that is not a key. This one splits the row into three areas::

    with Footer(pinned=(OPEN_ACTION, "ctrl+q"), sort=True):
        yield Countdown(id="footer-countdown")

* **pinned** -- the keys named in `pinned=`, leftmost, in that order, whatever
  the focus chain says.
* the rest -- every other active binding, in Textual's own order unless
  `sort=` says otherwise.
* **status** -- whatever was yielded into the footer, plus a text label
  reached as `footer.status.update("Online")`. In a `ChordMixin` app it also
  shows a chord that is waiting for its next step.

A pinned binding renders even when it was declared `show=False`: naming a key
in `pinned=` is an explicit request to show it, which outranks a default its
author chose for a footer that had no pinned area. That is what puts Textual's
own `ctrl+q` Quit -- `show=False` in `App.BINDINGS` -- into the left corner.

Only the key areas are rebuilt when bindings change. Status widgets are
composed once and never touched, so they keep their own state: yield a
`Countdown`, keep the reference, and set `remaining` on it. There is no status
channel here, and none is needed.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Sequence
from contextlib import suppress
from dataclasses import dataclass, field, replace
from itertools import groupby
from typing import TYPE_CHECKING, Any, ClassVar

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import HorizontalGroup, HorizontalScroll
from textual.dom import DOMNode, NoScreen
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label, Static

from tcoda.chords import ChordMixin, Steps

if TYPE_CHECKING:
    from textual.screen import Screen
    from textual.visual import VisualType


@dataclass(frozen=True)
class FooterEntry:
    """One binding, as the footer will render it."""

    key: str
    key_display: str
    description: str
    action: str
    enabled: bool
    tooltip: str
    # Excluded from equality so the rebuild diff compares what is *rendered*:
    # a fresh Binding object for an otherwise unchanged key is no reason to
    # tear the row down and build it again.
    binding: Binding = field(compare=False, repr=False)
    node: DOMNode = field(compare=False, repr=False)


#: A `sort=` callable: anything that turns an entry into a sort key.
type SortKey = Callable[[FooterEntry], object]

_DIGITS = re.compile(r"(\d+)")


def natural_key(text: str) -> object:
    """Natural order on text, so `f2` sorts before `f10`.

    Plain string order would not: it compares "10" against "2" a character at
    a time. Digit runs are compared as numbers here, everything else as text.
    """
    return tuple(
        (1, int(part), "") if part.isdigit() else (0, 0, part)
        for part in _DIGITS.split(text.lower())
        if part
    )


def sort_by_key(entry: FooterEntry) -> object:
    """Natural order on the displayed key -- see `natural_key`."""
    return natural_key(entry.key_display)


def _occupied(area: Widget) -> bool:
    """Is this area showing anything at all?"""
    return any(child.display for child in area.children)


def _tokens(pinned: str | Sequence[str]) -> tuple[str, ...]:
    """Normalise `pinned=` to a tuple of tokens.

    A bare string is *one* token, not a sequence of characters. Without this,
    `tuple("ctrl+q")` is `("c", "t", "r", "l", "+", "q")` -- which pins nothing
    that was asked for and may well pin a single-character binding that wasn't.
    A `str` is a `Sequence[str]`, so no type checker objects either, and the
    usual way in is a tuple that lost its trailing comma: `pinned=(OPEN_ACTION)`.
    """
    return (pinned,) if isinstance(pinned, str) else tuple(pinned)


class FooterBinding(Widget):
    """One binding as it appears in the footer: its key, then its description.

    Deliberately not named `FooterKey`. Textual scopes a widget's default CSS
    behind a type selector, so in an app that also mounts a stock `Footer`,
    its `Footer FooterKey.-command-palette { dock: right }` would match a
    child of ours exactly, with registration order as the tie-break.
    """

    ALLOW_SELECT = False

    COMPONENT_CLASSES: ClassVar[set[str]] = {
        "footer-binding--key",
        "footer-binding--description",
    }

    DEFAULT_CSS = """
    FooterBinding {
        width: auto;
        height: 1;
        text-wrap: nowrap;
        background: $footer-item-background;
    }
    FooterBinding .footer-binding--key {
        color: $footer-key-foreground;
        background: $footer-key-background;
        text-style: bold;
        padding: 0 1;
    }
    FooterBinding .footer-binding--description {
        color: $footer-description-foreground;
        background: $footer-description-background;
        padding: 0 1 0 0;
    }
    FooterBinding:hover {
        pointer: pointer;
        color: $footer-key-foreground;
        background: $block-hover-background;
    }
    FooterBinding.-disabled {
        text-style: dim;
    }
    FooterBinding.-compact .footer-binding--key {
        padding: 0;
    }
    FooterBinding.-compact .footer-binding--description {
        padding: 0 0 0 1;
    }
    """

    compact: reactive[bool] = reactive(False)

    def __init__(self, entry: FooterEntry) -> None:
        """
        Args:
            entry: The binding to render.
        """
        self.key = entry.key
        self.key_display = entry.key_display
        self.description = entry.description
        self.action = entry.action
        self._enabled = entry.enabled
        super().__init__(classes="" if entry.enabled else "-disabled")
        # Never shrink a key to fit: a footer showing "^Q Qui" is worse than
        # one that scrolls.
        self.set_reactive(Widget.shrink, False)
        if entry.tooltip:
            self.tooltip = entry.tooltip

    def render(self) -> Text:
        key_style = self.get_component_rich_style("footer-binding--key")
        text_style = self.get_component_rich_style("footer-binding--description")
        # The component classes style spans of this widget's own render rather
        # than child widgets, so the layout engine never sees their padding --
        # it has to be materialised as literal spaces. Textual's own FooterKey
        # does the same.
        key_pad = self.get_component_styles("footer-binding--key").padding
        text_pad = self.get_component_styles("footer-binding--description").padding

        if not self.description:
            return self._styled(Text.assemble((self.key_display, key_style)))
        key = f"{' ' * key_pad.left}{self.key_display}{' ' * key_pad.right}"
        description = f"{' ' * text_pad.left}{self.description}{' ' * text_pad.right}"
        return self._styled(Text.assemble((key, key_style), (description, text_style)))

    def _styled(self, label: Text) -> Text:
        label.stylize_before(self.rich_style)
        return label

    def on_mouse_down(self) -> None:
        if self._enabled:
            self.app.simulate_key(self.key)
        else:
            self.app.bell()

    def watch_compact(self, compact: bool) -> None:
        self.set_class(compact, "-compact")


class FooterGroup(HorizontalGroup):
    """Bindings that share a `Binding.Group`: a `FooterBinding` per key, with
    no description of its own, then the group's description once after them.

    Textual's own footer does the same with its `KeyGroup`; the name differs
    for the reason `FooterBinding`'s does.
    """

    DEFAULT_CSS = """
    FooterGroup {
        width: auto;
    }
    """


class FooterGroupLabel(Label):
    """The description after a group's keys, as Textual's `FooterLabel`."""


class FooterStatus(HorizontalGroup):
    """The footer's status corner: the app's own widgets, plus a text label."""

    def compose(self) -> ComposeResult:
        # Pending children -- whatever the app yielded into the Footer -- are
        # mounted before anything compose() yields, so this label always lands
        # rightmost. They start hidden, so an unused status area takes up no
        # width and earns no divider. The chord hint has a label of its own so
        # that it never clobbers -- or is clobbered by -- the app's text.
        for label in (Static(id="footer-chord"), Static(id="footer-status-text")):
            label.display = False
            yield label

    def update(self, renderable: VisualType = "") -> None:
        """Set the status text, mirroring `header.right.update(...)`.

        Additive: widgets the app yielded into the area are left alone.
        """
        label = self.query_one("#footer-status-text", Static)
        label.update(renderable)
        # An empty label still occupies its padding, which would leave a gap --
        # and a divider -- with nothing in it.
        label.display = bool(renderable)

    def _show_chord(self, text: str) -> None:
        label = self.query_one("#footer-chord", Static)
        label.update(text)
        label.display = bool(text)

    def on_resize(self) -> None:
        # An app hiding its own status widget (`countdown.display = False`) is
        # not something the footer can be told about directly, but it always
        # resizes this `width: auto` area -- signal enough to re-decide whether
        # the rule on our left edge still has anything to divide.
        parent = self.parent
        if isinstance(parent, Footer):
            parent._sync_dividers()


class _FooterKeys(HorizontalScroll, can_focus=False, can_focus_children=False):
    """The scrolling middle of the footer.

    Scrolling the *keys* rather than the whole bar is what lets the pinned
    keys and the status stay put while a crowded run of keys moves.
    """

    def _on_mouse_scroll_down(self, event: Any) -> None:
        # Vertical overflow is hidden here, so without this the wheel does
        # nothing at all over the footer.
        if self.allow_horizontal_scroll:
            self.release_anchor()
            if self._scroll_right_for_pointer(animate=True):
                event.stop()
                event.prevent_default()

    def _on_mouse_scroll_up(self, event: Any) -> None:
        if self.allow_horizontal_scroll:
            self.release_anchor()
            if self._scroll_left_for_pointer(animate=True):
                event.stop()
                event.prevent_default()


class Footer(Widget, can_focus=False, can_focus_children=False):
    """A single-line footer, docked to the bottom of its screen."""

    DEFAULT_CSS = """
    Footer {
        dock: bottom;
        width: 100%;
        height: 1;
        layout: horizontal;
        color: $footer-foreground;
        background: $footer-background;
        /* One row, never scrolled. Without this a child mis-sized by an app
           stylesheet draws a scrollbar across the bar instead of just looking
           slightly wrong. */
        overflow: hidden hidden;
    }
    Footer > #footer-pinned {
        width: auto;
        height: 1;
        layout: horizontal;
        overflow: hidden hidden;
    }
    Footer > #footer-keys {
        /* 1fr is what pushes the status area flush right -- no spacer widget,
           and no `dock: right`, which would stack the status on top of
           anything else docked to that edge rather than beside it (Textual
           takes the max width of same-edge docks, not the sum). */
        width: 1fr;
        height: 1;
        scrollbar-size: 0 0;
    }
    Footer > #footer-status {
        width: auto;
        height: 1;
        layout: horizontal;
        overflow: hidden hidden;
    }
    /* Textual's own separator, moved off the command-palette key and onto
       whichever area has something showing to its left. A left-only border
       costs one column and no rows, which is what makes it usable here. */
    Footer > .-divider {
        border-left: vkey $foreground 20%;
    }
    /* Groups, spaced as Textual's own footer spaces them: a cell either
       side of each key, none between the keys of a compact group. */
    Footer FooterBinding.-grouped {
        margin: 0 1;
    }
    Footer FooterGroup.-compact {
        margin: 0 1 0 0;
        padding-left: 1;
        & > FooterBinding.-grouped {
            margin: 0;
        }
    }
    Footer FooterGroupLabel {
        margin: 0 1 0 0;
        color: $footer-description-foreground;
        background: $footer-description-background;
    }
    Footer.-compact FooterGroupLabel {
        margin: 0;
    }
    Footer > #footer-status > * {
        width: auto;
        height: 1;
        padding: 0 1;
        color: $footer-description-foreground;
        background: $footer-description-background;
    }
    """

    compact: reactive[bool] = reactive(False, toggle_class="-compact")

    #: Bindings to render leftmost, in this order -- see `__init__`.
    pinned: reactive[tuple[str, ...]] = reactive(())

    def __init__(
        self,
        *children: Widget,
        pinned: str | Sequence[str] = (),
        sort: bool | SortKey = False,
        compact: bool = False,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        """
        Args:
            *children: Status widgets, the same as `with Footer(): yield ...`.
            pinned: Bindings to render leftmost, in this order, whatever the
                focus chain says. Each entry matches a binding's `id`, then
                its `action`, then its key -- so `pinned=(OPEN_ACTION,
                "ctrl+q")` works without the caller knowing which kind of name
                it has. A bare string is one token, so `pinned=OPEN_ACTION` and
                `pinned=(OPEN_ACTION,)` mean the same thing. A pinned binding
                renders even if it was declared `show=False`.
            sort: Order the keys that are not pinned. False keeps Textual's
                focus-chain order, True sorts by `sort_by_key`, and a callable
                is a sort key over `FooterEntry`. Pins are never sorted --
                `pinned` already states their order.
            compact: Less whitespace per key.
            name: The widget's name.
            id: DOM id.
            classes: CSS classes.
            disabled: Whether the widget starts out disabled.
        """
        super().__init__(
            *children, name=name, id=id, classes=classes, disabled=disabled
        )
        self._pin_cache: dict[str, FooterEntry] = {}
        self._rendered: (
            tuple[tuple[FooterEntry, ...], tuple[FooterEntry, ...]] | None
        ) = None
        self._sort: SortKey | None = None
        self.sort = sort
        # set_reactive deliberately bypasses validators, so normalise here too.
        self.set_reactive(Footer.pinned, _tokens(pinned))
        self.set_reactive(Footer.compact, compact)
        self.set_class(compact, "-compact", update=False)

    # No compose(): children arrive through the `with Footer():` protocol, and
    # Textual mounts those before anything compose() yields.
    def _extend_compose(self, widgets: list[Widget]) -> None:
        # Whatever the caller yielded arrives here as this widget's pending
        # children. Handing that same list on as the status area's pending
        # children re-homes them in a single mount pass, so the app keeps its
        # references and nothing is built twice.
        widgets[:] = [
            HorizontalGroup(id="footer-pinned"),
            _FooterKeys(id="footer-keys"),
            FooterStatus(*widgets, id="footer-status"),
        ]

    @property
    def sort(self) -> SortKey | None:
        """The active sort key, or None for Textual's focus-chain order."""
        return self._sort

    @sort.setter
    def sort(self, sort: bool | SortKey | None) -> None:
        # Not a reactive: Reactive treats a callable default as a *factory*, so
        # a reactive holding a function is a trap.
        if sort is True:
            self._sort = sort_by_key
        elif not sort:
            self._sort = None
        else:
            self._sort = sort
        self._invalidate()

    @property
    def status(self) -> FooterStatus:
        """The status corner. `footer.status.update(text)`, or mount widgets."""
        return self.query_one("#footer-status", FooterStatus)

    @property
    def _pinned_area(self) -> HorizontalGroup:
        return self.query_one("#footer-pinned", HorizontalGroup)

    @property
    def _keys_area(self) -> _FooterKeys:
        return self.query_one("#footer-keys", _FooterKeys)

    # ----------------------------------------------------------- refreshing

    async def on_mount(self) -> None:
        # Compose is dispatched before Mount, and mounting composed widgets
        # awaits the children's own mount, so every area -- and every status
        # widget the app yielded -- exists by now. That is why the first build
        # happens here, with no "bindings ready" reactive of the kind the stock
        # footer needs.
        self.screen.bindings_updated_signal.subscribe(self, self._bindings_changed)
        if isinstance(self.app, ChordMixin):
            self.watch(self.app, "pending_chord", self._chord_changed)
        await self._rebuild()

    def on_unmount(self) -> None:
        # Teardown can take the screen out from under us first.
        with suppress(NoScreen):
            self.screen.bindings_updated_signal.unsubscribe(self)

    async def _bindings_changed(self, screen: Screen) -> None:
        # No `call_after_refresh`: Signal delivers through `node.call_next`, so
        # this already arrives on our own message queue, one at a time and in
        # order, which is the serialisation `call_after_refresh` was buying.
        #
        # No `app_focus` gate either, unlike the stock footer: on Windows
        # Terminal that flag can lag reality by tens of seconds, leaving the
        # footer stale long after the bindings themselves changed.
        if self.is_attached and screen is self.screen:
            await self._rebuild()

    def _chord_changed(self, steps: Steps) -> None:
        app = self.app
        assert isinstance(app, ChordMixin)
        text = (
            f"({app.get_chord_display(steps)}) waiting for next key…" if steps else ""
        )
        self.status._show_chord(text)

    def validate_pinned(self, pinned: str | Sequence[str]) -> tuple[str, ...]:
        return _tokens(pinned)

    def watch_pinned(self) -> None:
        self._invalidate()

    def _invalidate(self) -> None:
        """Force the next rebuild to redraw, and schedule one."""
        self._rendered = None
        if self.is_running:
            self.call_next(self._rebuild)

    async def _rebuild(self) -> None:
        if not self.is_mounted:
            return
        pinned, dynamic = self._collect()
        if (pinned, dynamic) == self._rendered:
            # `refresh_bindings` fires on every focus move, screen-stack change
            # and `bindings=True` reactive -- far more often than the rendered
            # keys actually change. Comparing first is what keeps the footer
            # from rebuilding, and visibly flickering, on every arrow key.
            return
        self._rendered = (pinned, dynamic)
        # batch() takes the widget lock and holds the screen update, so the
        # emptied intermediate state is never painted.
        async with self.batch():
            await self._pinned_area.remove_children()
            await self._keys_area.remove_children()
            await self._pinned_area.mount_all(self._render_keys(pinned))
            # Pins are named one binding at a time, so only the rest group.
            await self._keys_area.mount_all(self._render_keys(dynamic, grouped=True))
        self._sync_dividers()

    def _render_keys(
        self, entries: Iterable[FooterEntry], *, grouped: bool = False
    ) -> list[Widget]:
        """A `FooterBinding` per entry; with `grouped`, neighbours that share a
        `Binding.Group` become a `FooterGroup` instead, as in Textual's footer.
        A group of one is just its binding, under its own description."""
        widgets: list[Widget] = []
        for group, members in groupby(
            entries, key=lambda entry: entry.binding.group if grouped else None
        ):
            run = list(members)
            if group is None or len(run) == 1:
                widgets.extend(self._render_key(entry) for entry in run)
                continue
            keys = []
            for entry in run:
                # The key alone; its own description is what hovering shows.
                key = self._render_key(
                    replace(
                        entry,
                        description="",
                        tooltip=entry.tooltip or entry.description,
                    )
                )
                key.add_class("-grouped")
                keys.append(key)
            widgets.append(
                FooterGroup(*keys, classes="-compact" if group.compact else "")
            )
            widgets.append(FooterGroupLabel(group.description))
        return widgets

    def _render_key(self, entry: FooterEntry) -> FooterBinding:
        return FooterBinding(entry).data_bind(compact=Footer.compact)

    def _sync_dividers(self) -> None:
        # "Draw a rule on my left edge if anything is already showing to my
        # left" -- so an empty area never strands one, which is why the keys
        # area (1fr, and always present) cannot simply carry a static border.
        anything_yet = False
        for area in self.children:
            occupied = _occupied(area)
            area.set_class(occupied and anything_yet, "-divider")
            anything_yet = anything_yet or occupied

    # ------------------------------------------------------------ collecting

    def _pin_token(self, binding: Binding, key: str) -> str | None:
        """Which `pinned=` entry, if any, names this binding."""
        for candidate in (binding.id, binding.action, key):
            if candidate is not None and candidate in self.pinned:
                return candidate
        return None

    def _collect(self) -> tuple[tuple[FooterEntry, ...], tuple[FooterEntry, ...]]:
        """The pinned and the unpinned entries, each in render order."""
        pins: dict[str, FooterEntry] = {}
        dynamic: list[FooterEntry] = []
        seen_actions: set[str] = set()

        # Ordered by focus-chain depth: the focused widget's own bindings
        # first, the app's last. Three wrinkles worth knowing: with nothing
        # focused the chain is just [screen, app] rather than an ancestor walk;
        # a modal screen truncates it; and a key that a more-focused Input or
        # TextArea would swallow is dropped from it entirely.
        for key, active in self.screen.active_bindings.items():
            binding = active.binding
            token = self._pin_token(binding, key)
            # `show` is the author's default for a footer with no pinned area;
            # naming the key in `pinned=` overrides it. A binding with no
            # description has nothing to render either way -- and Textual
            # forces `show=False` on those regardless.
            if not binding.description or (token is None and not binding.show):
                continue
            if binding.action in seen_actions:
                # Stock's de-dup: several keys on one action show as the first.
                continue
            seen_actions.add(binding.action)
            entry = FooterEntry(
                key=key,
                key_display=self.app.get_key_display(binding),
                description=binding.description,
                action=binding.action,
                enabled=active.enabled,
                tooltip=active.tooltip,
                binding=binding,
                node=active.node,
            )
            if token is None:
                dynamic.append(entry)
            else:
                pins.setdefault(token, entry)
                self._pin_cache[token] = entry

        if self._sort is not None:
            dynamic.sort(key=self._sort)

        ordered: list[FooterEntry] = []
        for token in self.pinned:
            entry = pins.get(token)
            if entry is None:
                # Not active right now. Re-render the last one seen, dimmed:
                # letting it vanish would shift every pin after it, which is
                # the movement pinning exists to stop. A pin that has never
                # been active has no description yet, so it renders nothing.
                cached = self._pin_cache.get(token)
                entry = None if cached is None else replace(cached, enabled=False)
            if entry is not None:
                ordered.append(entry)
        return tuple(ordered), tuple(dynamic)
