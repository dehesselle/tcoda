"""Terminal title: set on mount, changeable at runtime, restored on exit."""

from __future__ import annotations

import pytest
from textual.app import App
from textual.drivers.headless_driver import HeadlessDriver

from tcoda.terminal_title import (
    POP_TITLE,
    PUSH_TITLE,
    TerminalTitleMixin,
    set_title_sequence,
)


class Harness(TerminalTitleMixin, App[None]):
    TERMINAL_TITLE = "harness"


class Untitled(TerminalTitleMixin, App[None]):
    pass


class OwnMount(TerminalTitleMixin, App[None]):
    TERMINAL_TITLE = "own"

    def on_mount(self) -> None:
        self.mounted = True


@pytest.fixture
def written(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Every title sequence the headless driver is asked to write."""
    out: list[str] = []

    def record(self: HeadlessDriver, data: str) -> None:
        if data in (PUSH_TITLE, POP_TITLE) or data.startswith("\x1b]0;"):
            out.append(data)

    monkeypatch.setattr(HeadlessDriver, "write", record)
    return out


async def test_title_is_pushed_set_and_popped(written: list[str]) -> None:
    async with Harness().run_test():
        assert written == [PUSH_TITLE, set_title_sequence("harness")]
    assert written[-1] == POP_TITLE


async def test_title_changes_at_runtime(written: list[str]) -> None:
    async with Harness().run_test() as pilot:
        pilot.app.terminal_title = "playing"
        await pilot.pause()
    assert written == [
        PUSH_TITLE,
        set_title_sequence("harness"),
        set_title_sequence("playing"),
        POP_TITLE,
    ]


async def test_no_title_writes_nothing(written: list[str]) -> None:
    async with Untitled().run_test():
        pass
    assert written == []


async def test_title_set_later_is_still_restored(written: list[str]) -> None:
    async with Untitled().run_test() as pilot:
        pilot.app.terminal_title = "later"
        await pilot.pause()
    assert written == [PUSH_TITLE, set_title_sequence("later"), POP_TITLE]


async def test_app_on_mount_does_not_switch_it_off(written: list[str]) -> None:
    async with OwnMount().run_test() as pilot:
        assert pilot.app.mounted
        assert written == [PUSH_TITLE, set_title_sequence("own")]


def test_control_characters_are_stripped() -> None:
    assert set_title_sequence("a\x07b\x1b]0;c\x9cd") == "\x1b]0;ab]0;cd\x07"
