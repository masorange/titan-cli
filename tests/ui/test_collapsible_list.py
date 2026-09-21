"""
Tests for the collapsible list widget.

Only the parts with a rule worth pinning: fitting a title to the width it is
given, the order in which styling is applied to it, and the choice between a
collapsible row and a plain line.
"""

import asyncio

from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Static

from titan_cli.ui.tui.widgets import (
    CollapsibleEntry,
    JsonTree,
    build_collapsible_list,
    build_json_entry,
    escape_markup,
)
from titan_cli.ui.tui.widgets.collapsible_list import (
    CopyButton,
    ListEntry,
    RightBlock,
    _styled,
    elide,
)

# ── fitting text to a row ─────────────────────────────────────────────────────

def test_elide_leaves_short_text_alone_and_never_pads():
    assert elide("short", 20) == "short"
    assert elide("exact", 5) == "exact"


def test_elide_marks_the_cut():
    assert elide("abcdefghij", 5) == "abcd…"


def test_elide_never_cuts_a_markup_escape_in_half():
    """
    `escape_markup` writes `\\[`, and cutting between the two leaves a stray
    backslash on screen and an unbalanced escape behind it.
    """
    assert elide(r"ab\[x]cd", 4) == "ab…"


def test_a_row_too_narrow_for_anything_says_nothing_rather_than_a_stray_character():
    assert elide("anything", 0) == ""
    assert elide("anything", 1) == "…"


def test_the_style_is_applied_after_the_cut_never_before():
    """Cutting styled text lands inside a `[dim]` and the tag reaches the screen."""
    assert _styled(elide("a very long name indeed", 8), "dim") == "[dim]a very …[/]"


def test_escape_markup_neutralises_content_that_came_from_outside():
    assert escape_markup("[MOBILE, LANDLINE]") == r"\[MOBILE, LANDLINE]"


# ── building the tree ─────────────────────────────────────────────────────────

def test_an_entry_with_nothing_behind_it_is_a_line_not_a_collapsible():
    """A triangle that opens onto emptiness reads as a bug."""
    container = build_collapsible_list([CollapsibleEntry(title="just a line")])

    row = container._pending_children[0]
    assert isinstance(container, Vertical)
    assert isinstance(row, Horizontal)
    assert not isinstance(row, ListEntry)


def test_an_entry_with_a_body_is_collapsible():
    container = build_collapsible_list(
        [CollapsibleEntry(title="has detail", body=["the detail"])]
    )
    assert isinstance(container._pending_children[0], ListEntry)


def test_children_of_a_collapsed_entry_are_not_built_until_it_is_opened():
    """A large tree must cost nothing until the user asks for it."""
    entry = CollapsibleEntry(
        title="parent", body=["detail"],
        children=[CollapsibleEntry(title="child", body=["more"])],
    )
    collapsible = build_collapsible_list([entry])._pending_children[0]

    assert len(collapsible._pending) == 1
    assert len(collapsible._contents_list) == 1  # the body, not the child


def test_children_of_an_expanded_entry_are_built_up_front():
    """It would otherwise expand onto nothing."""
    entry = CollapsibleEntry(
        title="parent", body=["detail"], expanded=True,
        children=[CollapsibleEntry(title="child", body=["more"])],
    )
    collapsible = build_collapsible_list([entry])._pending_children[0]

    assert collapsible._pending == []
    assert len(collapsible._contents_list) == 2


def test_the_container_grows_with_its_content():
    """
    Textual's default `1fr` means "take the space offered", which inside a step's
    output is a couple of lines — clipping the list with nothing to scroll.
    """
    container = build_collapsible_list([CollapsibleEntry(title="a")])
    assert container.styles.height.is_auto


def test_a_plain_line_still_gets_its_right_block_and_copy_button():
    """Nothing to open does not mean nothing to copy."""
    row = build_collapsible_list(
        [CollapsibleEntry(title="a line", right="12ms", copy_text="payload")]
    )._pending_children[0]

    assert any(isinstance(child, RightBlock) for child in row._pending_children)
    assert any(isinstance(child, CopyButton) for child in row._pending_children)


def test_a_child_inherits_its_parents_body_colour():
    parent = CollapsibleEntry(
        title="parent", body=["detail"], body_colour="#ff0000", expanded=True,
        children=[CollapsibleEntry(title="child", body=["more"], body_colour="")],
    )
    collapsible = build_collapsible_list([parent])._pending_children[0]
    child = collapsible._contents_list[1]

    assert child._body_colour == "#ff0000"


def test_an_entry_body_can_include_widgets_directly():
    widget = Static("already built")
    entry = CollapsibleEntry(title="with widget", body=[widget], expanded=True)
    collapsible = build_collapsible_list([entry])._pending_children[0]

    assert collapsible._contents_list[0] is widget


class _JsonTreeApp(App):
    def compose(self) -> ComposeResult:
        yield JsonTree(
            "Response body",
            {
                "productId": "0000018",
                "from": "2026-09-01",
                "cost": [],
                "consumption": [
                    {"type": "MOBILE_CALL", "amount": -1, "usage": 0},
                    {"type": "MOBILE_DATA", "amount": -1, "usage": 0},
                ],
            },
            collapsed=False,
        )


def test_json_value_keeps_scalars_visible_and_folds_nested_collections():
    entry = build_json_entry(
        "Response body",
        {
            "productId": "0000018",
            "from": "2026-09-01",
            "cost": [],
            "consumption": [
                {"type": "MOBILE_CALL", "amount": -1, "usage": 0},
                {"type": "MOBILE_DATA", "amount": -1, "usage": 0},
            ],
        },
    )
    inline = entry.body[0]
    children = entry.children

    assert isinstance(inline, Text)
    assert inline.plain == (
        "productId  0000018\n"
        "from       2026-09-01\n"
        "cost       []"
    )
    assert [child.title for child in children] == ["consumption   2 items"]
    assert [child.title for child in children[0].children] == [
        "0   MOBILE_CALL",
        "1   MOBILE_DATA",
    ]
    assert children[0].children[0].body[0].plain == (
        "type    MOBILE_CALL\namount  -1\nusage   0"
    )


def test_json_entry_exposes_pretty_json_for_copying():
    entry = build_json_entry("Response body", {"enabled": True}, expanded=True)

    assert entry.title == "Response body"
    assert entry.expanded is True
    assert entry.copy_label == "Response body"
    assert entry.copy_text == '{\n  "enabled": true\n}'


def test_json_tree_mounts_values_as_shared_collapsible_entries():
    captured = {}

    async def run():
        app = _JsonTreeApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            captured["entries"] = len(list(app.query(ListEntry)))

    asyncio.run(run())

    assert captured == {"entries": 2}
