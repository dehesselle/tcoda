# Footer

Textual's `Footer` renders `screen.active_bindings` in focus-chain order, so
every key shifts whenever focus moves, and there is nowhere to put anything
that is not a key. This one splits the row into three areas — pinned keys, the
rest, and a status corner — each of which is optional. Left alone, it behaves
like the stock footer.

```python
from tcw.widgets import Countdown, Footer, OPEN_ACTION


class MainScreen(Screen):
    def compose(self) -> ComposeResult:
        with Footer(pinned=(OPEN_ACTION, "ctrl+q"), sort=True):
            yield Countdown(id="footer-countdown")
```

- **`pinned=` keys render leftmost, in the order given**, whatever the focus
  chain says. Each entry matches a binding's `id`, then its `action`, then its
  key — so `pinned=(OPEN_ACTION,)` pins a [`MenuBar`](MenuBar.md) whose key the
  app changed, where `pinned=("f9",)` would silently pin nothing.
- **A pinned binding renders even if it was declared `show=False`.** Naming a
  key is an explicit request to show it, and it has to be: Textual's own
  `ctrl+q` Quit is `show=False`, which is why no stock footer has ever shown
  it. A pin whose binding goes inactive keeps its slot, dimmed, rather than
  letting every pin after it shift — but a pin that has *never* been active
  has no description to draw yet and renders nothing.
- **`^p` gets no special treatment.** It is an app-level binding like any
  other, and it is declared `show=False`, so it does not appear unless pinned.
- **`sort=True` orders the unpinned keys** by displayed key, comparing digit
  runs as numbers so `f2` comes before `f10`; pass a callable over
  `FooterEntry` for anything else. Pins are never sorted — `pinned` already
  states their order. Worth knowing before turning it on: focus-chain order is
  not noise, it puts the most contextual keys first.
- **The status corner holds widgets, not just text.** Whatever is yielded into
  the footer lands there and is *never rebuilt*, so it keeps its own state —
  hold the reference and set attributes on it. There is no status channel,
  because none is needed once the widget survives. `footer.status.update(text)`
  sets a label alongside, without disturbing them.
- **Hide a status widget with `display`**, not by rendering an empty string —
  the dividers follow `display`, and a [countdown](Countdown.md) that blanks at
  zero cannot express the difference between "zero seconds left" and "switched
  off". See [DESIGN.md](../DESIGN.md#hide-with-display-never-with-an-empty-render).
- **Dividers appear only between areas that both have content**, drawn with
  Textual's own `border-left: vkey` rather than a character.
- **`Binding.Group` is ignored**; grouped bindings render as individual keys.
- **A pending [chord](../chords.md) shows in the status corner**, beside the
  app's own `status.update(...)` text rather than in place of it, and chord
  keys display step by step (`^k ^s`). Clicking one runs it.

Also exported, for customising rather than everyday use:

- **`FooterEntry`** — one binding as the footer will render it; what a custom
  `sort=` callable receives. **`sort_by_key`** is the natural-order key that
  `sort=True` uses.
- **`FooterBinding`** — the widget for one rendered key, stylable through its
  `footer-binding--key` and `footer-binding--description` component classes.
  Deliberately not named `FooterKey`: an app that also mounts a stock `Footer`
  would have that footer's `FooterKey` CSS match ours.
- **`FooterStatus`** — the status corner, reached as `footer.status`.
