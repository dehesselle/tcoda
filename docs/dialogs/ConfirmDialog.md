# ConfirmDialog

A generic yes/no question, kept free of any particular question's vocabulary
so the next confirmation need not invent its own dialog.
[`SettingsDialog`](SettingsDialog.md) uses it for its unsaved-changes guard.

```python
from tcw.dialogs import ConfirmDialog


@work
async def _delete(self) -> None:
    if await self.app.push_screen_wait(
        ConfirmDialog(
            "Delete 3 files?",
            title="Delete",
            confirm_label="Delete",
            cancel_label="Keep",
            danger=True,
            focus_cancel=True,
        )
    ):
        ...
```

- **Dismisses `True` for the confirm button, `False` for the cancel button or
  escape** — the result is always a `bool`, never `None`.
- **`danger=True` styles the confirm button as destructive** (Textual's `error`
  variant instead of `primary`).
- **`focus_cancel=True` puts the initial focus on the cancel button**, so a
  stray Enter cannot go through with something costly.
- **Everything else is [`Dialog`](Dialog.md)'s** — the chrome, escape, and the
  60-column width is its only styling of its own.
