# tcoda — design

This document holds the decisions that span more than one widget, dialog or
module. Reasoning specific to one component lives in that component's own doc,
next to what it explains — see the tables in the [README](../README.md).

## Why tcoda exists

The widgets here are meant to be shared between Textual apps, so a fix is made
once rather than in every app. Several docs open by naming the workarounds the
widget replaces.

The name is short for "Textual coda": what comes after the widgets Textual
itself provides.

## Styling is inline `DEFAULT_CSS`

All styling is inline `DEFAULT_CSS` — a library cannot rely on a consumer's
`CSS_PATH`. Textual scopes it to the declaring widget's subtree, and an app's
own stylesheet outranks it regardless of specificity, so anything here can be
overridden.

Where a choice is purely cosmetic and apps might reasonably differ, it is
exposed as a class attribute to override in a subclass rather than as a
constructor argument (e.g. `SettingsDialog.INSTANCE_GLYPH`,
`Countdown.SPINNER`). Where one consistent look across apps is the point, it
is not configurable at all (e.g. the `DataTable` sort glyphs).

## Naming: dialog, screen and overlays

Modal classes are named for what they are, not for the base class they
extend. A **`Dialog`** is a centered box that asks something and dismisses
with a result — `AboutDialog`, `ConfirmDialog`, `SettingsDialog`, and
whatever a consuming app adds. `MenuBarOverlay` and `MenuDropdown` are *not*
dialogs: they are transparent, render no chrome of their own, and exist only
to capture input while a menu is in use. **`Screen`** stays reserved for a
host app's own screens, such as its main one.

Textual has no `Dialog` of its own — its vocabulary stops at `Screen` and
`ModalScreen` — but it does not claim the term either, and everyone who has
met Qt, GTK or wxWidgets already knows what a dialog is.

The shared chrome is [`Dialog`](dialogs/Dialog.md).

## Widgets that own a key bind it on their screen

A widget with a key of its own ([`MenuBar`](widgets/MenuBar.md)'s F9,
[`LogViewer`](widgets/LogViewer.md)'s F1) installs the binding on whichever
screen it is mounted on. Textual only consults the focus chain plus the screen
and the app when resolving a key, so a widget that is never focused cannot own
one.

- The action is exported as a constant (`OPEN_ACTION`, `TOGGLE_ACTION`) so
  something other than the key can reach it with `run_action(...)`, and so a
  [`Footer`](widgets/Footer.md) pin keeps working when an app rebinds the key.
- `key=` changes the key; `key=None` installs nothing, leaving the app to bind
  it.
- `show_key=False` keeps the binding out of the footer altogether, but *where*
  it appears is never the widget's business — that is the footer's.

## Keys are shown through `App.get_key_display`

No widget formats a key itself. The [`Footer`](widgets/Footer.md), the
[`ChordViewer`](widgets/ChordViewer.md), the [chord](chords.md) status text
and a [`MenuItem`](widgets/MenuBar.md)'s shortcut all take a key in `Binding`
syntax and ask the app how to show it. Textual's answer is caret notation:
`^q`, `^k ^s`, lowercase `f5`, `esc`.

So the style is the app's choice, made once. An app that prefers `Ctrl+Q`
overrides `get_key_display` and every one of these follows, along with
Textual's own footer and key panel. A widget that accepted
pre-formatted text instead would be the one place that does not.

## Hide with `display`, never with an empty render

A widget that has nothing to show is hidden with `display = False`, not by
rendering an empty string. An empty render would mean "nothing to say", which
is not the same thing as a genuine zero, and a widget that conflates the two
cannot express either. It also matters structurally: the
[`Footer`](widgets/Footer.md)'s dividers follow `display`, so an empty-but-
displayed widget leaves a stray divider behind.
[`Countdown`](widgets/Countdown.md) renders `0` at zero for this reason.

## Mixins go first and have no `__init__`

Behaviour added to someone else's class ([`Resizable`](widgets/Resizable.md)
onto a widget, [`ChordMixin`](chords.md) onto an app) is a mixin, listed
*ahead* of the class it extends so its handlers run first in the MRO.

A mixin defines no `__init__`: one would have to cooperate with the signature
of every class it is mixed into. State it needs starts life as a class-level
default instead.

## `import tcoda` imports nothing

`tcoda/__init__.py` is deliberately empty of imports: pulling in `tcoda` must not
drag Textual (or a config file read) into a module that only wanted the
version. Consumers import from `tcoda.widgets`, `tcoda.dialogs`, `tcoda.settings`,
`tcoda.chords`, `tcoda.terminal_title`, `tcoda.log_sink` or `tcoda.plot`.

The same rule applies between subpackages: `tcoda.widgets` stays importable
without the settings machinery, so `SettingsMenuItem` imports
`SettingsDialog` lazily, when it is chosen.

## Code from elsewhere lives in its own subpackage

[`tcoda.plot`](plot.md) began as someone else's code (textual-plot and
textual-hires-canvas, MIT). It was absorbed rather than vendored: tcoda
changes it freely and does not re-sync with upstream. One directory draws
every boundary that comes with that:

- **License**: everything under `src/tcoda/plot/` is MIT, the rest of tcoda
  0BSD, so "`tcoda.plot` is MIT" stays literally true. A file changed here
  gains a copyright line but keeps its license.
- **Provenance**: the commit that brought the code in changed only headers
  and import paths, so the history shows exactly what tcoda made of it.
- **Dependencies**: nothing outside `tcoda.plot` imports it, so whatever it
  needs stays out of `tcoda.widgets` and the rest.

## Persisted state is an optimisation, never a dependency

Every store built on `tcoda.paths` (the settings file, and anything an app keeps
in its per-user config/cache/data directories) is an optimisation: an absent,
unreadable or corrupt file means "no data", not a crash on startup. That is
why `read_json` degrades to a default instead of raising, and why writes go
through a temp file (`write_json_atomic`) so a crash or a concurrent read
never sees half a file.
