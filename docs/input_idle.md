# Input idle

Tells the app how long it has gone without anyone using it. The mixin goes on
the app.

```python
from tcoda.chords import ChordMixin
from tcoda.input_idle import InputIdleMixin


class MyApp(InputIdleMixin, ChordMixin, App[None]):
    def on_tick(self) -> None:
        if self.seconds_since_input > 3600:
            ...  # nobody has been here for an hour
```

- **It only measures.** `seconds_since_input` is a number to read wherever the
  app already looks at the time. What to do about a long silence, such as
  stopping a poll, dimming or locking, is the app's decision. The mixin runs
  no timer and posts no message.
- **Input is what a person does on purpose:** a key press, a paste, a mouse
  button, the scroll wheel, and focusing the terminal window (`AppFocus`, for
  terminals that report focus).
- **Moving the mouse is not input.** A pointer passing over the terminal on
  its way somewhere else moves it too. Neither is losing focus.
- **Override `INPUT_EVENTS` to count something else.** It is a class attribute
  holding the event types above, so an app that does want mouse movement to
  count adds `events.MouseMove` to it.
- **The clock starts on mount**, so an app nobody has touched yet counts as
  used from the moment it appeared. Before mount it reads `0`.
- **An app's own `on_mount` cannot switch it off.** The mixin uses the private
  `_on_mount` handler, which Textual calls alongside the app's.
- **Put it before `ChordMixin`.** `ChordMixin` does not pass a key it consumes
  as a chord step on to `super()`, so a mixin after it would never see that
  key. That is the general rule anyway (see
  [DESIGN.md](DESIGN.md#mixins-go-first-and-have-no-__init__)).
- **It is not Textual's `events.Idle`**, which says a message queue has run
  empty.
