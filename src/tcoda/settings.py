# SPDX-FileCopyrightText: 2026 René de Hesselle <dehesselle@web.de>
#
# SPDX-License-Identifier: 0BSD

"""Typed settings with a self-registering declaration.

Declaring a `Setting` at module scope registers it, so the settings dialog can
enumerate everything with no per-setting wiring. `ConfigStore` persists only
values somebody actually overrode -- a setting left at its default stays
absent from the file, so a later release can change that default without a
stale override silently shadowing it.

The store is a module-level singleton (`config`) that resolves its path
*lazily*, on first read or write rather than at import. That is what lets an
app call `configure("myapp")` from its own settings module after importing
this one, and lets a test point the whole thing at a tmp_path with one call
instead of monkeypatching the singleton's internals.

Where a setting is *declared* matters: it exists only once its module has been
imported, so declaring settings in a module gated behind an optional extra
makes the group vanish from the dialog while stored values linger. Declare
them somewhere always imported.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tcoda.paths import read_json, settings_file, write_json_atomic

_registry: dict[str, SettingsEntry] = {}

#: Reserved: `ConfigStore` keeps per-instance values in a dict under this key,
#: so a setting may not claim it.
INSTANCES_KEY = "instances"


def _parse_bool(text: str) -> bool:
    """Strict on purpose: an unrecognised word raises rather than quietly
    meaning False, so the dialog can refuse it with a visible warning instead
    of saving something the user did not type."""
    lowered = text.strip().lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"not a boolean: {text!r}")


_PARSERS: dict[type, Callable[[str], Any]] = {
    bool: _parse_bool,
    int: int,
    float: float,
    str: str,
}

_FORMATTERS: dict[type, Callable[[Any], str]] = {
    bool: lambda value: "true" if value else "false",
}


@dataclass(frozen=True)
class Setting[T: (bool, int, float, str)]:
    """One persisted, typed preference. Declaring it registers it."""

    key: str
    label: str
    description: str
    group: str
    default: T
    parse: Callable[[str], T] = field(default=None)  # type: ignore[assignment]
    format: Callable[[T], str] = field(default=None)  # type: ignore[assignment]
    #: Scoped per active instance (a host, an account, a profile -- whatever
    #: the app switches between) rather than global. See
    #: `ConfigStore.current_instance`.
    per_instance: bool = False
    #: When set, the dialog offers exactly these values (a `Select`) instead
    #: of free text. `None`, not an empty tuple, means "unconstrained" -- a
    #: setting always holds some value, so zero choices would be nonsensical.
    choices: tuple[T, ...] | None = None

    def __post_init__(self) -> None:
        value_type = type(self.default)
        if self.parse is None:
            object.__setattr__(self, "parse", _PARSERS[value_type])
        if self.format is None:
            object.__setattr__(self, "format", _FORMATTERS.get(value_type, str))
        _register(self)


@dataclass(frozen=True)
class SettingAction:
    """A settings-dialog row with no stored value: a labeled button that runs
    `callback` immediately when clicked, rather than editing something
    persisted in `ConfigStore`. Placed in the tree by the same `group` field a
    `Setting` uses, so "do a thing related to these settings" sits next to the
    settings it relates to instead of needing a dialog of its own.

    `button_label` is the text on the button ("Clear Now"), distinct from
    `label`, which names the row the way a `Setting`'s does.

    `callback` takes no arguments: entries register at import time, long
    before any screen or session exists, so it cannot close over app state and
    must construct whatever it needs.
    """

    key: str
    label: str
    description: str
    group: str
    button_label: str
    callback: Callable[[], None]
    #: Only offered while an instance is active. See `Setting.per_instance`.
    per_instance: bool = False

    def __post_init__(self) -> None:
        _register(self)


#: Everything the settings dialog can list in a group: a value-backed
#: `Setting` or a callback-backed `SettingAction`.
type SettingsEntry = Setting[Any] | SettingAction


def _register(entry: SettingsEntry) -> None:
    if entry.key == INSTANCES_KEY:
        raise ValueError(f"{INSTANCES_KEY!r} is a reserved setting key")
    if entry.key in _registry:
        raise ValueError(f"duplicate setting key: {entry.key!r}")
    _registry[entry.key] = entry


def all_settings() -> list[SettingsEntry]:
    """Every registered entry, ordered the way the dialog renders it."""
    return sorted(_registry.values(), key=lambda entry: (entry.group, entry.label))


class ConfigStore:
    """A JSON file of overridden values, keyed by `Setting.key`.

    Read values at the point of use (`config.get(SETTING)`) rather than
    caching the result, so a change made in the settings dialog takes effect
    without a restart.
    """

    def __init__(
        self, path: Path | None = None, *, app_name: str | None = None
    ) -> None:
        self._path = path
        self._app_name = app_name
        self._values: dict[str, Any] = {}
        self._loaded = False
        #: Which instance's values `per_instance=True` settings resolve against --
        #: the host/account/profile currently on screen, or None before one is
        #: active. The app is the only writer.
        self.current_instance: str | None = None

    # ----------------------------------------------------------------- path

    @property
    def path(self) -> Path:
        if self._path is None:
            if self._app_name is None:
                raise RuntimeError(
                    "tcoda settings are not configured; call "
                    "tcoda.settings.configure(<app name>) before using `config`"
                )
            self._path = settings_file(self._app_name)
        return self._path

    @path.setter
    def path(self, path: Path) -> None:
        self._path = path
        self._values = {}
        self._loaded = False

    def configure(
        self, app_name: str | None = None, *, path: Path | None = None
    ) -> None:
        """Point the store at an app's settings file. Idempotent; calling it
        again (a test switching to a tmp_path, say) discards loaded values so
        the next read comes from the new file."""
        self._app_name = app_name
        self._path = path
        self._values = {}
        self._loaded = False
        self.current_instance = None

    def load(self) -> None:
        data = read_json(self.path, {})
        self._values = data if isinstance(data, dict) else {}
        self._loaded = True

    # --------------------------------------------------------------- values

    def _bucket(self, setting: SettingsEntry, *, create: bool) -> dict[str, Any] | None:
        """Which dict `setting`'s value lives in: `_values` itself for a global
        setting, or its instance's slot under `_values["instances"]` for an
        instance-scoped one. `create` controls whether missing intermediate
        dicts are created (for set) or absence is just reported as None (for
        get/reset)."""
        if not self._loaded:
            self.load()
        if not setting.per_instance:
            return self._values
        if self.current_instance is None:
            raise ValueError(
                f"{setting.key!r} is instance-scoped but no instance is "
                "currently active"
            )
        instances = self._values.get(INSTANCES_KEY)
        if instances is None:
            if not create:
                return None
            instances = self._values[INSTANCES_KEY] = {}
        bucket = instances.get(self.current_instance)
        if bucket is None:
            if not create:
                return None
            bucket = instances[self.current_instance] = {}
        return bucket

    def get[T: (bool, int, float, str)](self, setting: Setting[T]) -> T:
        bucket = self._bucket(setting, create=False)
        if bucket is None:
            return setting.default
        value = bucket.get(setting.key, setting.default)
        # A hand-edited settings.json can hold anything; a wrong type here
        # would surface as a TypeError deep inside a worker instead of at the
        # point of use, so fall back to the default rather than trust it.
        # Exact type, not isinstance: bool is a subclass of int, so isinstance
        # would let a JSON `true` satisfy an int setting.
        if type(value) is not type(setting.default):
            return setting.default
        return value

    def set[T: (bool, int, float, str)](self, setting: Setting[T], value: T) -> None:
        """Store `value`, or drop the key when it equals the default -- a
        setting nobody overrode stays absent from the file, so a later release
        can change its default without a stale override shadowing it."""
        if value == setting.default:
            self.reset(setting)
            return
        bucket = self._bucket(setting, create=True)
        assert bucket is not None
        bucket[setting.key] = value
        self._save()

    def reset(self, setting: Setting[Any]) -> None:
        """Forget any stored override, pruning the emptied instance bucket so
        an untouched file stays clean."""
        bucket = self._bucket(setting, create=False)
        if bucket is None or setting.key not in bucket:
            return
        del bucket[setting.key]
        if setting.per_instance and not bucket:
            instances = self._values[INSTANCES_KEY]
            del instances[self.current_instance]
            if not instances:
                del self._values[INSTANCES_KEY]
        self._save()

    def _save(self) -> None:
        try:
            write_json_atomic(self.path, self._values)
        except OSError:
            # Best effort: an unwritable config dir must not take the app down
            # mid-edit. The value stays live for this session.
            pass


#: The single store every module imports by name.
config = ConfigStore()


def configure(app_name: str | None = None, *, path: Path | None = None) -> None:
    """Point the global `config` at an app's settings file.

    Call this once, from the app's own settings module, before anything reads
    a setting: `configure("myapp")`. Tests pass `path=` directly.
    """
    config.configure(app_name, path=path)
