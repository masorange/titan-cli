from titan_cli.ui.elements import Box, Columns, Text, column_widths, responsive_columns
from titan_cli.ui.tui.widgets.element_widgets import _Columns, kind, plan_reconcile


def test_the_gap_comes_off_the_width_before_it_is_shared_by_ratio():
    assert column_widths(101, (3, 2), gap=1) == (60, 40)
    assert column_widths(10, (1, 1, 1), gap=2) == (2, 2, 2)


def test_a_column_is_never_narrower_than_one_cell():
    assert column_widths(2, (3, 2), gap=1) == (1, 1)


def test_columns_default_to_equal_shares_and_drop_empty_children():
    assert Columns(Text("a"), None, Text("b"), []).ratio == (1, 1)


def test_wide_screens_get_columns_drawn_for_the_width_each_has():
    drawn = []

    def left(w):
        drawn.append(("left", w))
        return Text("l")

    def right(w):
        drawn.append(("right", w))
        return Text("r")

    tree = responsive_columns(121, [left, right], ratio=(3, 2), collapse_below=120)

    assert isinstance(tree, Columns) and tree.ratio == (3, 2)
    assert drawn == [("left", 72), ("right", 48)]


def test_narrow_screens_stack_the_same_builders_at_the_full_width():
    drawn = []
    tree = responsive_columns(
        80, [lambda w: drawn.append(w) or Text("l"), lambda w: drawn.append(w) or Text("r")], ratio=(3, 2),
    )

    assert isinstance(tree, Box) and not isinstance(tree, Columns) and len(tree.children) == 2
    assert drawn == [80, 80]


def test_crossing_the_threshold_replaces_the_container_instead_of_patching_it():
    wide, narrow = responsive_columns(130, [lambda w: Text("a"), lambda w: Text("b")]), Box(Text("a"), Text("b"))

    assert kind(wide) is _Columns and kind(narrow) is not _Columns
    assert plan_reconcile([_Columns], [narrow]) == [("replace", 0)]
    assert plan_reconcile([_Columns], [wide]) == [("patch", 0)]
