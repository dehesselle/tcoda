# SPDX-FileCopyrightText: 2026 René de Hesselle <dehesselle@web.de>
#
# SPDX-License-Identifier: 0BSD

"""The two panes of the demo: a directory tree you can resize by dragging its
border, and a sortable, tooltipped table of the selected directory's files."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from rich.text import Text
from textual.widgets import Tree

from tcoda.demo._settings import SIZE_UNITS
from tcoda.settings import config
from tcoda.widgets import DataTable, Resizable

if TYPE_CHECKING:
    from collections.abc import Iterable

    from textual.widgets.data_table import ColumnKey, RowKey
    from textual.widgets.tree import TreeNode


@dataclass(frozen=True)
class FileInfo:
    """One row of the table, and the model its `sort_key`s rank by."""

    path: Path
    size: int
    modified: float


def scan(directory: Path) -> list[FileInfo]:
    """The files directly inside `directory`."""
    files = []
    for path in sorted(directory.iterdir()):
        if path.is_file():
            stat = path.stat()
            files.append(FileInfo(path, stat.st_size, stat.st_mtime))
    return files


def format_size(size: int, units: str) -> str:
    base, suffixes = (
        (1024, ("B", "KiB", "MiB", "GiB"))
        if units == "binary"
        else (1000, ("B", "kB", "MB", "GB"))
    )
    if size < base:
        return f"{size} B"
    value = float(size)
    for suffix in suffixes[1:]:
        value /= base
        if value < base or suffix == suffixes[-1]:
            break
    return f"{value:.1f} {suffix}"


def format_age(modified: float, now: float) -> str:
    seconds = max(0, int(now - modified))
    for unit, span in (("day", 86400), ("hour", 3600), ("minute", 60)):
        if seconds >= span:
            count = seconds // span
            return f"{count} {unit}{'' if count == 1 else 's'} ago"
    return "just now"


def _subdirectories(directory: Path) -> list[Path]:
    return sorted(
        path
        for path in directory.iterdir()
        if path.is_dir() and path.name != "__pycache__"
    )


class Sidebar(Resizable, Tree[Path]):
    """The directory tree. Its right border is the drag handle."""

    DEFAULT_CSS = """
    Sidebar {
        width: 0.4fr;
        height: 1fr;
        border-right: vkey $foreground 30%;
    }
    """

    RESIZE_EDGE = "right"
    RESIZE_MIN = 16
    RESIZE_MIN_SIBLING = 40

    def __init__(self, root: Path, *, id: str | None = None) -> None:
        super().__init__(root.name, data=root, id=id)
        self._add_directories(self.root, root)
        self.root.expand()

    def _add_directories(self, node: TreeNode[Path], directory: Path) -> None:
        for path in _subdirectories(directory):
            if _subdirectories(path):
                self._add_directories(node.add(path.name, data=path, expand=True), path)
            else:
                node.add_leaf(path.name, data=path)


class FileTable(DataTable):
    """The files of one directory. Size and Modified are displayed rounded,
    and ranked by the exact number behind them."""

    DEFAULT_CSS = """
    FileTable {
        width: 1fr;
        height: 1fr;
    }
    """

    def __init__(self, *, id: str | None = None) -> None:
        super().__init__(cursor_type="row", zebra_stripes=True, id=id)
        #: Keyed by the row key, which is the path as a string.
        self.files: dict[str, FileInfo] = {}
        self.add_column("Name", key="name", sortable=True)
        self.add_column(
            "Size",
            key="size",
            sortable=True,
            sort_key=lambda row: self.files[row.value].size,
        )
        self.add_column(
            "Modified",
            key="modified",
            sortable=True,
            sort_key=lambda row: self.files[row.value].modified,
        )

    def show(self, files: Iterable[FileInfo]) -> None:
        """Replace the rows. An active sort is reapplied by `DataTable`."""
        self.clear()
        self.files = {str(info.path): info for info in files}
        units = config.get(SIZE_UNITS)
        now = time.time()
        for key, info in self.files.items():
            # Text rather than str: a bare string cell is parsed as markup.
            self.add_row(
                Text(info.path.name),
                self._size_cell(info, units),
                Text(format_age(info.modified, now)),
                key=key,
            )

    def restyle(self) -> None:
        """Re-render the sizes, for when the units setting changed."""
        units = config.get(SIZE_UNITS)
        for key, info in self.files.items():
            self.update_cell(
                key, "size", self._size_cell(info, units), update_width=True
            )

    def _size_cell(self, info: FileInfo, units: str) -> Text:
        return Text(format_size(info.size, units), justify="right")

    def get_cell_tooltip(self, row_key: RowKey, column_key: ColumnKey) -> str | None:
        info = self.files.get(row_key.value or "")
        if info is None:
            return None
        if column_key.value == "name":
            return str(info.path)
        if column_key.value == "size":
            return f"{info.size:,} bytes"
        if column_key.value == "modified":
            modified = datetime.fromtimestamp(info.modified, tz=UTC).astimezone()
            return modified.strftime("%Y-%m-%d %H:%M:%S")
        return None
