"""Multi-keystroke ("chord") bindings, VSCode-style: `ctrl+k ctrl+s`.

Chords are declared in the ordinary `BINDINGS`, steps separated by a space::

    class MyApp(ChordMixin, App[None]):
        BINDINGS = [Binding("ctrl+k ctrl+s", "save_all", "Save all")]

That works without any help from Textual because `Binding.make_bindings` only
splits on `,`: the whole chord is stored as one key, `"ctrl+k ctrl+s"`, which
no single key press can ever match. Textual therefore ignores it for dispatch
but still lists it in `screen.active_bindings` -- so `check_action`, `show`,
`id`, keymaps and the footer all keep working unchanged. What it cannot do is
*match* one, and that is all this mixin adds.

It has to live on the App: `App.on_event` is the one funnel every key press
passes through before priority bindings are checked and before the focused
widget sees the key. Anything later is too late -- an `Input` would already
have acted on its own `ctrl+k`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from textual import events
from textual.binding import ActiveBinding, Binding
from textual.keys import _character_to_key, key_to_character
from textual.reactive import reactive

if TYPE_CHECKING:
    from textual.app import App
    from textual.screen import Screen
    from textual.timer import Timer

    _Base = App[Any]
else:
    _Base = object

type Steps = tuple[str, ...]


def chord_steps(key: str) -> Steps:
    """Split a binding key into its steps, normalised the way `event.key` is.

    Textual only normalises a key that is one character long *as a whole*, so
    the `?` in `"ctrl+k ?"` is never turned into `question_mark` -- which is
    what the key press will actually say.
    """
    return tuple(
        _character_to_key(step) if len(step) == 1 else step for step in key.split()
    )


class ChordMixin(_Base):
    """Adds chord bindings to an App: `class MyApp(ChordMixin, App[None])`.

    A chord's first step always wins over a single-key binding for the same
    key, wherever that binding sits in the focus chain -- but only while the
    chord itself is active, and never for a key the focused widget would type
    (a printable key in an `Input`), so `g g` does not stop anyone typing a g.
    """

    #: Seconds to wait for the next step before giving up, or None to wait
    #: forever. The swallowed steps are dropped, not replayed.
    CHORD_TIMEOUT: ClassVar[float | None] = 2.0

    #: The steps typed so far of a chord not yet complete, or () if none.
    pending_chord: reactive[Steps] = reactive(())

    _chord_timer: Timer | None = None
    _chord_screen: Screen[Any] | None = None

    async def on_event(self, event: events.Event) -> None:
        if (
            isinstance(event, events.Key)
            and not event.is_forwarded
            and await self._handle_chord_key(event)
        ):
            return
        await super().on_event(event)

    async def _handle_chord_key(self, event: events.Key) -> bool:
        """Advance, complete or abandon a chord. True if the key was consumed."""
        pending = self.pending_chord
        if pending and self.screen is not self._chord_screen:
            # The chord was started for bindings on a screen that is no longer
            # current; its steps mean nothing here.
            self._cancel_chord()
            pending = ()

        # `split()` rather than a 1-tuple: clicking a chord in the footer
        # simulates its whole key, "ctrl+k ctrl+s", as a single event.
        steps = (*pending, *chord_steps(event.key))
        is_prefix = False
        for chord, active in self._active_chords(first_step=not pending):
            if chord == steps:
                self._cancel_chord()
                await self.run_action(active.binding.action, active.node)
                return True
            if chord[: len(steps)] == steps:
                is_prefix = True

        if is_prefix:
            self._start_chord(steps)
            return True
        if pending:
            # Any key that continues no chord abandons it, escape included --
            # and is swallowed, as VSCode does, rather than typed half-way
            # through what the user thought was a command.
            self._cancel_chord()
            return True
        return False

    def _active_chords(self, first_step: bool) -> list[tuple[Steps, ActiveBinding]]:
        """Every enabled chord in the current binding chain, as steps."""
        chords: list[tuple[Steps, ActiveBinding]] = []
        for key, active in self.screen.active_bindings.items():
            steps = chord_steps(key)
            if len(steps) < 2 or not active.enabled:
                continue
            if first_step and self._consumed_before(steps[0], active):
                continue
            chords.append((steps, active))
        return chords

    def _consumed_before(self, key: str, active: ActiveBinding) -> bool:
        """Would a widget nearer the focus than the chord's node type this key?

        Textual applies the same rule to single-key bindings, but it cannot
        see the first step of a chord, only the whole string.
        """
        focused = self.focused
        if focused is None:
            return False
        character = key_to_character(key)
        for node in focused.ancestors_with_self:
            if node is active.node:
                return False
            if node.check_consume_key(key, character):
                return True
        return False

    def _start_chord(self, steps: Steps) -> None:
        self._stop_chord_timer()
        self._chord_screen = self.screen
        self.pending_chord = steps
        if self.CHORD_TIMEOUT is not None:
            self._chord_timer = self.set_timer(self.CHORD_TIMEOUT, self._cancel_chord)

    def _cancel_chord(self) -> None:
        self._stop_chord_timer()
        self._chord_screen = None
        self.pending_chord = ()

    def _stop_chord_timer(self) -> None:
        if self._chord_timer is not None:
            self._chord_timer.stop()
            self._chord_timer = None

    def get_key_display(self, binding: Binding) -> str:
        # Stock display splits on "+" only, so "ctrl+k ctrl+s" would come out
        # as "k ctrl+^s". Format each step on its own instead.
        display = super().get_key_display
        steps = chord_steps(binding.key)
        if binding.key_display or len(steps) < 2:
            return display(binding)
        return " ".join(display(binding.with_key(step)) for step in steps)

    def get_chord_display(self, steps: Steps) -> str:
        """Format typed steps the way the footer formats a key: `^k ^s`."""
        return " ".join(self.get_key_display(Binding(step, "")) for step in steps)
