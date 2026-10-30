"""The jira workspace: the open issue's card, the controls, and the reads and actions its handlers run.

Taking an issue, the JQL and the formatting are the jira plugin's, tested there.
"""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from titan_cli.core.mods import WORKSPACES, AIAnswer, ModBus, import_mod
from titan_cli.ui.components import AIResult
from titan_cli.ui.elements import Box, Button, Columns
from titan_cli.core.result import ClientError, ClientSuccess
from titan_plugin_jira.readers import issues as reader, models
from titan_plugin_jira.models import (
    UIJiraComment,
    UIJiraComponent,
    UIJiraFilter,
    UIJiraIssue,
    UIJiraProject,
    UIJiraStatus,
    UIJiraFieldOption,
    UIJiraTransition,
    UIJiraTransitionField,
    UIJiraVersion,
)

ws = import_mod(Path(__file__).resolve().parent.parent, kind=WORKSPACES)
draw = ws.draw

REGISTER_OPTIONS = {"project": "", "shown": 10, "refresh_seconds": 300, "plan_workflow": "", "take_status": ""}


def register_workspace(host, **options):
    """The workspace registered on a bus of its own kind and started, with the host it is given."""
    bus = ModBus(prefix="workspace.", store_dir="workspaces")
    for name, fn in {"dock": lambda *a: None, "toast": lambda *a: None}.items():
        if not hasattr(host, name):
            setattr(host, name, fn)
    bus.host = host
    ws.register(bus.api("jira"), bus.on_for("jira"), {**REGISTER_OPTIONS, **options})
    bus.start()
    return bus, bus.api("jira")


def render(bus, width=50):
    return bus.render_view("jira", width)

OPTIONS = {"plan_workflow": "plan-jira-issue", "take_status": "In Progress"}


def issue(status="Ready to Dev", description="line one", assignee="ANA GIL") -> UIJiraIssue:
    return UIJiraIssue(
        key="PROJ-1", id="1", summary="Do it", description=description, status=status, status_icon="🟡",
        status_category="To Do", issue_type="Task", issue_type_icon="✅", assignee=assignee, assignee_email=None,
        reporter="", priority="High", priority_icon="🔴", formatted_created_at="", formatted_updated_at="",
        labels=[], components=[], fix_versions=[], is_subtask=False, parent_key=None, subtask_count=0,
    )


def actions():
    return draw.CardActions(*(Mock() for _ in range(12)))


def card(i, unfolded=False, taking=None, comments=None, comments_open=False, act=None,
         transitions=None, move_open=False, moving=None, versions=None, fix_open=False, fixing=None, fix_released=False):
    return draw.issue_card(i, "https://x/browse/PROJ-1", OPTIONS, taking, unfolded,
                          comments, comments_open, act or actions(),
                          transitions, move_open, moving, versions, fix_open, fixing, fix_released)


def labels(box):
    return [c.label for c in box.children if isinstance(c, Button)]


def choices(box):
    """Every button in a choice card, wherever its layout put them (one row, a grid or a column)."""
    found = []
    for child in box.children:
        if isinstance(child, Button):
            found.append(child)
        elif isinstance(child, Box):
            found += choices(child)
    return found


def names(box):
    return [b.label.strip() for b in choices(box)]


def action_card(i, **kwargs):
    """The card of actions at the foot of the open issue."""
    return card(i, **kwargs).children[1].children[-1].children[0]


def test_the_card_reads_summary_people_description_then_actions_last():
    sections = card(issue()).children[1].children

    assert sections[0].parts == ("Do it",)
    assert labels(sections[2]) == ["▸ Description"]
    assert names(sections[-1].children[0]) == ["▶ Plan", "✋ Take", "▸ Move", "▸ Fix version"]


def test_an_issue_already_in_the_working_status_does_not_offer_take():
    assert names(action_card(issue(status="In Progress"))) == ["▶ Plan", "▸ Move", "▸ Fix version"]


def test_the_issue_being_taken_says_so():
    assert names(action_card(issue(), taking="PROJ-1"))[1] == "Taking…"


# -- moving an issue to another status ---------------------------------------

def transition(to_status, icon="🔵"):
    return UIJiraTransition(id=to_status, name=f"Go {to_status}", to_status=to_status, to_status_icon=icon)


def test_moving_offers_every_other_status_once_and_never_the_current_one():
    done = models.Transitions("done", [transition("Ready to Dev"), transition("In Progress"),
                                    transition("in progress"), transition("Done")])

    options = draw.move_options(issue(status="Ready to Dev"), done.items)

    assert [t.to_status for t in options] == ["In Progress", "Done"]


def test_the_move_button_unfolds_the_statuses_and_pressing_one_moves_the_issue():
    act = actions()
    done = models.Transitions("done", [transition("In Progress"), transition("Done")])

    sections = card(issue(), transitions=done, move_open=True, act=act).children[1].children
    picker, buttons = sections[-2], sections[-1].children[0]

    assert "▾ Move" in names(buttons)
    assert names(picker) == ["🔵 In Progress", "🔵 Done"]
    choices(picker)[1].on_press()
    assert act.move.call_args.args[1] == "Done"


def test_the_picker_says_so_while_loading_and_when_jira_fails():
    loading = card(issue(), transitions=models.Transitions("loading"), move_open=True).children[1].children[-2]
    failed = card(issue(), transitions=models.Transitions("error", error="403"), move_open=True).children[1].children[-2]

    assert loading.children[0].parts == ("Loading statuses…",)
    assert failed.border == "error" and [c.parts for c in failed.children[:2]] == [("Statuses",), ("403",)]


def test_a_closed_picker_adds_nothing_and_a_move_in_progress_blocks_the_buttons():
    assert draw.move_section(issue(), None, False, None, actions()) is None
    act = actions()
    busy = draw.move_section(issue(), models.Transitions("done", [transition("Done")]), True, "PROJ-1", act)

    choices(busy)[0].on_press()

    act.move.assert_not_called()
    assert "Moving…" in names(action_card(issue(), moving="PROJ-1"))


def version(name, released=False, id_="1"):
    return UIJiraVersion(
        id=id_, name=name, description="", released=released, start_date="Not set", release_date="Not set"
    )


def test_the_fix_version_picker_ticks_the_current_one_and_pressing_another_replaces_it():
    act = actions()
    current = issue()
    current.fix_versions.append("2.0")
    done = models.Versions("done", [version("1.0", True, "10"), version("2.0", False, "20"), version("3.0", False, "30")])

    sections = card(current, act=act, versions=done, fix_open=True).children[1].children
    picker, buttons = sections[-2], sections[-1].children[0]

    assert labels(picker) == ["☑ 2.0", "☐ 3.0", "✕ Clear"]
    assert "▾ Fix version" in names(buttons)
    picker.children[1].on_press()
    act.set_fix.assert_not_called()
    picker.children[2].on_press()
    assert act.set_fix.call_args.args[1].id == "30"
    picker.children[3].on_press()
    assert act.set_fix.call_args.args[1] is None


def test_the_fix_version_picker_warns_that_pressing_one_replaces_every_current_version():
    many = issue()
    many.fix_versions.extend(["2.1", "2.2"])
    done = models.Versions("done", [version("2.1"), version("2.2"), version("3.0")])

    picker = draw.fix_version_section(many, done, True, None, actions())

    assert picker.children[1].parts == ("Pressing one replaces all 2 current versions",)


def test_the_released_switch_sits_beside_the_title_and_swaps_the_list():
    act = actions()
    done = models.Versions("done", [version("1.0", True, "10"), version("2.0", False, "20")])

    unreleased = draw.fix_version_section(issue(), done, True, None, act, released=False)
    released = draw.fix_version_section(issue(), done, True, None, act, released=True)

    title = unreleased.children[0]
    assert title.row and title.children[0].parts == ("Fix version",) and title.children[1].label == "○ Released"
    assert labels(unreleased) == ["☐ 2.0"] and released.children[0].children[1].label == "◉ Released"
    assert labels(released) == ["☐ 1.0"]
    title.children[1].on_press()
    act.toggle_released.assert_called_once()


def test_the_card_says_which_fix_version_the_issue_has_or_that_it_has_none():
    with_version = issue()
    with_version.fix_versions.extend(["26.42", "26.43"])

    def line(i):
        return card(i).children[1].children[1].children[2]

    assert line(with_version).parts == ("🏷 ", "26.42, 26.43")
    assert line(issue()).parts == ("🏷 No fix version",)


def test_the_fix_version_picker_says_so_while_loading_failing_or_empty_and_blocks_while_busy():
    def picker(versions, fixing=None):
        return draw.fix_version_section(issue(), versions, True, fixing, actions())

    assert picker(models.Versions("loading")).children[0].parts == ("Loading versions…",)
    failed = picker(models.Versions("error", error="403"))
    assert failed.border == "error" and [c.parts for c in failed.children[:2]] == [("Versions",), ("403",)]
    assert picker(models.Versions("done")).children[0].parts == ("This project has no versions",)
    assert draw.fix_version_section(issue(), None, False, None, actions()) is None
    act = actions()
    busy = draw.fix_version_section(issue(), models.Versions("done", [version("1.0")]), True, "PROJ-1", act)
    busy.children[1].on_press()
    act.set_fix.assert_not_called()


def test_fix_version_reads_the_project_versions_when_opened_and_sets_the_one_pressed():
    runs, toasts = [], []
    jira = Mock(project_key="PROJ")
    jira.list_project_versions.return_value = ClientSuccess(data=[version("1.0", id_="10")])
    jira.set_fix_version.return_value = ClientSuccess(data=None, message="Set fixVersion of PROJ-1")
    jira.search_issues.return_value = ClientSuccess(data=[])
    host = SimpleNamespace(
        open_pane=lambda *a: None, every=lambda *a: None, repaint=lambda mod: None,
        run=lambda mod, fn: runs.append(fn), client=lambda name: jira,
        ai_describe=lambda mod: "Claude · opus", toast=lambda mod, text, severity: toasts.append((text, severity)),
    )
    bus, m = register_workspace(host, **{"project": "", "shown": 10, "refresh_seconds": 300, "plan_workflow": "", "take_status": ""})
    m.state.set("ready", models.Ready("q", [issue()], "PROJ"))
    m.state.set("selected", "PROJ-1")

    def buttons(element):
        if isinstance(element, Button):
            yield element
        for child in getattr(element, "children", ()) or ():
            if child:
                yield from buttons(child)

    next(b for b in buttons(render(bus)) if b.label == "▸ Fix version").on_press()
    runs.pop()()
    assert m.state.get("versions")["PROJ"].status == "done"
    jira.list_project_versions.assert_called_once_with("PROJ")

    runs.clear()
    next(b for b in buttons(render(bus)) if b.label == "☐ 1.0").on_press()
    runs.pop()()

    jira.set_fix_version.assert_called_once_with("PROJ-1", "10")
    assert toasts == [("Set fixVersion of PROJ-1", "information")]
    assert m.state.get("fixing") is None and m.state.get("fix_open") is None


def test_the_unfolded_description_shows_its_lines():
    body = card(issue(), unfolded=True).children[1].children[2].children[1]

    assert isinstance(body, Box) and body.children[0].parts == ("line one",)


def test_an_issue_without_description_has_no_toggle():
    assert draw.description(issue(description="No description"), False, Mock()) is None


# -- status and filters, read from Jira --------------------------------------

def status(name, category="To Do"):
    return UIJiraStatus(id=name, name=name, description="", category=category, icon="🟡")


def project(key, name=""):
    return UIJiraProject(id=key, key=key, name=name or key, description="", project_type="software",
                         lead_name="", issue_types=[])


CHOICES = models.Choices(
    statuses=[status("Ready to Dev"), status("Done", "Done")],
    components=[UIJiraComponent("1", "Android", ""), UIJiraComponent("2", "iOS", "")],
    filters=[UIJiraFilter("10023", "Sprint", "sprint in openSprints() ORDER BY Rank", "")],
    projects=[project("ECAPP"), project("ESHOP")],
)


def test_default_projects_prefers_the_option_then_the_plugins_default_then_none():
    assert reader.default_projects(Mock(project_key="PROJ"), {"project": "ECAPP, ESHOP"}) == ["ECAPP", "ESHOP"]
    assert reader.default_projects(Mock(project_key="PROJ"), {"project": ""}) == ["PROJ"]
    assert reader.default_projects(Mock(project_key=""), {"project": ""}) == []
    assert reader.default_projects(None, {"project": ""}) == []


def test_no_filter_adds_no_condition_and_no_status_means_any():
    jira = Mock(project_key="PROJ")
    jira.search_issues.return_value = ClientSuccess(data=[])

    ready = reader.read_ready(jira, {"project": "", "shown": 10}, [], [], CHOICES, ["PROJ"])

    assert ready.query == 'project = "PROJ" ORDER BY key ASC'


def test_several_projects_are_or_ed():
    jira = Mock(project_key="PROJ")
    jira.search_issues.return_value = ClientSuccess(data=[])

    ready = reader.read_ready(jira, {"project": "", "shown": 10}, [], [], CHOICES, ["ECAPP", "ESHOP"])

    assert ready.query == 'project in ("ECAPP", "ESHOP") ORDER BY key ASC'
    assert ready.project == "ECAPP, ESHOP"


def test_search_fields_adds_the_parent_link_field_when_the_site_has_one():
    jira = Mock()
    jira.get_parent_link_field_id.return_value = ClientSuccess(data="customfield_10100")
    assert reader.search_fields(jira) == [*reader.FIELDS, "customfield_10100"]


def test_search_fields_falls_back_when_the_site_has_none_or_the_lookup_fails():
    jira = Mock()
    jira.get_parent_link_field_id.return_value = ClientSuccess(data=None)
    assert reader.search_fields(jira) == reader.FIELDS

    jira.get_parent_link_field_id.return_value = ClientError(error_message="boom")
    assert reader.search_fields(jira) == reader.FIELDS


def test_read_ready_requests_the_parent_link_field_in_its_search():
    jira = Mock(project_key="PROJ")
    jira.get_parent_link_field_id.return_value = ClientSuccess(data="customfield_10100")
    jira.search_issues.return_value = ClientSuccess(data=[])

    reader.read_ready(jira, {"project": "", "shown": 10}, [], [], CHOICES, ["PROJ"])

    jira.search_issues.assert_called_once_with(
        'project = "PROJ" ORDER BY key ASC', max_results=11, fields=[*reader.FIELDS, "customfield_10100"]
    )


def test_find_issue_returns_the_matching_issue_or_none():
    a, b = issue(), issue()
    a.key, b.key = "PROJ-1", "PROJ-2"

    assert reader.find_issue([a, b], "PROJ-2") is b
    assert reader.find_issue([a, b], "PROJ-9") is None
    assert reader.find_issue([], "PROJ-1") is None


def test_components_are_or_ed_and_the_rest_and_ed_without_their_order():
    filters = ["mine", "component:Android", "component:iOS", "filter:10023"]

    assert reader.conditions(filters, CHOICES) == [
        "assignee = currentUser()",
        'component in ("Android", "iOS")',
        "sprint in openSprints()",
    ]


def test_a_saved_filter_no_longer_starred_drops_out():
    assert reader.conditions(["filter:999"], CHOICES) == []


def test_a_search_query_complements_filters_as_an_exact_key_or_free_text():
    assert reader.conditions(["mine"], CHOICES, "ECAPP-2268") == [
        "assignee = currentUser()",
        'key = "ECAPP-2268"',
    ]
    assert reader.conditions([], CHOICES, "login crash") == ['text ~ "login* crash*"']
    assert reader.conditions([], CHOICES, "  ") == []


def test_a_bare_number_is_searched_across_the_selected_projects():
    assert reader.conditions([], CHOICES, "2268", ["ECAPP", "ESHOP"]) == ['key in ("ECAPP-2268", "ESHOP-2268")']
    assert reader.conditions([], CHOICES, "ESHOPP-2268", ["ECAPP", "ESHOP"]) == ['key in ("ECAPP-2268", "ESHOP-2268")']


def test_choices_come_from_jira_ordered_by_category_and_a_failed_read_offers_nothing():
    jira = Mock()
    jira.list_statuses.return_value = ClientSuccess(data=[status("Done", "Done"), status("Doing", "In Progress"), status("Todo")])
    jira.list_components.return_value = ClientError(error_message="403")
    jira.list_favourite_filters.return_value = ClientSuccess(data=CHOICES.filters)

    choices = reader.read_choices(jira, ["PROJ"])

    assert [s.name for s in choices.statuses] == ["Todo", "Doing", "Done"]
    assert choices.components == [] and choices.filters == CHOICES.filters


def test_a_failed_read_keeps_the_previous_offer_or_marks_it_unknown():
    jira = Mock()
    jira.list_statuses.return_value = ClientSuccess(data=[status("Todo")])
    jira.list_components.return_value = ClientSuccess(data=[])
    jira.list_favourite_filters.return_value = ClientSuccess(data=[])
    jira.list_projects.return_value = ClientError(error_message="boom")

    first = reader.read_choices(jira, ["ECAPP"])
    assert first.unknown == frozenset({"projects"})

    jira.list_projects.return_value = ClientSuccess(data=[project("ECAPP")])
    loaded = reader.read_choices(jira, ["ECAPP"], first)
    assert loaded.unknown == frozenset() and [p.key for p in loaded.projects] == ["ECAPP"]

    jira.list_projects.return_value = ClientError(error_message="boom")
    again = reader.read_choices(jira, ["ECAPP"], loaded)
    assert again.unknown == frozenset() and [p.key for p in again.projects] == ["ECAPP"]


def test_picks_survive_an_unknown_offer_and_projects_match_case_insensitively():
    def state(choices, **store):
        return SimpleNamespace(
            store=SimpleNamespace(get=lambda key, default=None: store.get(key, default)),
            state=SimpleNamespace(get=lambda key, default=None: choices if key == "choices" else default),
        )

    unknown = models.Choices(unknown=frozenset({"projects", "statuses", "components", "filters"}))
    m = state(unknown, projects=["ecapp"], statuses=["Done"], filters=["component:iOS", "filter:1", "mine"])
    assert ws.active_projects(m) == ["ecapp"]
    assert ws.active_statuses(m) == ["Done"]
    assert ws.active_filters(m) == ["component:iOS", "filter:1", "mine"]

    m = state(CHOICES, projects=["ecapp", "GONE"], statuses=["Gone"], filters=["component:Nope"])
    assert ws.active_projects(m) == ["ECAPP"]
    assert ws.active_statuses(m) == []
    assert ws.active_filters(m) == []


def test_projects_are_offered_alphabetically():
    jira = Mock()
    jira.list_favourite_filters.return_value = ClientSuccess(data=[])
    jira.list_projects.return_value = ClientSuccess(data=[project("ESHOP"), project("ECAPP")])

    choices = reader.read_choices(jira, [])

    assert [p.key for p in choices.projects] == ["ECAPP", "ESHOP"]


def test_several_projects_merge_their_statuses_and_components_deduped_by_name():
    def statuses_for(key):
        return ClientSuccess(data=[status("To Do"), status(f"{key} only")])

    def components_for(key):
        return ClientSuccess(data=[UIJiraComponent("1", "Shared", ""), UIJiraComponent("2", f"{key} only", "")])

    jira = Mock()
    jira.list_statuses.side_effect = statuses_for
    jira.list_components.side_effect = components_for
    jira.list_favourite_filters.return_value = ClientSuccess(data=[])

    choices = reader.read_choices(jira, ["ECAPP", "ESHOP"])

    assert sorted(s.name for s in choices.statuses) == ["ECAPP only", "ESHOP only", "To Do"]
    assert sorted(c.name for c in choices.components) == ["ECAPP only", "ESHOP only", "Shared"]


def test_without_a_project_only_starred_filters_are_offered():
    jira = Mock()
    jira.list_favourite_filters.return_value = ClientSuccess(data=[])

    choices = reader.read_choices(jira, [])

    jira.list_statuses.assert_not_called()
    assert choices.statuses == []


def test_closed_drop_downs_say_what_is_picked():
    status_line = draw.status_control([], CHOICES, False, Mock(), Mock())
    filters_line = draw.filters_control(["mine", "component:iOS", "filter:10023"], CHOICES, False, Mock(), Mock())

    assert status_line.children[0].label == "Status   ▸ Any"
    assert filters_line.children[0].label == "Filters  ▸ Mine · iOS · Sprint"
    assert len(status_line.children) == 1  # closed: no options


def _rows(box):
    """What an open drop-down holds under its line: a text, or a row of checkboxes (as their labels)."""
    return [[b.label.strip() for b in c.children if isinstance(b, Button)] if isinstance(c, (Columns, Box)) and not hasattr(c, "parts")
            else c.parts[0] for c in box.children[1].children if c]


def test_the_open_status_drop_down_offers_jiras_statuses_as_checkboxes():
    toggle = Mock()
    box = draw.status_control(["Done"], CHOICES, True, Mock(), toggle, width=120)

    assert _rows(box) == [["☐ 🟡 Ready to Dev", "☑ 🟡 Done"]]
    next(b for b in _buttons(box) if "Ready to Dev" in b.label).on_press()
    toggle.assert_called_once_with("Ready to Dev")


def test_the_open_filters_drop_down_groups_components_and_starred_filters():
    box = draw.filters_control([], CHOICES, True, Mock(), Mock(), width=120)

    assert _rows(box) == [["☐ Mine"], "Components", ["☐ Android", "☐ iOS"], "Starred filters", ["☐ Sprint"]]


def test_checkboxes_fill_rows_as_wide_as_the_window_allows_and_stack_when_narrow():
    boxes = [(f"☐ Component {i}", Mock(), True) for i in range(7)]

    wide = draw.checkbox_grid(boxes, 100)
    narrow = draw.checkbox_grid(boxes, 20)

    per_row = len(wide[0].children)
    assert per_row > 1 and sum(len(_pressables(r)) for r in wide) == 7
    assert narrow[0].children[0].label == "☐ Component 0"  # a plain list: one column
    assert len(narrow) == 1 and len(_pressables(narrow[0])) == 7 and not isinstance(narrow[0], Columns)


def test_every_row_of_a_grid_has_the_same_number_of_equal_columns_even_the_short_last_one():
    boxes = [(f"☐ Component {i}", Mock(), True) for i in range(7)]

    rows = draw.checkbox_grid(boxes, 100)

    assert len(rows) > 1 and all(isinstance(r, Columns) for r in rows)
    assert len({len(r.children) for r in rows}) == 1
    assert len({r.ratio for r in rows}) == 1 and set(rows[0].ratio) == {1}
    assert len(_pressables(rows[-1])) < len(rows[-1].children)  # padded with empty cells


def _pressables(element):
    return [c for c in element.children if isinstance(c, Button)]


def test_the_screen_gives_the_open_drop_downs_more_columns_the_wider_it_is():
    bus, w = register_workspace(_host(None, []))
    many = models.Choices(components=[UIJiraComponent(str(i), f"Component {i}", "") for i in range(20)])
    w.state.set("choices", many)
    w.state.set("open_control", "filters")

    def widest_row(width):
        return max((len(r.children) for r in _all_rows(render(bus, width))), default=0)

    assert widest_row(160) > widest_row(60) > 0
    assert widest_row(24) == 0  # too narrow for two cells: a plain list, no grid rows


def _all_rows(element):
    if isinstance(element, Columns) and any(isinstance(c, Button) for c in element.children):
        yield element
    for child in getattr(element, "children", ()) or ():
        if child:
            yield from _all_rows(child)


# -- description preview, comments, AI summary ---------------------------------


def comment(body, author="ANA GIL"):
    return UIJiraComment("1", author, None, body, "01/01/2026 10:00:00", None)


def texts(box):
    return [c.parts[0] if hasattr(c, "parts") else c.label for c in box.children if c]


def test_a_folded_description_previews_its_first_lines():
    folded = draw.description(issue(description="one\n\ntwo\nthree"), False, Mock())

    assert texts(folded.children[1]) == ["one", "two", "…"]


def test_an_issue_without_comments_shows_no_comments_fold():
    assert draw.comments_section("PROJ-1", models.Comments("done", []), False, Mock(), Mock()) is None
    assert texts(draw.comments_section("PROJ-1", None, False, Mock(), Mock())) == ["Comments…"]


def test_open_comments_show_who_said_what():
    box = draw.comments_section("PROJ-1", models.Comments("done", [comment("Mejor\n\nsolo Android")]), True, Mock(), Mock())

    assert box.children[0].label == "▾ Comments (1)"
    first = box.children[1].children[0]
    assert first.children[0].parts[0].parts == ("Ana Gil",)
    assert texts(first)[1:] == ["Mejor", " ", "solo Android"]


def test_a_done_summary_is_framed_with_its_model_and_can_be_copied():
    copied = []
    m = ModBus(prefix="workspace.", store_dir="workspaces").api("jira")
    m.ui.copy = lambda text, what: copied.append((text, what))
    m.state.set("ai:summary:PROJ-1", AIResult("done", "Qué: X", "opus", value=("Qué: X",)))
    m.state.set("ai:who", "Claude · opus")

    box = draw.summary_section(m, issue(), lambda m: None)

    assert [b.label for b in box.children[0].children] == ["✦ Summarize again", "⟳ Claude · opus"]
    framed = box.children[1]
    assert texts(framed)[1] == "Qué: X"
    framed.children[-1].on_press()
    assert copied == [("Qué: X", "answer")]


def test_a_running_summary_cannot_be_started_twice():
    started = []
    m = ModBus(prefix="workspace.", store_dir="workspaces").api("jira")
    m.state.set("ai:summary:PROJ-1", AIResult("running", model="opus"))

    box = draw.summary_section(m, issue(), lambda m: started.append(True))

    button = box.children[0].children[0]
    assert button.label == "… summarizing with opus"
    button.on_press()
    assert started == []


def test_summarize_reads_the_comments_first_and_sends_them_to_the_ai():
    prompts, runs = [], []
    jira = Mock(project_key="PROJ")
    jira.get_comments.return_value = ClientSuccess(data=[comment("Al final solo Android")])
    host = SimpleNamespace(
        open_pane=lambda *a: None, every=lambda *a: None, repaint=lambda mod: None,
        run=lambda mod, fn: runs.append(fn), client=lambda name: jira,
        ai_describe=lambda mod: "Claude · opus",
        ai=lambda mod, prompt, system, max_tokens, model, timeout: prompts.append(prompt) or AIAnswer("Qué: X", "opus"),
    )
    bus, m = register_workspace(host, **{"project": "", "shown": 10, "refresh_seconds": 300, "plan_workflow": "", "take_status": ""})
    m.state.set("ready", models.Ready("q", [issue()], "PROJ"))
    m.state.set("selected", "PROJ-1")

    tree = render(bus)

    def buttons(element):
        if isinstance(element, Button):
            yield element
        for child in getattr(element, "children", ()) or ():
            if child:
                yield from buttons(child)

    summarize_button = next(b for b in buttons(tree) if b.label == "✦ Summarize")
    runs.clear()
    summarize_button.on_press()
    runs[-1]()

    assert "Al final solo Android" in prompts[0]
    done = m.state.get("ai:summary:PROJ-1")
    assert (done.status, done.text, done.model) == ("done", "Qué: X", "opus")


def test_move_reads_the_statuses_when_opened_and_transitions_to_the_one_pressed():
    runs, toasts = [], []
    jira = Mock(project_key="PROJ")
    jira.get_transitions.return_value = ClientSuccess(data=[transition("In Progress"), transition("Done")])
    jira.transition_issue.return_value = ClientSuccess(data=None, message="Transitioned PROJ-1 to Done")
    jira.search_issues.return_value = ClientSuccess(data=[])
    host = SimpleNamespace(
        open_pane=lambda *a: None, every=lambda *a: None, repaint=lambda mod: None,
        run=lambda mod, fn: runs.append(fn), client=lambda name: jira,
        ai_describe=lambda mod: "Claude · opus", toast=lambda mod, text, severity: toasts.append((text, severity)),
    )
    bus, m = register_workspace(host, **{"project": "", "shown": 10, "refresh_seconds": 300, "plan_workflow": "", "take_status": ""})
    m.state.set("ready", models.Ready("q", [issue()], "PROJ"))
    m.state.set("selected", "PROJ-1")

    def buttons(element):
        if isinstance(element, Button):
            yield element
        for child in getattr(element, "children", ()) or ():
            if child:
                yield from buttons(child)

    next(b for b in buttons(render(bus)) if b.label == "▸ Move").on_press()
    runs.pop()()
    assert m.state.get("transitions")["PROJ-1"].status == "done"

    runs.clear()
    next(b for b in buttons(render(bus)) if b.label == "🔵 Done").on_press()
    runs.pop()()

    jira.transition_issue.assert_called_once_with("PROJ-1", "Done")
    assert toasts == [("Transitioned PROJ-1 to Done", "information")]
    assert m.state.get("moving") is None and m.state.get("move_open") is None


def test_one_issue_beyond_the_limit_is_read_to_know_there_is_more():
    jira = Mock(project_key="PROJ")
    jira.issue_url.return_value = "u"
    jira.search_issues.return_value = ClientSuccess(data=[issue() for _ in range(4)])

    ready = reader.read_ready(jira, {"project": "", "shown": 3}, [], [], CHOICES)

    assert jira.search_issues.call_args.kwargs["max_results"] == 4
    assert len(ready.issues) == 3 and ready.more

    jira.search_issues.return_value = ClientSuccess(data=[issue() for _ in range(3)])
    assert not reader.read_ready(jira, {"project": "", "shown": 3}, [], [], CHOICES).more


def test_show_all_reads_everything_jira_returns_in_one_search_and_a_filter_resets_it():
    runs = []
    jira = Mock(project_key="PROJ")
    jira.issue_url.return_value = "u"
    jira.list_statuses.return_value = ClientSuccess(data=[])
    jira.list_components.return_value = ClientSuccess(data=[])
    jira.list_favourite_filters.return_value = ClientSuccess(data=[])
    jira.search_issues.return_value = ClientSuccess(data=[issue() for _ in range(3)])
    host = SimpleNamespace(
        open_pane=lambda *a: None, every=lambda *a: None, repaint=lambda mod: None,
        run=lambda mod, fn: runs.append(fn), client=lambda name: jira, ai_describe=lambda mod: "x",
    )
    bus, m = register_workspace(host, **{"project": "", "shown": 2, "refresh_seconds": 300, "plan_workflow": "", "take_status": ""})

    def buttons(element):
        if isinstance(element, Button):
            yield element
        for child in getattr(element, "children", ()) or ():
            if child:
                yield from buttons(child)

    m.state.set("ready", models.Ready("q", [issue(), issue()], "PROJ", more=True))
    next(b for b in buttons(render(bus)) if b.label == "＋ Show all").on_press()
    runs.pop()()

    assert jira.search_issues.call_args.kwargs["max_results"] == reader.SHOW_ALL + 1
    assert "＋ Show all" not in [b.label for b in buttons(render(bus))]


def test_a_refresh_keeps_the_list_on_screen_so_the_pane_does_not_jump_to_the_top():
    bus, m = register_workspace(SimpleNamespace(every=lambda *a: None, repaint=lambda mod: None,
                                                run=lambda mod, fn: None, client=lambda name: None,
                                                ai_describe=lambda mod: "x"))
    m.state.set("ready", models.Ready("q", [issue()], "PROJ"))
    m.state.set("loading", True)

    tree = render(bus)

    def texts(element):
        if isinstance(element, str):
            yield element
        for part in getattr(element, "parts", ()) or ():
            yield from texts(part)
        for child in getattr(element, "children", ()) or ():
            yield from texts(child)
        if isinstance(element, Button):
            yield element.label

    shown = " ".join(texts(tree))
    assert "PROJ-1" in shown and "PROJ · loading…" in shown and "Loading…" not in shown.replace("loading…", "")


def test_matching_projects_filters_by_key_or_name_case_insensitively():
    projects = [project("ECAPP", "App Android"), project("ESHOP", "Tienda")]

    assert draw.matching_projects(projects, "") == projects
    assert draw.matching_projects(projects, "ecapp") == [projects[0]]
    assert draw.matching_projects(projects, "tienda") == [projects[1]]
    assert draw.matching_projects(projects, "nope") == []


def test_a_search_ignores_status_and_filters_and_looks_through_the_whole_projects():
    jira = Mock(project_key="PROJ")
    jira.search_issues.return_value = ClientSuccess(data=[])

    ready = reader.read_ready(jira, {"project": "", "shown": 10}, ["Done"], ["mine", "component:iOS"], CHOICES,
                           ["ECAPP", "ESHOP"], "2268")

    assert ready.query == ('project in ("ECAPP", "ESHOP") AND (key in ("ECAPP-2268", "ESHOP-2268")) '
                           'ORDER BY key ASC')


def test_a_failed_read_inside_an_open_issue_is_an_error_card_with_copy():
    copied = []

    def copy(text, what):
        copied.append((what, text))

    for box in (
        draw.comments_section("PROJ-1", models.Comments("error", error="HTTP 403"), False, Mock(), copy),
        draw.parent_section("PROJ-0", models.Parent("error", error="HTTP 404"), copy),
    ):
        assert box.border == "error"
        next(b for b in choices(box) if b.label == "⧉ Copy error").on_press()
    assert copied == [("error", "Comments\nHTTP 403"), ("error", "⬆ PROJ-0\nHTTP 404")]


def _host(jira, runs, docks=None, ticks=None):
    return SimpleNamespace(
        dock=lambda mod, slot: (docks if docks is not None else []).append(slot.label),
        every=lambda mod, seconds, fn, immediately: (ticks if ticks is not None else []).append(fn),
        repaint=lambda mod: None, run=lambda mod, fn: runs.append(fn), client=lambda name: jira,
        ai_describe=lambda mod: "x", toast=lambda *a: None,
    )


def test_the_dock_tile_and_the_timer_appear_only_once_the_screen_exists():
    docks, ticks = [], []
    bus = ModBus(prefix="workspace.", store_dir="workspaces")
    bus.host = _host(None, [], docks, ticks)
    ws.register(bus.api("jira"), bus.on_for("jira"), dict(REGISTER_OPTIONS))
    assert docks == [] and ticks == []

    bus.start()

    assert docks == ["Jira"] and len(ticks) == 1


def test_opening_on_an_issue_of_the_list_selects_it_and_reads_its_comments():
    runs = []
    jira = Mock(project_key="PROJ")
    jira.get_comments.return_value = ClientSuccess(data=[])
    bus, w = register_workspace(_host(jira, runs))
    w.state.set("ready", models.Ready("q", [issue()], "PROJ"))

    bus.opened("jira", {"issue": "PROJ-1"})
    while runs:  # opening queues the selection, which queues the comments' read
        runs.pop(0)()

    assert w.state.get("selected") == "PROJ-1"
    assert w.state.get("comments")["PROJ-1"].status == "done"


def test_opening_on_an_issue_the_filters_hide_searches_for_it_exactly():
    runs = []
    jira = Mock(project_key="PROJ")
    jira.issue_url.return_value = "u"
    jira.get_parent_link_field_id.return_value = ClientSuccess(data=None)
    jira.get_comments.return_value = ClientSuccess(data=[])
    jira.search_issues.return_value = ClientSuccess(data=[issue()])
    bus, w = register_workspace(_host(jira, runs))
    w.state.set("ready", models.Ready("q", [], "PROJ"))

    bus.opened("jira", {"issue": "PROJ-1"})
    while runs:
        runs.pop(0)()

    assert w.store.get("search") == "PROJ-1" and w.state.get("selected") == "PROJ-1"
    assert "PROJ-1" in jira.search_issues.call_args.args[0]


def test_opening_from_the_dock_or_with_an_unknown_focus_changes_nothing():
    runs = []
    bus, w = register_workspace(_host(None, runs))
    runs.clear()  # what starting queued is not what opening does

    for focus in (None, "x", {"pr": 3}):
        bus.opened("jira", focus)

    assert runs == [] and w.state.get("selected") is None


def test_a_finished_workflow_rereads_the_list_off_its_thread_but_a_nested_one_does_not():
    from titan_cli.core.mods import WorkflowRun

    runs = []
    jira = Mock(project_key="PROJ")
    jira.issue_url.return_value = "u"
    jira.get_parent_link_field_id.return_value = ClientSuccess(data=None)
    jira.search_issues.return_value = ClientSuccess(data=[issue()])
    bus, w = register_workspace(_host(jira, runs))
    runs.clear()

    bus.dispatch("workflow.run", WorkflowRun("plan-jira-issue", "plugin", nested=True), lambda e: None)
    assert runs == []

    bus.dispatch("workflow.run", WorkflowRun("plan-jira-issue", "plugin", nested=False), lambda e: None)
    assert w.state.get("ready") is None  # not on the workflow's thread
    runs.pop()()
    assert [i.key for i in w.state.get("ready").issues] == ["PROJ-1"]


def test_plan_runs_the_plan_workflow_on_that_issue():
    ran = []
    host = _host(None, [])
    host.run_workflow = lambda mod, name, params: ran.append((name, params))
    bus, w = register_workspace(host, plan_workflow="plan-jira-issue")
    w.state.set("ready", models.Ready("q", [issue()], "PROJ"))
    w.state.set("selected", "PROJ-1")

    next(b for b in _buttons(render(bus)) if b.label == "▶ Plan").on_press()

    assert ran == [("plan-jira-issue", {"jira_issue_key": "PROJ-1"})]


def test_the_screen_gives_the_list_and_the_card_two_columns_when_wide_and_stacks_them_when_narrow():
    from titan_cli.ui.elements import Columns

    bus, w = register_workspace(_host(None, []))
    w.state.set("ready", models.Ready("q", [issue()], "PROJ"))
    w.state.set("selected", "PROJ-1")

    wide, narrow = render(bus, 160), render(bus, 80)

    assert any(isinstance(c, Columns) for c in wide.children)
    assert not any(isinstance(c, Columns) for c in narrow.children)


def _buttons(element):
    if isinstance(element, Button):
        yield element
    for child in getattr(element, "children", ()) or ():
        if child:
            yield from _buttons(child)


def test_a_failed_read_inside_the_open_issue_offers_a_retry_that_reads_it_again():
    runs = []
    jira = Mock(project_key="PROJ")
    jira.get_comments.return_value = ClientSuccess(data=[])
    bus, w = register_workspace(_host(jira, runs))
    w.state.set("ready", models.Ready("q", [issue()], "PROJ"))
    w.state.set("selected", "PROJ-1")
    w.state.set("comments", {"PROJ-1": models.Comments("error", error="HTTP 500")})
    w.state.set("move_open", "PROJ-1")
    w.state.set("transitions", {"PROJ-1": models.Transitions("error", error="HTTP 500")})
    runs.clear()

    retries = [b for b in _buttons(render(bus)) if b.label == "↻ Retry"]
    assert len(retries) == 2
    retries[0].on_press()
    runs.pop()()

    jira.get_comments.assert_called_once_with("PROJ-1")
    assert w.state.get("comments")["PROJ-1"].status == "done"


def _closing():
    t = UIJiraTransition(
        id="31", name="Close", to_status="Closed", to_status_icon="⚪",
        required_fields=[UIJiraTransitionField("resolution", "Resolution", True,
                                               [UIJiraFieldOption("1", "Done"), UIJiraFieldOption("2", "Won't Do")])],
    )
    return t, transition("In Progress")


def _move_world(jira):
    runs, toasts = [], []
    host = _host(jira, runs)
    host.toast = lambda mod, text, severity: toasts.append((text, severity))
    bus, w = register_workspace(host)
    w.state.set("ready", models.Ready("q", [issue()], "PROJ"))
    w.state.set("selected", "PROJ-1")
    w.state.set("move_open", "PROJ-1")
    w.state.set("transitions", {"PROJ-1": models.Transitions("done", list(_closing()))})
    return bus, w, runs, toasts


def test_moving_to_a_status_that_requires_a_resolution_offers_the_ones_jira_allows():
    jira = Mock(project_key="PROJ")
    bus, w, runs, _ = _move_world(jira)
    runs.clear()

    next(b for b in _buttons(render(bus)) if b.label == "⚪ Closed").on_press()

    assert runs == [] and w.state.get("resolving") == {"key": "PROJ-1", "status": "Closed"}
    labels = [b.label for b in _buttons(render(bus))]
    assert "Done" in labels and "Won't Do" in labels
    jira.transition_issue.assert_not_called()


def test_pressing_a_resolution_transitions_with_it_and_closes_both_pickers():
    jira = Mock(project_key="PROJ")
    jira.issue_url.return_value = "u"
    jira.get_parent_link_field_id.return_value = ClientSuccess(data=None)
    jira.search_issues.return_value = ClientSuccess(data=[])
    jira.transition_issue.return_value = ClientSuccess(data=None, message="Transitioned PROJ-1 to Closed")
    bus, w, runs, toasts = _move_world(jira)
    next(b for b in _buttons(render(bus)) if b.label == "⚪ Closed").on_press()
    runs.clear()

    next(b for b in _buttons(render(bus)) if b.label == "Won't Do").on_press()
    runs.pop()()

    jira.transition_issue.assert_called_once_with("PROJ-1", "Closed", resolution="Won't Do")
    assert toasts == [("Transitioned PROJ-1 to Closed", "information")]
    assert w.state.get("resolving") is None and w.state.get("move_open") is None


def test_a_status_that_needs_no_resolution_still_moves_at_once():
    jira = Mock(project_key="PROJ")
    jira.issue_url.return_value = "u"
    jira.get_parent_link_field_id.return_value = ClientSuccess(data=None)
    jira.search_issues.return_value = ClientSuccess(data=[])
    jira.transition_issue.return_value = ClientSuccess(data=None, message="ok")
    bus, w, runs, _ = _move_world(jira)
    w.state.set("transitions", {"PROJ-1": models.Transitions("done", [transition("Testing")])})
    runs.clear()

    next(b for b in _buttons(render(bus)) if b.label.endswith("Testing")).on_press()
    runs.pop()()

    jira.transition_issue.assert_called_once_with("PROJ-1", "Testing")
    assert w.state.get("resolving") is None


def test_an_issue_moved_out_of_the_picked_status_leaves_the_list_even_if_jiras_index_still_lists_it():
    jira = Mock(project_key="PROJ")
    jira.issue_url.return_value = "u"
    moved = issue(status="Closed")
    jira.search_issues.return_value = ClientSuccess(data=[issue(status="In progress"), moved])

    ready = reader.read_ready(jira, {"project": "", "shown": 10}, ["In Progress"], [], CHOICES, ["PROJ"])

    assert [i.status for i in ready.issues] == ["In progress"] and not ready.more


def test_without_a_picked_status_every_status_stays_and_a_search_ignores_the_pick():
    jira = Mock(project_key="PROJ")
    jira.issue_url.return_value = "u"
    jira.search_issues.return_value = ClientSuccess(data=[issue(status="Closed"), issue(status="Open")])

    assert len(reader.read_ready(jira, {"project": "", "shown": 10}, [], [], CHOICES, ["PROJ"]).issues) == 2
    assert len(reader.read_ready(jira, {"project": "", "shown": 10}, ["Done"], [], CHOICES, ["PROJ"], "text").issues) == 2
