"""Textual coda: widgets, dialogs and helpers.

Deliberately empty of imports: pulling in `tcoda` must not drag Textual (or a
config file read) into a module that only wanted the version. Import from
`tcoda.widgets`, `tcoda.dialogs`, `tcoda.settings` or `tcoda.chords` instead.
"""

from tcoda.version import __version__

__all__ = ["__version__"]
