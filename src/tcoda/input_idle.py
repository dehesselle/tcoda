# SPDX-FileCopyrightText: 2026 René de Hesselle <dehesselle@web.de>
#
# SPDX-License-Identifier: 0BSD

"""How long the app has gone without anyone using it.

    class MyApp(InputIdleMixin, ChordMixin, App[None]):
        def on_tick(self) -> None:
            if self.seconds_since_input > 3600:
                ...  # nobody has been here for an hour

The mixin only measures. What to do about a long silence -- stop polling a
server, dim the screen, lock -- is the app's decision, made wherever it already
looks at the time.

Input is what a person does on purpose: a key press, a paste, a mouse button,
the scroll wheel, and focusing the terminal window. Mouse movement is not: a
pointer passing over the terminal on its way somewhere else produces it too.

It is not Textual's `events.Idle`, which says a message queue has run empty.

It has to come before `ChordMixin` in the bases, as every tcoda mixin goes
first: `ChordMixin.on_event` does not call `super()` for a key it consumes as
a chord step, so a mixin after it would never see that key.
"""

from __future__ import annotations

from time import monotonic
from typing import TYPE_CHECKING, Any, ClassVar

from textual import events

if TYPE_CHECKING:
    from textual.app import App

    _Base = App[Any]
else:
    _Base = object


class InputIdleMixin(_Base):
    """Tracks the last input: `class MyApp(InputIdleMixin, App[None])`.

    The clock starts on mount, so an app nobody has touched yet counts as
    used from the moment it appeared. Its handler is the private `_on_mount`,
    which Textual calls alongside the app's own, so an `on_mount` that does
    not call super does not switch it off.
    """

    #: The events that count as someone using the app. Override to count more
    #: or fewer, e.g. to add `events.MouseMove`.
    INPUT_EVENTS: ClassVar[tuple[type[events.Event], ...]] = (
        events.Key,
        events.Paste,
        events.MouseDown,
        events.MouseScrollUp,
        events.MouseScrollDown,
        events.MouseScrollLeft,
        events.MouseScrollRight,
        events.AppFocus,
    )

    #: `monotonic()` at the last input, or at mount before there was one.
    _last_input: float | None = None

    @property
    def seconds_since_input(self) -> float:
        """Seconds since the last input; 0 before the app is mounted."""
        if self._last_input is None:
            return 0.0
        return monotonic() - self._last_input

    def _on_mount(self, event: events.Mount) -> None:
        self._last_input = monotonic()

    async def on_event(self, event: events.Event) -> None:
        if isinstance(event, self.INPUT_EVENTS):
            self._last_input = monotonic()
        await super().on_event(event)
