# Chord viewer

A panel in the style of [which-key.nvim](https://github.com/folke/which-key.nvim)
that lists what can follow a pending [chord](../chords.md): one entry per next
step, with the steps typed so far and a key legend on a line below. It needs a
`ChordMixin` app.

```python
from tcw.chords import ChordMixin
from tcw.widgets import ChordViewer, Footer


class MyApp(ChordMixin, App[None]):
    BINDINGS = [
        Binding("ctrl+k ctrl+s", "save_all", "Save all"),
        Binding("ctrl+k g c", "commit", "Commit"),
    ]
    CHORD_GROUPS = {"ctrl+k": "Keyboard", "ctrl+k g": "Git"}

    def compose(self) -> ComposeResult:
        yield Footer()
        yield ChordViewer()  # delay=0.2
```

```text
   ? ➜ Keyboard help           f1 ➜ Docs                  t ➜ Toggle theme
  ^o ➜ Open folder            f10 ➜ Release notes         w ➜ Close all windows
  ^s ➜ Save all                 g ➜ +Git                  x ➜ +Extras

  ^k Keyboard                          esc close
```

- **It appears only if the user hesitates**, `delay` seconds into a chord
  (0.2 by default, as in which-key). Someone typing a chord they know never
  sees it flash. The mixin's `CHORD_TIMEOUT` still applies until then, so a
  `delay` at or beyond the timeout means the panel never appears.
- **Once shown, it holds the chord open** until the chord completes or is
  abandoned; it never closes by timeout. It does this through
  `ChordMixin.hold_chord()`, so the mixin knows nothing about the panel.
- **While it is up, `⌫` steps back** instead of abandoning the chord (the
  mixin's `CHORD_BACK_KEY`). Stepping back from the first step closes it.
  Without a panel, backspace abandons the chord as any other key does. A
  chord that really continues with backspace still wins.
- **Groups are named in `CHORD_GROUPS`**, next to `BINDINGS` — see
  [chords](../chords.md#naming-groups). A step leading to further chords shows
  as `+Git`, or as `+2 chords` if it has no name. The bottom line names each
  typed step's group: `^k Keyboard » g Git`.
- **What is listed**: every enabled or dimmed chord on the current binding
  chain, one entry per next step, sorted naturally by key (`f2` before `f10`).
  `show=False` is ignored: that flag is the footer's, and keeping chords out
  of the footer while finding them here is the main reason to have the panel.
  A chord with no description is left out, which is which-key's `hidden`. A
  chord that `check_action` dims (returns None) is listed dimmed. If a step is
  both a complete chord and a prefix, the chord is listed, because the mixin
  runs it the moment it is typed.
- **Columns follow which-key's layout**, not a fixed number: as many as fit
  the widest entry (never narrower than `MIN_COLUMN_WIDTH`, 20) plus
  `COLUMN_SPACING` (3), filled top to bottom and then left to right, with a
  blank line above and below them (which-key's `win.padding`). The panel lays
  itself out again when the terminal is resized. It never takes more than
  half the screen; beyond that the entries scroll with the mouse wheel, and
  the blank lines stay put. Keyboard scrolling would need its own mixin hook, because any key
  that is not a next step abandons the chord.
- **Clicking an entry presses its step**, so clicking a group descends into
  it, much like clicking a key in the footer.
- **It covers the [footer](Footer.md)** rather than sitting above it. It is
  docked to the bottom in a layer of its own, and Textual arranges docked
  widgets separately for each layer, so its bottom line takes over the
  footer's "waiting for next key…" hint. Before the delay is up, that hint is
  what the user sees. The two widgets never need to know about each other.
- **It only reacts on its own screen.** A panel on a screen that is not the
  current one stays hidden; compose one onto each screen that should have it.
- **Mounting it in an app without `ChordMixin` raises `TypeError`.** Unlike
  the footer, it has no use without chords, and silently showing nothing would
  only hide the mistake.
- **Cosmetics are class attributes** to override in a subclass:
  `MIN_COLUMN_WIDTH`, `COLUMN_SPACING`, `SEPARATOR` (`➜`), `BREADCRUMB` (`»`)
  and `GROUP_PREFIX` (`+`), which-key's own defaults.
