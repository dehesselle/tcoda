# Dialog

The shared chrome for centered modal dialogs, and the base class of every
dialog in tcoda. It hoists only what every dialog shares: a bordered box, a bold
centered title, a right-aligned button row, and escape-to-cancel. What a
"dialog" is, as opposed to a screen or an overlay, is set out in
[DESIGN.md](../DESIGN.md#naming-dialog-screen-and-overlays).

```python
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Label

from tcoda.dialogs import Dialog


class RenameDialog(Dialog[str | None]):
    DEFAULT_CSS = """
    RenameDialog > #dialog { width: 50; }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label("Rename", id="title")
            ...
            with Horizontal(id="buttons"):
                yield Button("OK", variant="primary", id="ok")
```

- **The chrome hangs off ids**: a `#dialog` container directly under the
  screen, with `#title` and `#buttons` directly under that. Everything else in
  the box is the subclass's own.
- **Width and height are the subclass's.** They genuinely differ between a form
  and a picker, so the base sets only `height: auto`; set your own `#dialog`
  width (and height, if it should not size to content).
- **Escape dismisses with `CANCEL_RESULT`**, `None` unless a subclass sets it —
  [`ConfirmDialog`](ConfirmDialog.md) uses `False`, so its result stays a
  `bool`.
- **A dialog that must not be escapable overrides `check_action`** to disable
  the `cancel` action rather than dropping the binding: Textual merges
  `BINDINGS` across a class hierarchy, so a subclass cannot remove one it
  inherited.
