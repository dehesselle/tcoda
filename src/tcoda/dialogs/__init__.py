"""The dialogs: the shared `Dialog` chrome, a yes/no question, the settings
UI, and the about box."""

from tcoda.dialogs._about import AboutDialog
from tcoda.dialogs._confirm import ConfirmDialog
from tcoda.dialogs._dialog import Dialog
from tcoda.dialogs._settings import SettingsDialog

__all__ = ["AboutDialog", "ConfirmDialog", "Dialog", "SettingsDialog"]
