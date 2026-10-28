# Tabbed content

Textual's `TabbedContent` and `TabPane`, plus the two things every app kept
adding on top: a letter key per tab, and the focus following the tab into its
pane. Without the second, a tab's keys do nothing until it is clicked into,
and the next letter key goes nowhere — Textual drops the focus from the pane it
hides rather than moving it.

```python
from tcoda.widgets import TabbedContent, TabPane

with TabbedContent(initial="tab-data"):
    with TabPane("Columns", mnemonic="c", id="tab-columns"):
        yield DataTable()
    with TabPane("Data", mnemonic="d", id="tab-data"):
        yield DataTable()
```

Both are drop-ins: everything else — `active`, `add_pane`, `disable_tab`,
`hide_tab`, `TabActivated` — is Textual's, unchanged. A Textual `TabPane` mixes
in too; it just has no letter.

- **A `mnemonic` is found in the title by search**, so it need not be the first
  letter (`TabPane("Diff", mnemonic="d", id="tab-changes")`), and colored there
  bold in the theme's accent — the way the footer shows a key, so it reads as
  "a key you can press". The title is still markup, or a `Content`.
- **The letter is bound on the `TabbedContent`, not the screen.** It works
  wherever the focus is inside the widget, tab bar included, and two of them
  can share a screen with the same letters. See
  [DESIGN.md](../DESIGN.md#widgets-that-own-a-key-bind-it-on-their-screen).
  The bindings are hidden from the footer; the colored letter is the hint.
- **A disabled or hidden tab ignores its letter**, as it ignores a click.
  Setting `active` directly skips that check; `action_activate_tab` does not.
  A disabled tab's letter is not colored either, as in a menu, whichever way
  it was disabled — `disable_tab` or the pane's `disabled`.
- **The focus follows into the pane** on any change of tab. A letter always
  takes it in; a click, an arrow key or `active` does unless the focus is on
  the tab bar: someone walking the tabs with left/right must not have it
  yanked away after the first step. It also stays put when it is already
  inside the pane, or outside the widget altogether.
- **A pane with nothing to focus yet parks the focus on the tab bar** — one
  still `loading`, say. Left where Textual drops it, the focus would be
  nowhere, and the letters and arrow keys with it. Call
  `focus_active_pane()` once the pane's content is ready: it takes the focus
  in from a parked tab bar or from nowhere, but not from a tab bar the user
  has started walking, nor from anywhere else.
- **`focus_target(pane)` picks what gets it**: the pane's first focusable
  widget that is displayed. A hidden search box or a not-yet-drawn chart is
  skipped, since focusing it would drop the focus altogether; with nothing to
  take it, the focus stays where it was. Override it for a pane whose keys
  belong to another widget.
- **At start the focus goes into the pane, not the tab bar**, where Textual's
  auto-focus would put it as the first focusable widget. An `AUTO_FOCUS` aimed
  elsewhere, inside the widget or beside it, is kept.
