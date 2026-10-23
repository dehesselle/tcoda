# SPDX-FileCopyrightText: 2026 René de Hesselle <dehesselle@web.de>
#
# SPDX-License-Identifier: 0BSD

"""Overlay layers a widget registers on its host screen.

Textual's own overlays (LoadingIndicator, Toast, Tooltip) paint above ordinary
content through `_loading`/`_toastrack`/`_tooltips`, which are hardcoded into
`Screen.layers`. A library's overlay cannot be, so it adds its layer to the
screen it is mounted on -- the same way `MenuBar` installs a binding.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from textual.screen import Screen


def install_layer(screen: Screen[Any], name: str) -> None:
    """Add `name` on top of the screen's layers, unless it is there already."""
    # `screen.styles.layers` (the raw CSS rule) is empty until something sets
    # it -- it does not include "default", the name ordinary content resolves
    # to. Omitting that would put both the overlay and ordinary content at the
    # same paint-order index, defeating the overlay -- so an unset rule is
    # treated as `("default",)`, not `()`.
    existing = screen.styles.layers
    if name in existing:
        return
    base = existing if existing else ("default",)
    screen.styles.layers = (*base, name)
