"""A which-key style panel listing what can follow a pending chord.

It appears only once the user hesitates, `delay` seconds into a chord, so
someone typing a chord they know never sees it flash. Once shown it holds the
chord open (`ChordMixin.hold_chord`) until the chord completes or is abandoned,
and `CHORD_BACK_KEY` steps back instead of abandoning it.

The layout follows which-key's own (`view.lua`): as many columns as fit the
widest entry, filled top to bottom and then left to right, with the typed
steps and a key legend on a line of their own below.

Docked to the bottom in a layer of its own, it covers the `Footer` rather than
stacking above it -- Textual arranges docks per layer -- so its bottom line
takes over the footer's "waiting for next key…" hint without either widget
knowing about the other.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from rich.cells import cell_len
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widget import Widget
from textual.widgets import Static

from tcw.chords import ChordMixin, Steps, chord_groups, chord_steps
from tcw.widgets._footer import natural_key
from tcw.widgets._layers import install_layer

if TYPE_CHECKING:
    from rich.style import Style
    from textual.timer import Timer

#: The layer this widget adds to its host screen -- see `tcw.widgets._layers`.
_LAYER = "_tcw_chord_viewer"


@dataclass(frozen=True)
class ChordViewerItem:
    """One possible next step, as the panel renders it."""

    step: str
    key_display: str
    description: str
    enabled: bool
    #: True if the step leads to further chords rather than running one.
    group: bool


def _columns(
    widths: Sequence[int], total_width: int, min_width: int, spacing: int
) -> list[range]:
    """Which items go in which column, laid out the way which-key does it.

    As many columns as fit the widest item (never narrower than `min_width`)
    plus `spacing`, and at least one, filled top to bottom and then left to
    right -- `view.lua`'s `i = (b - 1) * box_height + l`. Columns the items do
    not reach are returned empty rather than dropped: they still take their
    share of the width, which is what keeps a short list from stretching.
    """
    if not widths:
        return []
    box_width = max(max(widths), min_width)
    count = max(total_width // (box_width + spacing), 1)
    height = math.ceil(len(widths) / count)
    total = len(widths)
    return [
        range(min(column * height, total), min((column + 1) * height, total))
        for column in range(count)
    ]


class ChordViewerEntry(Widget):
    """One item in the panel: its key, a separator, then its description.

    Clicking it presses the step, so a group entry descends into its group.
    """

    ALLOW_SELECT = False

    COMPONENT_CLASSES: ClassVar[set[str]] = {
        "chord-viewer-entry--key",
        "chord-viewer-entry--separator",
        "chord-viewer-entry--description",
        "chord-viewer-entry--group",
    }

    DEFAULT_CSS = """
    ChordViewerEntry {
        width: 1fr;
        height: 1;
    }
    ChordViewerEntry .chord-viewer-entry--key {
        color: $footer-key-foreground;
        text-style: bold;
    }
    ChordViewerEntry .chord-viewer-entry--separator {
        color: $text-muted;
    }
    ChordViewerEntry .chord-viewer-entry--description {
        color: $foreground;
    }
    ChordViewerEntry .chord-viewer-entry--group {
        color: $text-accent;
    }
    ChordViewerEntry:hover {
        pointer: pointer;
        background: $block-hover-background;
    }
    ChordViewerEntry.-disabled {
        text-style: dim;
    }
    """

    def __init__(self, item: ChordViewerItem, key_width: int, separator: str) -> None:
        """
        Args:
            item: What to render.
            key_width: The widest key in this entry's column, so the
                separators line up.
            separator: What goes between key and description.
        """
        super().__init__(classes="" if item.enabled else "-disabled")
        self.item = item
        self._key_width = key_width
        self._separator = separator

    def render(self) -> Text:
        item = self.item
        padding = " " * (self._key_width - cell_len(item.key_display))
        description = "group" if item.group else "description"
        label = Text.assemble(
            (f"{padding}{item.key_display}", self._style("key")),
            (f" {self._separator} ", self._style("separator")),
            (item.description, self._style(description)),
            no_wrap=True,
            overflow="ellipsis",
        )
        label.stylize_before(self.rich_style)
        return label

    def _style(self, component: str) -> Style:
        return self.get_component_rich_style(f"chord-viewer-entry--{component}")

    def on_mouse_down(self) -> None:
        if self.item.enabled:
            self.app.simulate_key(self.item.step)
        else:
            self.app.bell()


class ChordViewer(Widget, can_focus=False, can_focus_children=False):
    """Shows what can follow a pending chord, docked to the bottom.

    Needs a `ChordMixin` app. The mixin's `CHORD_TIMEOUT` still applies until
    the panel appears, so a `delay` at or beyond it means it never does.
    """

    #: An item's column is never narrower than this -- which-key's
    #: `layout.width.min`.
    MIN_COLUMN_WIDTH: ClassVar[int] = 20
    #: Room left between columns -- which-key's `layout.spacing`.
    COLUMN_SPACING: ClassVar[int] = 3
    #: Between an item's key and its description.
    SEPARATOR: ClassVar[str] = "➜"
    #: Between the typed steps on the bottom line.
    BREADCRUMB: ClassVar[str] = "»"
    #: In front of an item that leads to further chords.
    GROUP_PREFIX: ClassVar[str] = "+"

    COMPONENT_CLASSES: ClassVar[set[str]] = {
        "chord-viewer--key",
        "chord-viewer--group",
    }

    DEFAULT_CSS = """
    ChordViewer {
        dock: bottom;
        width: 100%;
        height: auto;
        /* Capped here rather than on the columns: an auto height ignores a
           child's max-height and grows to the child's whole content. */
        max-height: 50vh;
        layer: _tcw_chord_viewer;
        background: $panel;
    }
    ChordViewer > #chord-viewer-columns {
        height: auto;
        /* Of what the docked bar leaves. */
        max-height: 100%;
        padding: 1 2;
        scrollbar-size-vertical: 1;
    }
    ChordViewer #chord-viewer-boxes {
        height: auto;
    }
    ChordViewer .chord-viewer-box {
        width: 1fr;
        height: auto;
    }
    ChordViewer > #chord-viewer-bar {
        dock: bottom;
        height: 1;
        padding: 0 2;
    }
    ChordViewer > #chord-viewer-bar > Static {
        text-wrap: nowrap;
        text-overflow: ellipsis;
    }
    /* Equal flexible space either side is what centres the legend. */
    ChordViewer #chord-viewer-trail, ChordViewer #chord-viewer-spacer {
        width: 1fr;
    }
    ChordViewer #chord-viewer-help {
        width: auto;
        color: $text-muted;
    }
    ChordViewer .chord-viewer--key {
        color: $footer-key-foreground;
        text-style: bold;
    }
    ChordViewer .chord-viewer--group {
        color: $text-accent;
    }
    """

    def __init__(self, *, delay: float = 0.2, id: str | None = None) -> None:
        """
        Args:
            delay: Seconds into a chord before the panel appears, if it is
                still pending by then. 0.2 is which-key's default.
            id: DOM id.
        """
        super().__init__(id=id)
        self.delay = delay
        self.display = False
        self._delay_timer: Timer | None = None
        self._rendered: tuple[tuple[ChordViewerItem, ...], int] | None = None

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="chord-viewer-columns"):
            yield Horizontal(id="chord-viewer-boxes")
        with Horizontal(id="chord-viewer-bar"):
            yield Static(id="chord-viewer-trail")
            yield Static(id="chord-viewer-help")
            yield Static(id="chord-viewer-spacer")

    @property
    def _chords(self) -> ChordMixin:
        app = self.app
        assert isinstance(app, ChordMixin)
        return app

    def on_mount(self) -> None:
        # Unlike the footer, which is useful without chords, this has no use
        # at all -- and doing nothing quietly would only hide the mistake.
        if not isinstance(self.app, ChordMixin):
            raise TypeError(
                f"ChordViewer needs an app with ChordMixin, "
                f"not {type(self.app).__name__}"
            )
        install_layer(self.screen, _LAYER)
        self.watch(self.app, "pending_chord", self._chord_changed, init=False)

    # ------------------------------------------------------------- showing

    def _chord_changed(self, steps: Steps) -> None:
        if not steps or self.screen is not self.app.screen:
            # A chord on another screen is for that screen's own panel.
            self._conceal()
        elif self.display:
            self.call_next(self._rebuild)
        elif self.delay <= 0:
            # A Timer cannot take an interval of zero -- it divides by it.
            self.call_next(self._reveal)
        elif self._delay_timer is None:
            # Timed from the first step, not reset by later ones: which-key's
            # delay is for hesitating at the start of a sequence.
            self._delay_timer = self.set_timer(self.delay, self._reveal)

    async def _reveal(self) -> None:
        self._delay_timer = None
        app = self._chords
        if self.display or not app.pending_chord or self.screen is not app.screen:
            return
        # Built before it is shown, so an empty panel is never painted.
        await self._rebuild()
        self.display = True
        app.hold_chord()

    def _conceal(self) -> None:
        if self._delay_timer is not None:
            self._delay_timer.stop()
            self._delay_timer = None
        self.display = False

    def on_resize(self) -> None:
        # The number of columns depends on the width.
        if self.display:
            self.call_next(self._rebuild)

    # ------------------------------------------------------------ building

    async def _rebuild(self) -> None:
        steps = self._chords.pending_chord
        if not steps or not self.is_mounted:
            return
        groups = chord_groups(self.screen)
        items = self._collect(steps, groups)
        self.query_one("#chord-viewer-trail", Static).update(self._trail(steps, groups))
        self.query_one("#chord-viewer-help", Static).update(self._help(steps))

        columns = self.query_one("#chord-viewer-columns", VerticalScroll)
        # The screen's width, not our own: a panel that is not displayed yet
        # has no size to go by.
        width = self.screen.size.width - columns.styles.gutter.width
        layout = _columns(
            [self._width(item) for item in items],
            width,
            self.MIN_COLUMN_WIDTH,
            self.COLUMN_SPACING,
        )
        if (items, len(layout)) == self._rendered:
            # A resize that keeps the column count, or a rebuild queued twice.
            return
        self._rendered = (items, len(layout))
        boxes = self.query_one("#chord-viewer-boxes", Horizontal)
        async with self.batch():
            await boxes.remove_children()
            await boxes.mount_all(
                [self._box([items[i] for i in rows]) for rows in layout]
            )
        columns.scroll_home(animate=False)

    def _collect(
        self, steps: Steps, groups: dict[Steps, str]
    ) -> tuple[ChordViewerItem, ...]:
        """One item per possible next step, sorted by key."""
        depth = len(steps)
        items: dict[str, ChordViewerItem] = {}
        nested: dict[str, list[bool]] = {}
        # `show` is deliberately ignored: it is the footer's flag, and keeping
        # chords out of the footer while finding them here is the whole point.
        # A chord with no description is left out -- which-key's `hidden`.
        for key, active in self.screen.active_bindings.items():
            chord = chord_steps(key)
            binding = active.binding
            if len(chord) <= depth or chord[:depth] != steps:
                continue
            if not binding.description:
                continue
            step = chord[depth]
            if len(chord) > depth + 1:
                nested.setdefault(step, []).append(active.enabled)
            elif step not in items:
                items[step] = ChordViewerItem(
                    step=step,
                    key_display=self._display(step),
                    description=binding.description,
                    enabled=active.enabled,
                    group=False,
                )

        for step, enabled in nested.items():
            existing = items.get(step)
            if existing is not None and existing.enabled:
                # The mixin runs a complete chord the moment it is typed, so
                # nothing beyond it can be reached.
                continue
            name = groups.get((*steps, step))
            if name is None:
                name = f"{len(enabled)} chord{'' if len(enabled) == 1 else 's'}"
            items[step] = ChordViewerItem(
                step=step,
                key_display=self._display(step),
                description=f"{self.GROUP_PREFIX}{name}",
                enabled=any(enabled),
                group=True,
            )
        return tuple(sorted(items.values(), key=lambda i: natural_key(i.key_display)))

    def _width(self, item: ChordViewerItem) -> int:
        return (
            cell_len(item.key_display)
            + cell_len(self.SEPARATOR)
            + 2
            + cell_len(item.description)
        )

    def _box(self, items: list[ChordViewerItem]) -> Vertical:
        key_width = max((cell_len(item.key_display) for item in items), default=0)
        return Vertical(
            *(ChordViewerEntry(item, key_width, self.SEPARATOR) for item in items),
            classes="chord-viewer-box",
        )

    def _display(self, key: str) -> str:
        return self.app.get_key_display(Binding(key, ""))

    def _trail(self, steps: Steps, groups: dict[Steps, str]) -> Text:
        """The steps typed so far, each followed by its group's name."""
        key_style = self.get_component_rich_style("chord-viewer--key")
        group_style = self.get_component_rich_style("chord-viewer--group")
        trail = Text()
        for depth in range(1, len(steps) + 1):
            if depth > 1:
                trail.append(f" {self.BREADCRUMB} ")
            trail.append(self._display(steps[depth - 1]), key_style)
            name = groups.get(steps[:depth])
            if name:
                trail.append(f" {name}", group_style)
        return trail

    def _help(self, steps: Steps) -> Text:
        """The key legend -- `back` only when there is a step to go back to."""
        legend = [("escape", "close")]
        back = self._chords.CHORD_BACK_KEY
        if back is not None and len(steps) > 1:
            legend.append((back, "back"))
        key_style = self.get_component_rich_style("chord-viewer--key")
        text = Text()
        for index, (key, label) in enumerate(legend):
            if index:
                text.append("   ")
            text.append(self._display(key), key_style)
            text.append(f" {label}")
        return text
