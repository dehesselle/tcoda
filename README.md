# tcw — Textual Common Widgets

Widgets shared between several Textual apps (`snowcone`, `snakecam`, `vc`),
extracted so a fix is made once rather than three times.

Consumed as an editable path dependency while it is still being tracked from
source:

```toml
dependencies = ["tcw>=0.1"]

[tool.uv.sources]
tcw = { path = "../tcw", editable = true }
```

## Menu bar

A Midnight-Commander style pulldown bar: hidden until used, opened with F9 or
by clicking a title, with a bar-only stage before any dropdown so a mnemonic
letter is never ambiguous between "pick a menu" and "pick an item".

Declared inline, like any other part of a Textual UI:

```python
from tcw.widgets import Menu, MenuBar, MenuItem, MenuSeparator, SettingsMenuItem


class MainScreen(Screen):
    def compose(self) -> ComposeResult:
        with MenuBar(trailing=f"myapp {VERSION}"):
            with Menu("File", id="file"):
                yield MenuItem("Open...", id="open", mnemonic="o")
                yield MenuSeparator()
                yield MenuItem("Save", id="save", mnemonic="s", shortcut="Ctrl+S")
                yield SettingsMenuItem()
                yield MenuItem("Quit", id="quit", mnemonic="q", action="app.quit")

    @on(MenuItem.Pressed, "#open")
    @work
    async def _open(self) -> None:
        await self.app.push_screen_wait(OpenScreen())
```

- **Choosing an item posts `MenuItem.Pressed`**, which bubbles item → `Menu` →
  `MenuBar` → screen, so it is handled exactly like `Button.Pressed`. The
  message also carries the `Menu`, matchable as
  `@on(MenuItem.Pressed, "#filter", menu="#right")` — which is how one item id
  can appear in two menus and still act on the right thing.
- **A handler that pushes a screen and waits needs `@work`.** Nothing in a
  plain message handler provides the worker context `push_screen_wait`
  requires. The `action=` argument is the exception: `MenuBar` runs it from
  inside its own worker, so a Textual action string or an async callable works
  there without one.
- **`MenuBar` installs its own key binding** on whichever screen it is mounted
  on — Textual only consults the focus chain plus the screen and the app when
  resolving a key, so a bar that is never focused cannot own one. The action is
  called `open_menubar`, so something other than the key (a clickable key bar,
  say) reaches it with `run_action("screen.open_menubar")`. Pass `key=None` to
  bind it yourself.
- **Ids are CSS ids.** Textual only needs a `MenuItem` id to be unique among
  one menu's children, but an app stylesheet rule of the same name will style
  it — which, for a widget inside a one-row bar, shows up as a garbled bar
  rather than as a colour. Prefer a name the app does not already use.

## Settings

`Setting` declarations self-register, so the dialog enumerates them with no
per-setting wiring, and `ConfigStore` persists only values somebody actually
overrode.

```python
# myapp/settings.py
from tcw.settings import Setting, config, configure

configure("myapp")  # resolved lazily, on first read -- no import-time I/O

CACHE_TTL = Setting(
    key="cache_ttl",
    label="cache age",
    description="...",
    group="Cache",
    default=900,
)
```

Then `config.get(CACHE_TTL)` at the point of use — never cached, so a change in
the dialog takes effect without a restart.

- `group` may be dotted (`"Updates.Runner"`), which materialises the parent
  node in the dialog's tree.
- `Setting(instance=True)` scopes a value to `config.current_instance` (a host,
  an account, a profile) instead of storing it globally; such settings are
  hidden entirely while no instance is active.
- `SettingAction` is a dialog row with no stored value — a button that runs a
  callback immediately. Its `callback` takes no arguments, because entries
  register at import time, long before any screen exists.
- A setting exists only once its module has been imported, so declaring one in
  a module behind an optional extra hides it from the dialog while its stored
  value lingers. Declare them somewhere always imported.

`tcw.screens` also publishes `SettingsScreen` (pushed on demand, or dropped
into a menu as `SettingsMenuItem`), plus the `DialogScreen` chrome and the
`ConfirmScreen` it uses for its unsaved-changes guard.

## Conventions

All styling is inline `DEFAULT_CSS` — a library cannot rely on a consumer's
`CSS_PATH`. Textual scopes it to the declaring widget's subtree, and an app's
own stylesheet outranks it regardless of specificity, so anything here can be
overridden.
