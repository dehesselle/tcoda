# About dialog

A small modal that reads its text from a file: the first five lines are a
fixed header (never scrolled — a logo or tagline), everything after that is
a scrollable body capped at ten lines, so the dialog never grows past
fifteen lines or 57 columns wide.

```python
from tcoda.widgets import AboutMenuItem

from myapp import __version__


class MainScreen(Screen):
    def compose(self) -> ComposeResult:
        with MenuBar():
            with Menu("Help", id="help"):
                yield AboutMenuItem(
                    path="myapp/about.txt",
                    variables={"app": "myapp", "version": __version__},
                )
```

- **`path` is optional.** Omit it and `AboutDialog` shows a bundled
  placeholder — useful before an app has written its own about-text, or in
  tests. `AboutMenuItem(path=...)` passes it straight through.
- **`variables` fills in `$name` / `${name}` placeholders** in the
  about-text (via `string.Template.safe_substitute`) — handy for an app
  name or version number that only the consuming app knows. It's optional;
  omit it and the text is shown as-is. A placeholder with no matching key
  is left in the output untouched rather than raising.
- **Pushed directly, without a menu item**, with
  `self.app.push_screen(AboutDialog(path="myapp/about.txt"))`.
- **`escape` dismisses it** — inherited from [`Dialog`](Dialog.md), like every
  other dialog here. There is no button row; this dialog only ever dismisses,
  nothing to confirm.
