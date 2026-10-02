"""The demo's settings, declared the way a consuming app declares its own: at
module scope, in a module that is always imported, with `configure()` called
before anything reads one."""

from __future__ import annotations

from tcoda.settings import Setting, SettingAction, config, configure

configure("tcoda-demo")

AUTO_REFRESH = Setting(
    key="auto_refresh",
    label="auto-refresh",
    description="Rescan the listing on a timer, counting down in the footer.",
    group="Demo.Refresh",
    default=True,
)

REFRESH_INTERVAL = Setting(
    key="refresh_interval",
    label="interval",
    description="Seconds between rescans.",
    group="Demo.Refresh",
    default=30,
)

SIZE_UNITS = Setting(
    key="size_units",
    label="size units",
    description="Binary counts in 1024s (KiB), decimal in 1000s (kB).",
    group="Demo.Table",
    default="binary",
    choices=("binary", "decimal"),
)


def _reset() -> None:
    for setting in (AUTO_REFRESH, REFRESH_INTERVAL, SIZE_UNITS):
        config.reset(setting)


RESET = SettingAction(
    key="reset_demo",
    label="demo settings",
    description="Put every demo setting back to its default.",
    group="Demo",
    button_label="Reset",
    callback=_reset,
)

#: Everything declared here. The tests re-register these: their fixture gives
#: each test an empty registry, and a module is only imported once.
DEMO_SETTINGS = (AUTO_REFRESH, REFRESH_INTERVAL, SIZE_UNITS, RESET)
