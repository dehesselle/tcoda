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
- **A [`ChordViewer`](widgets/ChordViewer.md) lists what can come next**, in
  the style of which-key.nvim, if the user hesitates partway through a chord.

## Naming groups

A prefix that leads to further chords can be given a name for the
[`ChordViewer`](widgets/ChordViewer.md) to show, in a class variable next to
`BINDINGS`:

```python
class MyApp(ChordMixin, App[None]):
    BINDINGS = [
        Binding("ctrl+k g a", "stage", "Stage"),
        Binding("ctrl+k g c", "commit", "Commit"),
    ]
    CHORD_GROUPS = {"ctrl+k": "Keyboard", "ctrl+k g": "Git"}
```

- **Only the names live there; the chords stay in `BINDINGS`.** That is what
  keeps `check_action`, keymaps, the footer and focus-chain scoping working,
  so the variable is deliberately `CHORD_GROUPS` and not `CHORDS`. A group is
  also not a fake binding: it has no action to run and nothing to match, so
  the mixin's matching does not change.
- **Any node with bindings may declare one**, app, screen or widget, and its
  names apply on the same terms as its bindings: while it is in the focus
  chain, with a node nearer the focus winning. A subclass adds to its
  parents' names rather than replacing them all, as `BINDINGS` does.
- **A group has no condition of its own.** It is shown only while some chord
  under it is, so it comes and goes with its chords.
- **A keymap that moves a chord's prefix does not move its group's name.**
  `set_keymap` only knows about bindings.
- `chord_groups(screen)` returns the names in force, keyed by steps.

## Holding a chord

`hold_chord()` is for whatever has just shown the user what can come next
(the `ChordViewer` calls it when it appears). The pending chord then waits
until it completes or is abandoned, whatever `CHORD_TIMEOUT` says, and
`CHORD_BACK_KEY` (`"backspace"`, or None for no back key) drops the last step
instead of abandoning the chord. Stepping back from the first step abandons
it. A chord that actually continues with that key still wins.
