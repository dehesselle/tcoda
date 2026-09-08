"""A rolling, structured, thread-safe log buffer with live fan-out.

`InMemoryLogHandler` is a plain `logging.Handler` -- zero Textual import, so
it is attachable to any logger before a UI (or any Textual app) exists, and
independently testable with nothing but the stdlib.

It is deliberately unfiltered by default (`level=NOTSET`): filtering by
level or source is a subscriber's concern (see `tcw.widgets.LogViewer`), not
the sink's, so the same buffer can serve several differently-filtered views.
Level, source and timestamp survive on each buffered `LogEntry` as queryable
fields rather than being baked into `line`'s formatted text, so a subscriber
can filter -- or build its own display line, e.g. with a timestamp column --
without re-parsing anything.
"""

from __future__ import annotations

import logging
import threading
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

Subscriber = Callable[["LogEntry"], None]


@dataclass(frozen=True, slots=True)
class LogEntry:
    """One buffered record."""

    levelno: int
    levelname: str
    source: str  # record.name -- the logger name
    created: float  # record.created -- seconds since the epoch
    line: str  # pre-formatted display text (self.format(record) at emit time)


class InMemoryLogHandler(logging.Handler):
    """Buffers up to `capacity` `LogEntry` records and fans out each new one
    to subscribers."""

    def __init__(self, *, capacity: int = 30_000, level: int = logging.NOTSET) -> None:
        super().__init__(level=level)
        self._buffer: deque[LogEntry] = deque(maxlen=capacity)
        self._lock = threading.Lock()
        self._subscribers: list[Subscriber] = []

    def emit(self, record: logging.LogRecord) -> None:
        try:
            line = self.format(record)
        except Exception:
            self.handleError(record)
            return
        entry = LogEntry(
            record.levelno, record.levelname, record.name, record.created, line
        )
        with self._lock:
            self._buffer.append(entry)
            subscribers = list(self._subscribers)
        # Fan-out runs outside the lock: a subscriber (e.g. LogViewer's
        # post_message bridge) must never be called while holding it, or a
        # subscribe/unsubscribe from within a callback would deadlock.
        for subscriber in subscribers:
            subscriber(entry)

    def entries(self) -> list[LogEntry]:
        """A snapshot of everything currently buffered, oldest first."""
        with self._lock:
            return list(self._buffer)

    def subscribe(self, callback: Subscriber) -> None:
        with self._lock:
            self._subscribers.append(callback)

    def unsubscribe(self, callback: Subscriber) -> None:
        with self._lock:
            self._subscribers.remove(callback)
