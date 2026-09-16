"""Tests for the ExpandableList widget."""

import asyncio
from inspect import signature

from textual.app import App, ComposeResult
from textual.widgets import Collapsible, DataTable, Tree

from titan_cli.ui.tui.widgets import (
    ExpandableList,
    ExpandableListItem,
    JsonTree,
    JsonTreeDetail,
    Table,
)


class _ExpandableListApp(App):
    def compose(self) -> ComposeResult:
        yield ExpandableList(
            [
                ExpandableListItem(
                    title="deviceDealsFeaturedDevicesConfiguration",
                    subtitle="Yoigo · Orden de dispositivos destacados",
                    badge="JSON",
                    summary="default, Android - Dev",
                    detail_headers=["Entorno", "Valor", "Origen", "Editable"],
                    detail_rows=[
                        ["default", '{"smartphone": []}', "Literal", "si"],
                        ["Android - Dev", '{"smartphone": ["P09718P"]}', "Literal", "si"],
                    ],
                    detail_flex_column=1,
                    json_details=[
                        JsonTreeDetail(
                            "default",
                            {
                                "recommendedGroupIds": ["G075DGT"],
                                "smartphone": ["P09718P"],
                            },
                            collapsed=False,
                        )
                    ],
                    collapsed=False,
                )
            ],
            title="Valores por proyecto",
        )


def _mount_expandable_list():
    captured = {}

    async def run():
        app = _ExpandableListApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            collapsibles = list(app.query(Collapsible))
            wrapped_tables = list(app.query(Table))
            json_trees = list(app.query(JsonTree))
            trees = list(app.query(Tree))
            tables = list(app.query(DataTable))
            captured["collapsible_count"] = len(collapsibles)
            captured["wrapped_table_count"] = len(wrapped_tables)
            captured["json_tree_count"] = len(json_trees)
            captured["tree_count"] = len(trees)
            captured["table_count"] = len(tables)
            captured["collapsed"] = collapsibles[0].collapsed
            captured["flex_column"] = wrapped_tables[0].flex_column
            captured["row_count"] = tables[0].row_count
            captured["json_root_children"] = len(trees[0].root.children)

    asyncio.run(run())
    return captured


def test_expandable_list_mounts_collapsible_items_with_detail_tables():
    captured = _mount_expandable_list()

    assert captured == {
            "collapsible_count": 1,
            "wrapped_table_count": 1,
            "json_tree_count": 1,
            "tree_count": 1,
            "table_count": 1,
            "collapsed": False,
            "flex_column": 1,
            "row_count": 2,
            "json_root_children": 2,
        }


def test_expandable_list_is_a_valid_workflow_output_sink():
    """The facade accepts one item iterable and an optional title."""
    from titan_cli.ui.tui.textual_components import TextualComponents

    params = list(signature(TextualComponents.expandable_list).parameters)

    assert params == ["self", "items", "title"]
