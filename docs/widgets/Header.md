# Header

A single line docked to the top, with independently clickable left, middle and
right areas. Styled like Textual's own `Header`, but with no icon and no clock,
and the middle tracks the app/screen title live until `show_title=False`.

```python
from tcw.widgets import Header, HeaderArea


class MainScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Header(left="MyApp", right="v1.0")

    @on(HeaderArea.Clicked, "#header-left")
    def _left_clicked(self) -> None: ...
```

- **The areas are equal thirds**, not docked to their content, so the middle
  stays centered on the screen however much text the other two hold. The
  trade-off is that all three ellipsize at a third of the width.
- **Later updates go through the area**, `header.left.update("Connected")`,
  rather than through setters on `Header`.
