# SPDX-FileCopyrightText: 2026 René de Hesselle <dehesselle@web.de>
#
# SPDX-License-Identifier: 0BSD

from __future__ import annotations

from pathlib import Path

import pytest

from tcoda import settings as settings_module


@pytest.fixture(autouse=True)
def colour_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Textual's monochrome filter takes a different render path, and the
    mnemonic colouring these widgets rely on is invisible under it."""
    monkeypatch.delenv("NO_COLOR", raising=False)


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path: Path) -> None:
    """A fresh registry and a tmp settings file per test.

    The registry is process-global by design (declaring a `Setting` anywhere
    registers it), so tests that declare their own must not leak into each
    other -- and `all_settings()` must not see settings from another module.
    """
    saved = dict(settings_module._registry)
    settings_module._registry.clear()
    settings_module.configure(path=tmp_path / "settings.json")
    yield
    settings_module._registry.clear()
    settings_module._registry.update(saved)


@pytest.fixture
def settings_path(tmp_path: Path) -> Path:
    return tmp_path / "settings.json"
