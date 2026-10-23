# SPDX-FileCopyrightText: 2026 René de Hesselle <dehesselle@web.de>
#
# SPDX-License-Identifier: 0BSD

"""Textual coda: widgets, dialogs and helpers.

Deliberately empty of imports: pulling in `tcoda` must not drag Textual (or a
config file read) into a module that only wanted the version. Import from
`tcoda.widgets`, `tcoda.dialogs`, `tcoda.settings`, `tcoda.chords`,
`tcoda.terminal_title` or `tcoda.log_sink` instead.
"""

from tcoda.version import __version__

__all__ = ["__version__"]
