# SPDX-FileCopyrightText: 2026 René de Hesselle <dehesselle@web.de>
#
# SPDX-License-Identifier: 0BSD

"""Key bindings a widget installs on its host screen.

A widget that is never focused cannot own a key: Textual only consults the
focus chain plus the screen and the app. So `MenuBar` and `LogViewer` put
both the action and its binding onto whichever screen they are mounted on,
and take both away again when they are removed.

One widget owns an action per screen -- the first one mounted. A second one
asking for a key raises at mount, since its key would reach the first one; a
second one with `key=None` mounts quietly and is driven through its own
methods. Per-instance actions would lift that limit, but at the price of the
fixed action name that `Footer(pinned=...)` and `run_action` rely on.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from textual.screen import Screen
    from textual.widget import Widget

#: The screen attribute recording which widget owns which action.
_OWNERS = "_tcoda_key_owners"


@dataclass(frozen=True)
class _Ownership:
    """Who owns an action on a screen, and what installing it changed --
    which is all that removing it may undo."""

    widget: Widget
    #: The key bound for it, or None if none was: `key=None`, or the screen
    #: already had that key on the action.
    bound_key: str | None
    #: Whether the action was set on the screen, rather than left to the
    #: screen class's own.
    set_action: bool


def _owners(screen: Screen[Any]) -> dict[str, _Ownership]:
    owners = screen.__dict__.get(_OWNERS)
    if owners is None:
        owners = {}
        setattr(screen, _OWNERS, owners)
    return owners


def install_screen_key(
    widget: Widget,
    action: str,
    handler: Callable[[], object],
    key: str | None,
    description: str,
    *,
    show: bool,
) -> Screen[Any]:
    """Make `widget` the owner of `action` on its screen, bound to `key`.

    The action is installed even with `key=None`, so an app binding the key
    itself reaches it. A screen class that defines the action itself keeps
    its own.

    Returns:
        The screen, for `uninstall_screen_key` -- by unmount time
        `widget.screen` may already be gone.

    Raises:
        ValueError: Another widget owns `action` here and `key` is not None.
    """
    screen = widget.screen
    owners = _owners(screen)
    owner = owners.get(action)
    if owner is not None:
        if owner.widget is widget or key is None:
            return screen
        raise ValueError(
            f"{widget!r} wants {key!r} for {action!r}, but {owner.widget!r} "
            f"already owns that action on this screen; pass key=None and "
            f"drive it through its own methods"
        )
    name = f"action_{action}"
    set_action = not hasattr(type(screen), name)
    if set_action:
        setattr(screen, name, handler)
    bound_key = None
    if key is not None and not any(
        binding.action == action
        for binding in screen._bindings.key_to_bindings.get(key, ())
    ):
        # Where the key *appears* is not the widget's business:
        # `Footer(pinned=(action,))` puts it wherever the app wants it.
        screen._bindings.bind(key, action, description, show=show)
        bound_key = key
    owners[action] = _Ownership(widget, bound_key, set_action)
    screen.refresh_bindings()
    return screen


def uninstall_screen_key(screen: Screen[Any], widget: Widget, action: str) -> None:
    """Undo `install_screen_key`, if `widget` is the owner of `action`."""
    owners = _owners(screen)
    owner = owners.get(action)
    if owner is None or owner.widget is not widget:
        return
    del owners[action]
    if owner.set_action:
        screen.__dict__.pop(f"action_{action}", None)
    if owner.bound_key is not None:
        bindings = screen._bindings.key_to_bindings
        kept = [
            binding
            for binding in bindings.get(owner.bound_key, ())
            if binding.action != action
        ]
        if kept:
            bindings[owner.bound_key] = kept
        else:
            bindings.pop(owner.bound_key, None)
    screen.refresh_bindings()
