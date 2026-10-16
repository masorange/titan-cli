"""
Tests for arrow-key focus movement in a card grid.

Pure index arithmetic - nothing is mounted, so these do not fall under the no-UI-tests rule
that the rest of this screen's behaviour lives under.
"""

import pytest

from titan_cli.ui.tui.grid_navigation import Direction, next_focus_index


def move(current: int, direction: Direction, count: int = 9, columns: int = 3) -> int:
    """Shorthand: where the focus goes from `current`."""
    return next_focus_index(current, count, columns, direction)


class TestWithinAFullGrid:
    """A 3x3 grid, every position filled."""

    def test_right_moves_one_column(self):
        assert move(0, Direction.RIGHT) == 1

    def test_left_moves_one_column_back(self):
        assert move(1, Direction.LEFT) == 0

    def test_down_moves_a_whole_row(self):
        assert move(0, Direction.DOWN) == 3

    def test_up_moves_a_whole_row_back(self):
        assert move(3, Direction.UP) == 0

    def test_right_crosses_into_the_next_row(self):
        # Index 2 ends the first row; right goes to 3, which starts the second. Arrows
        # follow the sequence horizontally rather than stopping at the row edge, so a card
        # is never unreachable.
        assert move(2, Direction.RIGHT) == 3

    def test_a_round_trip_returns_where_it_started(self):
        there = move(4, Direction.DOWN)
        assert move(there, Direction.UP) == 4


class TestEdgesDoNotWrap:
    """A focus that leaps corner to corner reads as a glitch, not as navigation."""

    def test_left_at_the_first_card_stays(self):
        assert move(0, Direction.LEFT) == 0

    def test_right_at_the_last_card_stays(self):
        assert move(8, Direction.RIGHT) == 8

    def test_up_from_the_first_row_stays(self):
        assert move(1, Direction.UP) == 1

    def test_down_from_the_last_row_stays(self):
        assert move(7, Direction.DOWN) == 7


class TestTheShortLastRow:
    """The case that makes `down` asymmetric - and the card it would otherwise orphan."""

    def test_down_into_a_short_row_lands_on_the_last_card(self):
        # 7 cards in 3 columns: rows of 3, 3, 1. Down from index 4 (middle of row 2) would
        # be index 7, which does not exist. Without the fallback the only card in the last
        # row is unreachable by arrows.
        assert next_focus_index(4, 7, 3, Direction.DOWN) == 6

    def test_down_from_the_short_row_itself_stays(self):
        assert next_focus_index(6, 7, 3, Direction.DOWN) == 6

    def test_up_out_of_a_short_row_uses_plain_arithmetic(self):
        # No fallback needed upwards: the first row is never short.
        assert next_focus_index(6, 7, 3, Direction.UP) == 3

    def test_down_lands_exactly_when_the_row_below_is_full_enough(self):
        assert next_focus_index(3, 8, 3, Direction.DOWN) == 6


class TestDegenerateGrids:
    """Shapes a real screen produces: one column when narrow, one card, none at all."""

    def test_a_single_column_behaves_like_a_list(self):
        assert next_focus_index(0, 4, 1, Direction.DOWN) == 1
        assert next_focus_index(1, 4, 1, Direction.UP) == 0
        assert next_focus_index(3, 4, 1, Direction.DOWN) == 3

    def test_a_single_card_never_moves(self):
        for direction in Direction:
            assert next_focus_index(0, 1, 3, direction) == 0

    def test_an_empty_grid_returns_the_index_unchanged(self):
        assert next_focus_index(0, 0, 3, Direction.DOWN) == 0

    def test_zero_columns_is_treated_as_one_column(self):
        # A grid queried mid-layout can report no columns; the alternative is dividing by it.
        assert next_focus_index(0, 4, 0, Direction.DOWN) == 1

    @pytest.mark.parametrize("current", [-5, 99])
    def test_an_out_of_range_index_is_clamped_before_moving(self, current):
        assert 0 <= next_focus_index(current, 9, 3, Direction.RIGHT) <= 8

    def test_more_columns_than_cards_keeps_everything_on_one_row(self):
        # Two cards in a five-column grid are one row, so there is nothing below to reach
        # and the short-last-row fallback must NOT fire. This assertion was written the
        # other way round first and the code was right: the fallback exists to reach a row
        # that EXISTS, not to invent one.
        assert next_focus_index(0, 2, 5, Direction.DOWN) == 0
        assert next_focus_index(1, 2, 5, Direction.DOWN) == 1
        assert next_focus_index(0, 2, 5, Direction.RIGHT) == 1
