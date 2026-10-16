"""The width a mod's pane is laid out for.

A pane is drawn once per state change, so whatever width it is given has to be the
width it will still have when the scrollbar appears. Getting this wrong is silent:
every row is built one or two columns too wide and Rich trims the right-hand end of
each with an ellipsis, which reads as "the mod truncates its own values" rather than
as a layout bug.
"""

from types import SimpleNamespace

from titan_cli.ui.tui.widgets.mod_side_panel import RAIL_WIDTH, _pane_width


def body(width: int, *, scrollbar_shown: bool, scrollbar: int = 2) -> SimpleNamespace:
    return SimpleNamespace(
        scrollable_content_region=SimpleNamespace(width=width),
        show_vertical_scrollbar=scrollbar_shown,
        scrollbar_size_vertical=scrollbar,
    )


class TestMeasuredWidth:

    def test_a_shown_scrollbar_is_already_out_of_the_measurement(self):
        # `scrollable_content_region` excludes it, so subtracting again would waste
        # two columns on every pane that scrolls.
        assert _pane_width(body(47, scrollbar_shown=True), 56) == 47

    def test_a_hidden_scrollbar_is_reserved_so_the_width_survives_it_appearing(self):
        assert _pane_width(body(49, scrollbar_shown=False), 56) == 47

    def test_the_measurement_wins_over_the_panel_width(self):
        # The panel's width says nothing about padding, borders or the rail; only the
        # container knows what is left for content.
        assert _pane_width(body(30, scrollbar_shown=True), 56) == 30


class TestBeforeTheFirstLayout:

    def test_an_unsized_container_falls_back_to_the_panel_arithmetic(self):
        # Textual reports a zero region until the widget has been laid out once.
        assert _pane_width(body(0, scrollbar_shown=False), 56) == 56 - RAIL_WIDTH - 3 - 2

    def test_the_fallback_reserves_the_scrollbar_too(self):
        narrow = _pane_width(body(0, scrollbar_shown=False, scrollbar=0), 56)
        assert narrow == 56 - RAIL_WIDTH - 3


class TestFloor:

    def test_a_panel_dragged_to_nothing_still_gets_a_usable_width(self):
        assert _pane_width(body(1, scrollbar_shown=True), 6) == 10
        assert _pane_width(body(0, scrollbar_shown=False), 6) == 10
