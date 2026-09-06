"""Textual Common Widgets.

Deliberately empty of imports: pulling in `tcw` must not drag Textual (or a
config file read) into a module that only wanted the version. Import from
`tcw.widgets`, `tcw.screens` or `tcw.settings` instead.
"""

from tcw.version import __version__

__all__ = ["__version__"]
