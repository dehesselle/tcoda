# Countdown

A seconds counter, with a braille spinner for while something is actually in
flight. Two apps grew their own copy of this before it landed here. It is
published separately and depends on nothing else in tcw — the
[`Footer`](Footer.md) status corner is a natural home, but put one wherever a
wait needs a number.

```python
from tcw.widgets import Countdown

yield Countdown(id="footer-countdown")

...
countdown.remaining = 30  # counts down
countdown.refreshing = True  # spins until cleared
countdown.display = False  # gone entirely
```

- **It runs its own spinner: set `refreshing`.** The widget owns its clock, so
  a caller only says whether something is in flight — there is no frame
  counter to drive from outside, and no second timer to keep in step.
- **`display` is the only way to hide it.** Zero renders `0`, not an empty
  string: an empty render would mean "nothing to say", which is not the same
  thing as a genuine zero, and a widget that conflates the two cannot express
  either. See [DESIGN.md](../DESIGN.md#hide-with-display-never-with-an-empty-render).
- **The counter caps at `MAX_SECONDS` (999)**, three digits wide; a wait longer
  than that is not being read precisely anyway. `SPINNER` and
  `SPINNER_INTERVAL` are class attributes too.
