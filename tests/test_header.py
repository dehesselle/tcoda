"""The header: default title tracking, left/right text, and clicks on each
area."""

from __future__ import annotations

from textual import on
from textual.app import App, ComposeResult

from tcw.widgets import Header, HeaderArea


class Harness(App[None]):
    def __init__(self, **header_kwargs: object) -> None:
        super().__init__()
        self.title = "MyApp"
        self._header_kwargs = header_kwargs
        self.clicked: list[str] = []

    def compose(self) -> ComposeResult:
        yield Header(**self._header_kwargs)

    @on(HeaderArea.Clicked, "#header-left")
    def _left_clicked(self) -> None:
        self.clicked.append("left")

    @on(HeaderArea.Clicked, "#header-middle")
    def _middle_clicked(self) -> None:
        self.clicked.append("middle")

    @on(HeaderArea.Clicked, "#header-right")
    def _right_clicked(self) -> None:
        self.clicked.append("right")


# -------------------------------------------------------------------- title


async def test_the_middle_area_shows_the_app_title_by_default() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        await pilot.pause()
        header = app.query_one(Header)
        assert "MyApp" in str(header.middle.content)


async def test_the_middle_area_tracks_a_later_title_change() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.title = "Renamed"
        await pilot.pause()
        header = app.query_one(Header)
        assert "Renamed" in str(header.middle.content)


async def test_a_screen_title_overrides_the_app_title() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.screen.title = "ScreenTitle"
        await pilot.pause()
        header = app.query_one(Header)
        assert "ScreenTitle" in str(header.middle.content)


async def test_show_title_false_leaves_custom_middle_text_alone() -> None:
    app = Harness(show_title=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        header = app.query_one(Header)
        header.middle.update("Custom")
        app.title = "Renamed"
        await pilot.pause()
        assert "Custom" in str(header.middle.content)


async def test_re_enabling_show_title_resumes_tracking() -> None:
    app = Harness(show_title=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        header = app.query_one(Header)
        app.title = "Renamed"
        header.show_title = True
        await pilot.pause()
        assert "Renamed" in str(header.middle.content)


# ---------------------------------------------------------------- left/right


async def test_left_and_right_text_render_in_their_areas() -> None:
    app = Harness(left="left-text", right="right-text")
    async with app.run_test() as pilot:
        await pilot.pause()
        header = app.query_one(Header)
        assert "left-text" in str(header.left.content)
        assert "right-text" in str(header.right.content)


async def test_updating_an_area_after_mount_goes_through_its_widget() -> None:
    app = Harness(left="left-text")
    async with app.run_test() as pilot:
        await pilot.pause()
        header = app.query_one(Header)
        header.left.update("Changed")
        await pilot.pause()
        assert "Changed" in str(header.left.content)


# -------------------------------------------------------------------- clicks


async def test_clicking_the_left_area_posts_clicked_scoped_to_it() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#header-left")
        await pilot.pause()
        assert app.clicked == ["left"]


async def test_clicking_the_middle_area_posts_clicked_scoped_to_it() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#header-middle")
        await pilot.pause()
        assert app.clicked == ["middle"]


async def test_clicking_the_right_area_posts_clicked_scoped_to_it() -> None:
    app = Harness()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#header-right")
        await pilot.pause()
        assert app.clicked == ["right"]


async def test_clicked_event_carries_the_clicked_area_as_its_control() -> None:
    class RecordingHarness(App[None]):
        def __init__(self) -> None:
            super().__init__()
            self.title = "MyApp"
            self.events: list[HeaderArea.Clicked] = []

        def compose(self) -> ComposeResult:
            yield Header()

        def on_header_area_clicked(self, event: HeaderArea.Clicked) -> None:
            self.events.append(event)

    app = RecordingHarness()
    async with app.run_test() as pilot:
        await pilot.pause()
        header = app.query_one(Header)
        await pilot.click("#header-left")
        await pilot.pause()
        assert len(app.events) == 1
        assert app.events[0].control is header.left
        assert app.events[0].area is header.left
