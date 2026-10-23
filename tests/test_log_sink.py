# SPDX-FileCopyrightText: 2026 René de Hesselle <dehesselle@web.de>
#
# SPDX-License-Identifier: 0BSD

"""InMemoryLogHandler: structured buffering, the rolling capacity cap, and
subscriber fan-out -- all plain stdlib `logging`, no Textual involved."""

from __future__ import annotations

import logging
import threading

import pytest

from tcoda.log_sink import InMemoryLogHandler, LogEntry


def _logger(name: str, level: int = logging.DEBUG) -> logging.Logger:
    """An unregistered logger, isolated from the global manager and from
    every other test -- no cleanup needed, no risk of cross-test bleed."""
    logger = logging.Logger(name, level=level)  # noqa: LOG001
    return logger


# --------------------------------------------------------------- buffering


def test_emit_buffers_a_structured_log_entry() -> None:
    handler = InMemoryLogHandler()
    logger = _logger("source-a")
    logger.addHandler(handler)

    logger.warning("something happened")

    [entry] = handler.entries()
    assert entry.levelno == logging.WARNING
    assert entry.levelname == "WARNING"
    assert entry.source == "source-a"
    assert "something happened" in entry.line


def test_entries_is_a_snapshot_not_a_live_view() -> None:
    handler = InMemoryLogHandler()
    logger = _logger("source-a")
    logger.addHandler(handler)

    logger.info("first")
    snapshot = handler.entries()
    logger.info("second")

    assert len(snapshot) == 1
    assert len(handler.entries()) == 2


def test_the_buffer_is_capped_at_capacity_and_drops_the_oldest_first() -> None:
    handler = InMemoryLogHandler(capacity=5)
    logger = _logger("source-a")
    logger.addHandler(handler)

    for index in range(8):
        logger.info("message %d", index)

    entries = handler.entries()
    assert len(entries) == 5
    assert "message 3" in entries[0].line
    assert "message 7" in entries[-1].line


def test_emit_is_unfiltered_by_default_regardless_of_level() -> None:
    handler = InMemoryLogHandler()
    logger = _logger("source-a")
    logger.addHandler(handler)

    logger.debug("quiet")

    assert len(handler.entries()) == 1


# ------------------------------------------------------------- subscribers


def test_subscribers_receive_each_new_entry_in_order() -> None:
    handler = InMemoryLogHandler()
    logger = _logger("source-a")
    logger.addHandler(handler)
    received: list[LogEntry] = []
    handler.subscribe(received.append)

    logger.info("first")
    logger.info("second")

    assert [entry.line for entry in received] == [
        entries.line for entries in handler.entries()
    ]
    assert len(received) == 2


def test_unsubscribe_stops_further_delivery() -> None:
    handler = InMemoryLogHandler()
    logger = _logger("source-a")
    logger.addHandler(handler)
    received: list[LogEntry] = []
    handler.subscribe(received.append)

    logger.info("first")
    handler.unsubscribe(received.append)
    logger.info("second")

    assert len(received) == 1
    # The buffer keeps everything regardless of who's still subscribed.
    assert len(handler.entries()) == 2


def test_concurrent_emits_from_multiple_threads_preserve_count() -> None:
    handler = InMemoryLogHandler(capacity=1000)
    logger = _logger("source-a")
    logger.addHandler(handler)

    def _log_many() -> None:
        for _ in range(100):
            logger.info("from a thread")

    threads = [threading.Thread(target=_log_many) for _ in range(5)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(handler.entries()) == 500


# ------------------------------------------------------------------ errors


def test_a_broken_format_string_does_not_crash_emit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(logging, "raiseExceptions", False)
    handler = InMemoryLogHandler()
    logger = _logger("source-a")
    logger.addHandler(handler)

    logger.info("value %d", "not-a-number")

    assert handler.entries() == []


# ------------------------------------------------------------ plain stdlib


def test_the_handler_is_usable_via_plain_logging_addhandler() -> None:
    handler = InMemoryLogHandler()
    logger = logging.getLogger("tcoda-test-plain-stdlib")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    logger.addHandler(handler)
    try:
        logger.info("plain stdlib usage")
    finally:
        logger.removeHandler(handler)

    assert len(handler.entries()) == 1
