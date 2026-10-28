# SPDX-FileCopyrightText: 2026 René de Hesselle <dehesselle@web.de>
#
# SPDX-License-Identifier: 0BSD

"""A `TabbedContent` whose tabs switch by a letter and take the focus along.

Textual's own widget is all there; what every app kept adding on top of it is
not::

    with TabbedContent(initial="tab-data"):
        with TabPane("Columns", mnemonic="c", id="tab-columns"):
            yield DataTable()
        with TabPane("Data", mnemonic="d", id="tab-data"):
            yield DataTable()

A `mnemonic` colors its letter in the title the way a footer shows a key, and
binds it on the `TabbedContent`, so it works wherever the focus is inside it.
Switching tabs -- by letter, click or `active` -- moves the focus into the pane
just shown, unless the focus is on the tab bar itself: someone walking the
tabs with left/right must not have it yanked away after the first step.

Three Textual details are why this is a widget rather than a recipe:

* Textual hides the pane being left and drops the focus with it rather than
  moving it, so without the focus following, the next mnemonic goes nowhere.
* Setting `active` skips the disabled check that a click or an arrow key gets,
  so `action_activate_tab` repeats it.
* Auto-focus lands on the tab bar, the first focusable widget, which is the
  one place focus-follow leaves alone -- so the first time it does, the widget
  moves the focus into the pane. It cannot simply wait for its first refresh:
  with `initial=` set, that can come well after the app has put the focus
  somewhere on purpose.

The focus follows only from inside the widget, or from nowhere: a tab changed
by the app while the focus is beside the widget leaves the focus there.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual import events
from textual.content import Content, ContentType
from textual.css.query import NoMatches
from textual.widgets import ContentSwitcher, Tabs
from textual.widgets import TabbedContent as TextualTabbedContent
from textual.widgets import TabPane as TextualTabPane
from textual.widgets.tabbed_content import ContentTab, ContentTabs

if TYPE_CHECKING:
    from textual.await_complete import AwaitComplete
    from textual.widget import Widget

#: The action a mnemonic binding runs, with the pane id as its argument.
ACTIVATE_ACTION = "activate_tab"

#: How the mnemonic letter is styled: as Textual's footer styles a key, bold
#: in the key color. Not `$footer-key-foreground` itself -- some themes set it
#: against the footer's own background, and solarized-light's equals the
#: screen background, so anywhere else the letter would vanish.
MNEMONIC_STYLE = "$accent bold"


class TabPane(TextualTabPane):
    """Textual's `TabPane`, plus a letter that switches to it."""

    def __init__(
        self,
        title: ContentType,
        *children: Widget,
        mnemonic: str | None = None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        """
        Args:
            title: As for Textual's `TabPane`: a str is parsed as markup.
            mnemonic: A letter that switches to this pane while the focus is
                inside the `TabbedContent`. Located in `title` by search, so
                it need not be the first character, and colored there; a
                letter the title lacks still binds, but colors nothing. A
                disabled pane's letter is not colored, as in a menu.
        """
        self.mnemonic = mnemonic.lower() if mnemonic else None
        self.plain_title = (
            Content.from_markup(title) if isinstance(title, str) else title
        )
        self.mnemonic_title = self.plain_title
        if self.mnemonic is not None:
            index = self.plain_title.plain.lower().find(self.mnemonic)
            if index >= 0:
                self.mnemonic_title = self.plain_title.stylize(
                    MNEMONIC_STYLE, index, index + 1
                )
        super().__init__(
            self.plain_title if disabled else self.mnemonic_title,
            *children,
            name=name,
            id=id,
            classes=classes,
            disabled=disabled,
        )


class TabbedContent(TextualTabbedContent):
    """Textual's `TabbedContent`: mnemonics, and the focus follows the tab."""

    #: Set once the start-up focus is settled; until then a tab's activation
    #: is the initial one, and moving the focus would pre-empt auto-focus.
    _started = False

    def on_mount(self) -> None:
        for pane in self.get_child_by_type(ContentSwitcher).query_children(
            TextualTabPane
        ):
            self._bind_mnemonic(pane)
        self.call_after_refresh(self._focus_on_start)

    def add_pane(
        self,
        pane: TextualTabPane,
        *,
        before: TextualTabPane | str | None = None,
        after: TextualTabPane | str | None = None,
    ) -> AwaitComplete:
        added = super().add_pane(pane, before=before, after=after)
        # Textual has given the pane its id by now, before mounting it.
        self._bind_mnemonic(pane)
        return added

    def remove_pane(self, pane_id: str) -> AwaitComplete:
        self._unbind_mnemonics(f"{ACTIVATE_ACTION}({pane_id!r})")
        return super().remove_pane(pane_id)

    def clear_panes(self) -> AwaitComplete:
        self._unbind_mnemonics()
        return super().clear_panes()

    def action_activate_tab(self, pane_id: str) -> None:
        """Switch to a pane, as a click would: a disabled or hidden tab stays put.

        Setting `active` bypasses the checks that a click and the tab bar's
        arrow keys get for free, so they are repeated here.
        """
        tab = self.get_tab(pane_id)
        if tab.disabled or not tab.display:
            return
        self.active = pane_id

    def focus_target(self, pane: TextualTabPane) -> Widget | None:
        """What gets the focus when `pane` is shown: its first focusable widget.

        Override for a pane whose first focusable widget is not the one its
        keys belong to.
        """
        return next((widget for widget in pane.query("*") if widget.focusable), None)

    # ----------------------------------------------------------------- focus

    def _on_tabbed_content_tab_activated(
        self, event: TextualTabbedContent.TabActivated
    ) -> None:
        # Not stopped: the app's own handlers (lazy loading, mostly) still run.
        if event.tabbed_content is not self or not self._started:
            # The initial tab's activation, while mounting: _focus_on_start's.
            return
        focused = self.screen.focused
        if focused is not None:
            if self._is_own_tab_bar(focused) or self not in focused.ancestors:
                # The tab bar is being walked, or the focus is not ours.
                return
            if event.pane in focused.ancestors:
                # Already inside: an app focused a widget in a hidden pane,
                # and Textual switched to that pane for it.
                return
        self._focus_into(event.pane)

    def _on_descendant_focus(self, event: events.DescendantFocus) -> None:
        """The first focus to land in here settles the start: if it is
        auto-focus putting it on the tab bar, it goes into the pane instead."""
        if self._started:
            return
        self._started = True
        if self._is_own_tab_bar(event.widget) and self.active_pane is not None:
            self._focus_into(self.active_pane)

    def _focus_on_start(self) -> None:
        """Settle the start if no focus has landed in here by the first refresh.

        Auto-focus may have put it beside this widget -- an `Input`, say --
        which is the app's to keep. Only with no focus anywhere, as with
        auto-focus turned off, does the pane get it. This can run well after
        the first frames, so focus set in the meantime is kept too.
        """
        if self._started:
            return
        self._started = True
        if self.screen.focused is None and self.active_pane is not None:
            self._focus_into(self.active_pane)

    def _focus_into(self, pane: TextualTabPane) -> None:
        if (target := self.focus_target(pane)) is not None:
            target.focus()

    def _is_own_tab_bar(self, widget: Widget | None) -> bool:
        return isinstance(widget, ContentTabs) and widget.tabbed_content is self

    # ------------------------------------------------------------- mnemonics

    # A tab is disabled either through the tab bar or through its pane, and
    # Textual mirrors each onto the other while suppressing the second
    # message -- so both are heard here. These run before Textual's own, so
    # the state comes from the message rather than from the tab.

    def _on_tabs_tab_disabled(self, event: Tabs.TabDisabled) -> None:
        if event.tabs.parent is self and event.tab.id:
            self._restyle_title(ContentTab.sans_prefix(event.tab.id), disabled=True)

    def _on_tabs_tab_enabled(self, event: Tabs.TabEnabled) -> None:
        if event.tabs.parent is self and event.tab.id:
            self._restyle_title(ContentTab.sans_prefix(event.tab.id), disabled=False)

    def _on_tab_pane_disabled(self, event: TextualTabPane.Disabled) -> None:
        if event.tab_pane.id:
            self._restyle_title(event.tab_pane.id, disabled=True)

    def _on_tab_pane_enabled(self, event: TextualTabPane.Enabled) -> None:
        if event.tab_pane.id:
            self._restyle_title(event.tab_pane.id, disabled=False)

    def _restyle_title(self, pane_id: str, *, disabled: bool) -> None:
        """Color a pane's letter only while its tab can be used."""
        try:
            pane = self.get_pane(pane_id)
            tab = self.get_tab(pane_id)
        except (NoMatches, ValueError):
            return
        if isinstance(pane, TabPane):
            tab.label = pane.plain_title if disabled else pane.mnemonic_title

    def _bind_mnemonic(self, pane: TextualTabPane) -> None:
        if not isinstance(pane, TabPane) or pane.mnemonic is None or pane.id is None:
            return
        mnemonic = pane.mnemonic
        action = f"{ACTIVATE_ACTION}({pane.id!r})"
        if any(
            binding.action == action
            for binding in self._bindings.key_to_bindings.get(mnemonic, ())
        ):
            # Already bound: on_mount runs again if the widget is remounted.
            return
        self._bindings.bind(mnemonic, action, pane.plain_title.plain, show=False)
        self.refresh_bindings()

    def _unbind_mnemonics(self, action: str | None = None) -> None:
        """Drop the binding for one pane's action, or every mnemonic's."""
        bindings = self._bindings.key_to_bindings
        for key, entries in list(bindings.items()):
            kept = [
                binding
                for binding in entries
                if not binding.action.startswith(f"{ACTIVATE_ACTION}(")
                or (action is not None and binding.action != action)
            ]
            if kept:
                bindings[key] = kept
            else:
                del bindings[key]
        self.refresh_bindings()
