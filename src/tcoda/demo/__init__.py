"""The tcoda demo: `python -m tcoda`, as `python -m textual` runs Textual's.

A small browser over tcoda's own source files, built as ordinary consumer code
so that it doubles as a worked example of every widget and dialog. It is an
app, not a library module: importing it declares the demo's settings and
points `tcoda.settings.config` at the demo's own settings file.
"""

from tcoda.demo._app import DemoApp

__all__ = ["DemoApp"]
