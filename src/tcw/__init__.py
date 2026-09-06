"""Textual Common Widgets.

Deliberately empty of imports: pulling in `tcw` must not drag Textual (or a
config file read) into a module that only wanted the version. Import from
`tcw.widgets`, `tcw.screens` or `tcw.settings` instead.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("tcw")
except PackageNotFoundError:  # running from a source tree that was never installed
    __version__ = "0.0.0"

__all__ = ["__version__"]
