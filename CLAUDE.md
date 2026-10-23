# tcoda

**Read `docs/DESIGN.md` first.** It carries the conventions shared across every
widget and dialog, and the reasoning behind them.

## Instructions

This is a Textual-based library using Python 3.12. Use the `.venv` to call
`python`. Use `uv` for package management.

The codebase is ruff-formatted, `ruff` is available globally on this system.

The project is REUSE-compliant (`reuse` is available globally). New files
start with the SPDX header that `reuse annotate` writes; files that can't
carry a comment get covered in `REUSE.toml`. `reuse lint` must pass.

## Documentation

Every public widget, dialog and module has a doc under `docs/`. When changing
public behaviour, update that doc; when adding one, add a doc and a row to the
README table.
