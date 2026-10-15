# Terminal title

Sets the terminal's window title while the app runs and puts the previous one
back when it exits. The mixin goes on the app.

```python
from tcoda.terminal_title import TerminalTitleMixin


class MyApp(TerminalTitleMixin, App[None]):
    TERMINAL_TITLE = "myapp"  # None (the default) leaves the title alone
```

- **Change it at runtime** by assigning the `terminal_title` reactive, e.g.
  `self.terminal_title = "myapp: playing"`. Setting it back to `None` leaves
  the current title in place; it does not restore the old one early.
- **It is not `App.title`.** That one only feeds the in-app header, and
  Textual never touches the terminal's title, so nothing fights over it.
- **The old title comes back on exit** through the terminal's title stack:
  XTPUSHTITLE before the first title is set, XTPOPTITLE on unmount. The app's
  `Unmount` is dispatched before the driver leaves application mode, so the
  pop still reaches the terminal.
- **Not every terminal has a title stack.** xterm, VTE-based terminals, kitty
  and WezTerm do; one that does not (possibly Windows Terminal) ignores both
  sequences and keeps the app's title until the shell sets another.
- **An app's own `on_mount` cannot switch it off.** The mixin uses the private
  `_on_mount`/`_on_unmount` handlers, which Textual calls alongside the app's.

## How it gets to the terminal

The title is an OSC 0 sequence (`ESC ] 0 ; title BEL`). It draws nothing and
does not move the cursor, so Textual's idea of the screen stays correct. It is
written through the app's driver, which is exactly how Textual sends its own
OSC 52 in `App.copy_to_clipboard`: in order with the frames, and on Windows
only once VT processing is on. Control characters are stripped from the
title first, since a BEL or ESC inside it would end the sequence early.
