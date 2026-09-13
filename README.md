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

## Header

A single line docked to the top, with independently clickable left, middle and
right areas. Styled like Textual's own `Header`, but with no icon and no clock,
and the middle tracks the app/screen title live until `show_title=False`.

```python
from tcw.widgets import Header, HeaderArea


class MainScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Header(left="MyApp", right="v1.0")

    @on(HeaderArea.Clicked, "#header-left")
    def _left_clicked(self) -> None:
        ...
```

- **The areas are equal thirds**, not docked to their content, so the middle
  stays centered on the screen however much text the other two hold. The
  trade-off is that all three ellipsize at a third of the width.
- **Later updates go through the area**, `header.left.update("Connected")`,
  rather than through setters on `Header`.

## Footer

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
  key — so `pinned=(OPEN_ACTION,)` pins a `MenuBar` whose key the app changed,
  where `pinned=("f9",)` would silently pin nothing.
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
  the dividers follow `display`, and a countdown that blanks at zero cannot
  express the difference between "zero seconds left" and "switched off".
- **Dividers appear only between areas that both have content**, drawn with
  Textual's own `border-left: vkey` rather than a character.
- **`Binding.Group` is ignored**; grouped bindings render as individual keys.

`Countdown` is published separately and depends on nothing here — put one
wherever a wait needs a number. It runs its own spinner: set `refreshing`.

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
        await self.app.push_screen_wait(OpenDialog())
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
  bind it yourself. Where the key *appears* is not the bar's business: pin it
  with `Footer(pinned=(OPEN_ACTION,))`. Under a stock `Footer` it lands in
  focus-chain order like anything else.
- **Ids are CSS ids.** Textual only needs a `MenuItem` id to be unique among
  one menu's children, but an app stylesheet rule of the same name will style
  it — which, for a widget inside a one-row bar, shows up as a garbled bar
  rather than as a colour. Prefer a name the app does not already use.

## Log viewer

A panel that slides down from the top over existing content, showing the
last 30,000 lines a program has written through the stdlib `logging` module
-- no logfile, no tailing. A level dropdown (default: info and above) and a
per-source checklist (default: all sources visible) narrow what's shown.

```python
from tcw.widgets import LogViewer


class MainScreen(Screen):
    def compose(self) -> ComposeResult:
        yield LogViewer()
        ...
```

- **Zero-config by default.** `LogViewer()` creates its own in-memory sink
  (`tcw.log_sink.InMemoryLogHandler`) and attaches it to the root logger.
  Pass `logger=` (a `logging.Logger` or a name) to attach somewhere else
  instead. Pass an existing `handler=` -- typically one attached at process
  startup, before any UI existed -- to skip all of that: the viewer then
  only replays and subscribes, on the assumption the caller manages
  attachment themselves. `handler=` and `logger=` together raise
  `ValueError`.
- **The owned logger's level tracks the level dropdown**, not a fixed
  `DEBUG` -- a logger left at `DEBUG` costs measurably more than one at its
  default (every `debug`/`info` call across the whole logger hierarchy
  actually builds a `LogRecord` instead of short-circuiting), so the cost is
  paid only for whatever's currently selected, not unconditionally because a
  `LogViewer` exists. This only applies when `LogViewer` owns the logger --
  an explicitly-passed `handler=` means levels are the caller's business.
- **`LogViewer` installs its own key binding** (`F1` by default) the same
  way `MenuBar` does. Pass `key=` to change it, or `key=None` to bind it
  yourself (see `TOGGLE_ACTION`).
- **Sources are logger names (`record.name`), discovered live** -- the
  checklist grows as new ones appear, defaulting to visible. Hiding a
  source stops new lines from it reaching the panel, but they stay in the
  sink's buffer -- showing it again picks up everything that arrived while
  it was hidden. Lowering the level dropdown has no equivalent: a level
  suppressed upstream before you asked for it is gone for good.

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
- `Setting(per_instance=True)` scopes a value to `config.current_instance`
  (a host, an account, a profile) instead of storing it globally; such
  settings are hidden entirely while no instance is active, and are marked in
  the dialog so a reader can tell the value differs elsewhere. *That* they are
  marked is the library's business; what the mark looks like is the app's --
  override `SettingsDialog.INSTANCE_GLYPH` and `INSTANCE_STYLE` (a Rich style,
  or `None` for the running theme's accent) in a subclass.
- `SettingAction` is a dialog row with no stored value — a button that runs a
  callback immediately. Its `callback` takes no arguments, because entries
  register at import time, long before any screen exists.
- A setting exists only once its module has been imported, so declaring one in
  a module behind an optional extra hides it from the dialog while its stored
  value lingers. Declare them somewhere always imported.

`tcw.dialogs` also publishes `SettingsDialog` (pushed on demand, or dropped
into a menu as `SettingsMenuItem`), plus the `Dialog` chrome and the
`ConfirmDialog` it uses for its unsaved-changes guard.

## About dialog

A small modal that reads its text from a file: the first five lines are a
fixed header (never scrolled — a logo or tagline), everything after that is
a scrollable body capped at ten lines, so the dialog never grows past
fifteen lines or 57 columns wide.

```python
from tcw.widgets import AboutMenuItem

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
- **`escape` dismisses it** — inherited from `Dialog`, like every other
  dialog here. There is no button row; this dialog only ever dismisses,
  nothing to confirm.

## Conventions

All styling is inline `DEFAULT_CSS` — a library cannot rely on a consumer's
`CSS_PATH`. Textual scopes it to the declaring widget's subtree, and an app's
own stylesheet outranks it regardless of specificity, so anything here can be
overridden.

Modal classes are named for what they are, not for the base class they
extend. A **`Dialog`** is a centered box that asks something and dismisses
with a result — `AboutDialog`, `ConfirmDialog`, `SettingsDialog`, and
whatever a consuming app adds. `MenuBarOverlay` and `MenuDropdown` are *not*
dialogs: they are transparent, render no chrome of their own, and exist only
to capture input while a menu is in use. **`Screen`** stays reserved for a
host app's own screens, such as its main one.

Textual has no `Dialog` of its own — its vocabulary stops at `Screen` and
`ModalScreen` — but it does not claim the term either, and everyone who has
met Qt, GTK or wxWidgets already knows what a dialog is. The word carries
more than the suffix did.
