# Chords

VSCode-style bindings of several keystrokes in a row, declared in the ordinary
`BINDINGS` with the steps separated by a space. The mixin goes on the app,
because only the app sees a key before the focused widget does.

```python
from tcw.chords import ChordMixin


class MyApp(ChordMixin, App[None]):
    CHORD_TIMEOUT = 2.0  # the default; None waits forever

    BINDINGS = [
        Binding("ctrl+k ctrl+s", "save_all", "Save all", id="save-all"),
    ]
```

- **It has to live on the App.** `App.on_event` is the one funnel every key
  press passes through before priority bindings are checked and before the
  focused widget sees the key. Anything later is too late — an `Input` would
  already have acted on its own `ctrl+k`.
- **Everything else about a binding still works**: `check_action`, `show`,
  `id`, keymaps (`set_keymap({"save-all": "ctrl+k ctrl+w"})`), and any node in
  the focus chain can declare one. Textual stores a chord as one key that no
  single press can match, so it already lists them — the mixin only adds the
  matching.
- **A chord's first step beats a single-key binding on the same key**, however
  near the focus that binding is: while `ctrl+k ctrl+s` is active, `ctrl+k`
  starts it even in an `Input`, whose own `ctrl+k` deletes to the end of the
  line. The exception is a key the focused widget would *type*, so `g g` does
  not stop anyone typing a g.
- **A key that continues no chord abandons it and is swallowed**, `escape`
  included, rather than being typed halfway through what was meant as a
  command.
- **`CHORD_TIMEOUT` drops the steps typed so far**; it does not replay them to
  the focused widget.
- **The [footer](widgets/Footer.md) shows a pending chord** in its status
  corner, beside the app's own `status.update(...)` text rather than in place
  of it, and displays chord keys step by step (`^k ^s`). Clicking one runs it.
  The steps typed so far are also available as the app's `pending_chord`
  reactive.
