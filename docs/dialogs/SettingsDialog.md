# Settings dialog

A tree of setting groups on the left, the selected group's editable entries on
the right. It enumerates whatever has been declared with
[`tcw.settings`](../settings.md), so adding a setting needs no wiring here at
all.

```python
from tcw.widgets import Menu, MenuBar, SettingsMenuItem


class MainScreen(Screen):
    def compose(self) -> ComposeResult:
        with MenuBar():
            with Menu("File", id="file"):
                yield SettingsMenuItem()
```

- **Pushed on demand, or dropped into a menu as `SettingsMenuItem`.** The
  dialog is a modal screen, so it is never composed anywhere — something has
  to push it. `SettingsMenuItem` is that something, sparing the app both the
  menu entry and the handler behind it. Pushed directly, it is
  `self.app.push_screen(SettingsDialog())`.
- **Edits to the visible group are unsaved until Apply/OK.** Navigating to a
  different group with unsaved edits asks first, through
  [`ConfirmDialog`](ConfirmDialog.md), before discarding them.
- **A dotted `group` (`"Updates.Runner"`) materialises its parent node** in
  the tree, even with no entries assigned to the parent directly.
- **`per_instance` rows are marked**, so a reader can tell the value differs
  elsewhere. *That* they are marked is the library's business; what the mark
  looks like is the app's — override `INSTANCE_GLYPH` (default `◐`) and
  `INSTANCE_STYLE` (a Rich style, or `None` for the running theme's accent) in
  a subclass.
