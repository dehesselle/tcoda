"""The dialogs: the shared `Dialog` chrome, a yes/no question, the settings
UI, and the about box."""

from tcw.dialogs._about import AboutDialog
from tcw.dialogs._confirm import ConfirmDialog
from tcw.dialogs._dialog import Dialog
from tcw.dialogs._settings import SettingsDialog

__all__ = ["AboutDialog", "ConfirmDialog", "Dialog", "SettingsDialog"]
