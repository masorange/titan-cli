from titan_cli.core.mods import Box, ModState, Option, Text, choice_card
from titan_cli.core.mods.choice_card import layout
from titan_cli.core.mods.elements import plain


def opts(*names):
    return [Option(n, lambda: None) for n in names]


def rows(options, width):
    return [[o.label for o in row] for row in layout(options, width)]


def test_options_that_fit_go_on_one_line():
    assert rows(opts("Squash", "Merge", "Rebase"), 40) == [["Squash", "Merge", "Rebase"]]


def test_options_that_do_not_fit_become_a_grid():
    names = ["feat/container-grid", "feat/cms-shield-home-poc", "develop", "main"]
    assert rows(opts(*names), 60) == [names[:2], names[2:]]


def test_options_wider_than_half_the_pane_become_a_column():
    names = ["chore/update-titan-config-and-review-profiles", "develop"]
    assert rows(opts(*names), 50) == [[names[0]], [names[1]]]


def test_a_card_lists_its_options_and_pads_a_grid_to_equal_cells():
    card = choice_card(opts("a", "bbbbbbbbbb", "cc"), width=16, title="Merge into main")
    assert card.border == "subtle" and plain(card.children[0]) == "Merge into main"
    assert [b.label for b in card.children[1:]] == ["a         ", "bbbbbbbbbb", "cc        "]


def lines(card):
    """Every label in a card, top to bottom, whatever the layout put them in."""
    out = []
    for child in card.children:
        if isinstance(child, Box):
            out += lines(child)
        elif hasattr(child, "label"):
            out.append(child.label.strip())
        elif isinstance(child, Text):
            out.append(plain(child))
    return out


def press(card, label):
    """Press the button of a card that says `label`, wherever its layout put it."""
    for child in card.children:
        if getattr(child, "label", None) is not None and child.label.strip() == label:
            return child.on_press()
        if isinstance(child, Box) and press_in(child, label):
            return
    raise AssertionError(label)


def press_in(box, label):
    for child in box.children:
        if getattr(child, "label", None) is not None and child.label.strip() == label:
            child.on_press()
            return True
        if isinstance(child, Box) and press_in(child, label):
            return True
    return False


def test_dropdowns_sit_among_the_options_and_open_one_at_a_time():
    state, picked, opened = ModState(lambda: None), [], []

    def build():
        return choice_card(
            [
                Option("Pull", lambda: picked.append("pull")),
                Option("Push", lambda: picked.append("push")),
                Option("Merge…", options=[Option("develop", lambda: picked.append("develop"))]),
                Option("New…", content=Text("a form"), on_open=lambda: opened.append("new")),
            ],
            width=60, state=state, key="k",
        )

    assert lines(build()) == ["Pull", "Push", "▸ Merge…", "▸ New…"]
    press(build(), "▸ Merge…")
    assert lines(build()) == ["Pull", "Push", "▾ Merge…", "develop", "▸ New…"]
    press(build(), "▸ New…")  # opening another closes the first
    assert lines(build()) == ["Pull", "Push", "▸ Merge…", "▾ New…", "a form"] and opened == ["new"]
    press(build(), "▾ New…")
    assert lines(build()) == ["Pull", "Push", "▸ Merge…", "▸ New…"]


def test_a_pick_inside_a_dropdown_closes_it_unless_told_not_to():
    state, picked = ModState(lambda: None), []
    for close in (True, False):
        state.set("k", "Merge…")
        def build():
            return choice_card([Option("Merge…", options=[Option("develop", lambda: picked.append(1))])],
                               width=60, state=state, key="k", close=close)

        press(build(), "develop")
        assert (state.get("k") is None) == close


def test_none_options_are_dropped_and_no_options_is_an_empty_card():
    assert rows([None, *opts("a")], 40) == [["a"]]
    assert choice_card([], width=40, title="Nothing").children[0].parts == ("Nothing",)
