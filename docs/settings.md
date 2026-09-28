# Settings

`Setting` declarations self-register, so the
[settings dialog](dialogs/SettingsDialog.md) enumerates them with no
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

- **Only overrides are stored.** A setting left at its default stays absent
  from the file, so a later release can change that default without a stale
  override silently shadowing it.
- **`configure()` is lazy.** The store is a module-level singleton (`config`)
  that resolves its path on first read or write, not at import. That is what
  lets an app call `configure("myapp")` from its own settings module after
  importing this one, and lets a test point the whole thing at a `tmp_path`
  with `configure(path=...)` instead of monkeypatching the singleton.
- `group` may be dotted (`"Updates.Runner"`), which materialises the parent
  node in the dialog's tree.
- `Setting(per_instance=True)` scopes a value to `config.current_instance`
  (a host, an account, a profile) instead of storing it globally; such
  settings are hidden entirely while no instance is active, and are marked in
  the dialog so a reader can tell the value differs elsewhere (see
  [SettingsDialog](dialogs/SettingsDialog.md) for how to restyle the mark).
- `SettingAction` is a dialog row with no stored value — a button that runs a
  callback immediately. Its `callback` takes no arguments, because entries
  register at import time, long before any screen exists.
- A setting exists only once its module has been imported, so declaring one in
  a module behind an optional extra hides it from the dialog while its stored
  value lingers. Declare them somewhere always imported.
- The settings file lives in the platform's per-user config directory
  (`tcw.paths`). A missing or corrupt file reads as "no overrides" — see
  [DESIGN.md](DESIGN.md#persisted-state-is-an-optimisation-never-a-dependency).
