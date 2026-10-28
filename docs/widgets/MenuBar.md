# Menu bar

A Midnight-Commander style pulldown bar: hidden until used, opened with F9 or
by clicking a title, with a bar-only stage before any dropdown so a mnemonic
letter is never ambiguous between "pick a menu" and "pick an item".

Declared inline, like any other part of a Textual UI:

```python
from tcoda.widgets import Menu, MenuBar, MenuItem, MenuSeparator, SettingsMenuItem


class MainScreen(Screen):
    def compose(self) -> ComposeResult:
        with MenuBar(trailing=f"myapp {VERSION}"):
            with Menu("File", id="file"):
                yield MenuItem("Open...", id="open", mnemonic="o")
                yield MenuSeparator()
                yield MenuItem("Save", id="save", mnemonic="s", shortcut="ctrl+s")
                yield SettingsMenuItem()
                yield MenuItem("Quit", id="quit", mnemonic="q", action="app.quit")

    @on(MenuItem.Pressed, "#open")
    @work
    async def _open(self) -> None:
        await self.app.push_screen_wait(OpenDialog())
```

- **Choosing an item posts `MenuItem.Pressed`**, which bubbles item → `Menu` →
  `MenuBar` → screen, so it is handled exactly like `Button.Pressed`. The
  message also carries the `Menu`, matchable as
  `@on(MenuItem.Pressed, "#filter", menu="#right")` — which is how one item id
  can appear in two menus and still act on the right thing.
- **A handler that pushes a screen and waits needs `@work`.** Nothing in a
  plain message handler provides the worker context `push_screen_wait`
  requires. The `action=` argument is the exception: `MenuBar` runs that
  action string from inside its own worker, so an action that awaits
  `push_screen_wait` works there without one. It takes only a string, as
  `Button`'s does; anything more is a `@on(MenuItem.Pressed)` handler.
- **`MenuBar` installs its own key binding** on whichever screen it is mounted
  on — see [DESIGN.md](../DESIGN.md#widgets-that-own-a-key-bind-it-on-their-screen).
  The action is called `open_menubar` (exported as `OPEN_ACTION`), so
  something other than the key (a clickable key bar, say) reaches it with
  `run_action("screen.open_menubar")`. Pass `key=None` to bind it yourself.
  Removing the bar unbinds the key; a second bar on the same screen needs
  `key=None`.
  Where the key *appears* is not the bar's business: pin it with
  [`Footer(pinned=(OPEN_ACTION,))`](Footer.md). Under a stock `Footer` it lands
  in focus-chain order like anything else.
- **`disabled` works as it does on any Textual container.** A disabled
  `MenuItem` is greyed out and cannot be chosen; a disabled `Menu` greys its
  title, is passed over by arrows, mnemonics and the mouse, and disables
  every item in it. `MenuBar.enabled_menus` lists the ones left to open.
- **A shortcut is a key, not a label.** `shortcut=` is written the way a
  `Binding` key is (`"ctrl+s"`, `"f5"`, `"ctrl+k d s"`) and shown through
  `App.get_key_display` — `^s`, `f5`, `^k d s` by default — so it reads the
  same as the [`Footer`](Footer.md). It only advertises the key; the binding
  itself lives in `BINDINGS` as usual. See
  [DESIGN.md](../DESIGN.md#keys-are-shown-through-appget_key_display).
- **Ids are CSS ids.** Textual only needs a `MenuItem` id to be unique among
  one menu's children, but an app stylesheet rule of the same name will style
  it — which, for a widget inside a one-row bar, shows up as a garbled bar
  rather than as a colour. Prefer a name the app does not already use.
- **Ready-made items**: [`SettingsMenuItem`](../dialogs/SettingsDialog.md) and
  [`AboutMenuItem`](../dialogs/AboutDialog.md) each open their dialog with no
  handler on the app's side. They handle their own `Pressed` without stopping
  it, so the app still hears it, and the bar closes as the dialog opens.
- **Type alias for annotations**: `MenuEntry` is anything that can sit in a
  `Menu` (`MenuItem | MenuSeparator`).
