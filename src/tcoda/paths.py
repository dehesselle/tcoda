# SPDX-FileCopyrightText: 2026 René de Hesselle <dehesselle@web.de>
#
# SPDX-License-Identifier: 0BSD

"""Per-app config/cache/data locations and small JSON helpers.

Every store built on these is an optimisation, never a dependency: an absent,
unreadable or corrupt file means "no data", not a crash on startup. That is
why `read_json` degrades to a default instead of raising, and why writes go
through a temp file so a crash or a concurrent read never sees half a file.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import platformdirs


def config_dir(app_name: str) -> Path:
    return Path(platformdirs.user_config_dir(app_name, appauthor=False))


def cache_dir(app_name: str) -> Path:
    return Path(platformdirs.user_cache_dir(app_name, appauthor=False))


def data_dir(app_name: str) -> Path:
    return Path(platformdirs.user_data_dir(app_name, appauthor=False))


def settings_file(app_name: str) -> Path:
    return config_dir(app_name) / "settings.json"


def write_json_atomic(path: Path, data: Any) -> None:
    """Create the parent dir, write to .tmp, then replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def read_json(path: Path, default: Any) -> Any:
    """Read JSON, degrading to `default` on anything going wrong."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default
