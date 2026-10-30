"""The Jira screen's element tree, drawn from `w.state` only: it never waits on the network.

The controls (projects, status, filters, search) and the issue list sit on the left; the open
issue's card (description, comments, AI summary, move, fix version, actions) on the right. A
narrow window stacks them. Reading and acting are in `workspace.py`; this file only draws.
"""
from dataclasses import dataclass
from typing import Callable, List, Optional

from titan_cli.ui.components import (
    Option,
    ai_answer_box,
    ai_ask_button,
    ai_chip,
    choice_card,
    error_card,
)
from titan_cli.ui.elements import Box, Button, Columns, Input, Link, Text, responsive_columns
from titan_plugin_jira.models import UIJiraIssue, UIJiraProject, UIJiraTransition, UIJiraVersion
from titan_plugin_jira.operations import display_lines, format_person_name, issue_description_lines, resolution_field
from titan_plugin_jira.readers.issues import MINE, SHOW_ALL, component_id, filter_id, project_key
from titan_plugin_jira.readers.models import (
    Choices, Comments, Parent, Ready, Transitions, Versions,
)

DESCRIPTION_LINES = 200
PREVIEW_LINES = 2
COMMENT_LINES = 60
MAX_PROJECT_OPTIONS = 30  # a Jira instance can have hundreds of projects; rendering them all freezes Titan
# What an issue card's border and the results section's take off the pane's width.
CARD_INSET = 8


@dataclass
class CardActions:
    """What the open card's buttons do; the pane's `render` wires them to `m`."""
    select: Callable[[str], None]
    fold: Callable[[str], None]
    plan: Callable[[str], None]
    take: Callable[[UIJiraIssue], None]
    toggle_comments: Callable[[str], None]
    summary: Callable[[UIJiraIssue], Box]
    copy: Callable[[str, str], None]
    toggle_move: Callable[[str], None]
    move: Callable[[UIJiraIssue, str], None]
    toggle_fix: Callable[[UIJiraIssue], None]
    set_fix: Callable[[UIJiraIssue, Optional[UIJiraVersion]], None]
    toggle_released: Callable[[], None]
    retry: Optional[Callable[[str, str], None]] = None  # (what, key): read it again
    resolve: Optional[Callable[[UIJiraIssue, str, str], None]] = None  # (issue, status, resolution name)


def issue_line(issue: UIJiraIssue, selected: bool, select) -> Button:
    """One line per issue, led by the status colour the status filter uses; pressing it opens (or closes) its card."""
    return Button(f"{'▾' if selected else '▸'} {issue.status_icon} {issue.key} {issue.summary}", lambda: select(issue.key))


def description(issue: UIJiraIssue, unfolded: bool, fold) -> Optional[Box]:
    """Folded: its first lines as a preview. Unfolded: all of it in a frame, layout kept."""
    lines = issue_description_lines(issue, DESCRIPTION_LINES)
    if not lines:
        return None
    toggle = Button(f"{'▾' if unfolded else '▸'} Description", lambda: fold(issue.key), dim=not unfolded)
    if not unfolded:
        preview = [line for line in lines if line][:PREVIEW_LINES]
        more = len([line for line in lines if line]) > PREVIEW_LINES
        return Box(toggle, Box(*(Text(line.strip(), dim=True) for line in preview), more and Text("…", dim=True), indent=2))
    return Box(toggle, Box(*(Text(line or " ", wrap=True) for line in lines), border="subtle"))


def retry_actions(retry, what: str, key: str) -> list:
    """The Retry button of an error card, when the caller can read `what` of `key` again."""
    return [Button("↻ Retry", lambda: retry(what, key))] if retry else []


def parent_section(parent_key: Optional[str], parent: Optional[Parent], copy, retry=None) -> Optional[Box]:
    """A line naming the issue's parent, when it has one: its key, summary, status and a link."""
    if not parent_key:
        return None
    if parent is None or parent.status == "loading":
        return Box(Text(f"⬆ {parent_key} · loading…", dim=True))
    if parent.status == "error":
        return error_card(parent.error or "unknown error", copy=copy, title=f"⬆ {parent_key}", what="error",
                          actions=retry_actions(retry, "parent", parent_key))
    p = parent.issue
    return Box(
        Text(Text(f"⬆ {p.key} ", dim=True), Text(p.summary, wrap=True), Text(f" · {p.status_icon} {p.status}", dim=True)),
        parent.url and Text(Link("↗ Open", parent.url)),
    )


def comments_section(key: str, comments: Optional[Comments], is_open: bool, toggle, copy, retry=None) -> Optional[Box]:
    """A fold with the issue's comments, oldest first; nothing at all when it has none."""
    if comments is None or comments.status == "loading":
        return Box(Text("Comments…", dim=True))
    if comments.status == "error":
        return error_card(comments.error or "unknown error", copy=copy, title="Comments", what="error",
                          actions=retry_actions(retry, "comments", key))
    if not comments.items:
        return None
    toggle_button = Button(f"{'▾' if is_open else '▸'} Comments ({len(comments.items)})", lambda: toggle(key), dim=not is_open)
    if not is_open:
        return Box(toggle_button)
    return Box(
        toggle_button,
        Box(
            *(
                Box(
                    Text(Text(format_person_name(c.author_name), bold=True), Text(f" · {c.formatted_created_at}", dim=True)),
                    *(Text(line or " ", wrap=True) for line in display_lines(c.body, COMMENT_LINES)),
                )
                for c in comments.items
            ),
            gap=1,
            border="subtle",
        ),
    )


def summary_key(issue: UIJiraIssue) -> str:
    """Where the issue's summary lives in `m.state` (see `ask_ai`)."""
    return f"summary:{issue.key}"


def summary_section(m, issue: UIJiraIssue, work) -> Box:
    """The button that asks an AI what the issue asks for, who answers, and its last answer."""
    key = summary_key(issue)
    return Box(
        Box(
            ai_ask_button(m, key, work, "✦ Summarize", "✦ Summarize again", "… summarizing with"),
            ai_chip(m, "Jira issue summary"),
            row=True,
        ),
        ai_answer_box(m, key, "✦ Summary", render=lambda lines: [Text(line or " ", wrap=True) for line in lines]),
    )


def move_options(issue: UIJiraIssue, transitions: List[UIJiraTransition]) -> List[UIJiraTransition]:
    """The transitions that lead somewhere else, one per status (Jira may offer several to the same one)."""
    seen = {issue.status.strip().lower()}
    options = []
    for transition in transitions:
        status = transition.to_status.strip().lower()
        if status not in seen:
            seen.add(status)
            options.append(transition)
    return options




def move_section(issue: UIJiraIssue, transitions: Optional[Transitions], is_open: bool,
                 moving: Optional[str], act: CardActions, width: int = 40,
                 resolving: Optional[str] = None) -> Optional[Box]:
    """The statuses the open issue can move to; pressing one moves it. Nothing while the picker is closed."""
    if not is_open:
        return None
    if transitions is None or transitions.status == "loading":
        return Box(Text("Loading statuses…", dim=True), border="subtle")
    if transitions.status == "error":
        return error_card(transitions.error or "unknown error", copy=act.copy, title="Statuses", what="error",
                          actions=retry_actions(act.retry, "transitions", issue.key))
    busy = moving == issue.key
    field = resolution_field(transitions.items, resolving) if resolving else None
    if field:
        return choice_card(
            [Option(o.label, lambda label=o.label: None if busy else act.resolve(issue, resolving, label))
             for o in field.options],
            width=width - CARD_INSET,
            title=f"{field.name} for {resolving}",
        )
    options = move_options(issue, transitions.items)
    if not options:
        return Box(Text("Jira offers no other status from here", dim=True), border="subtle")
    return choice_card(
        [Option(f"{t.to_status_icon} {t.to_status}", lambda status=t.to_status: None if busy else act.move(issue, status))
         for t in options],
        width=width - CARD_INSET,
        title="Move to",
    )


def fix_version_options(versions: List[UIJiraVersion], released: bool) -> List[UIJiraVersion]:
    """The project's released versions, or the ones still to be released, in Jira's order."""
    return [v for v in versions if v.released == released]


def fix_version_section(issue: UIJiraIssue, versions: Optional[Versions], is_open: bool,
                        fixing: Optional[str], act: CardActions, released: bool = False) -> Optional[Box]:
    """
    The project's versions, released or not as the switch says; the issue's current ones are
    ticked; pressing an unticked one replaces them, pressing a ticked one does nothing.
    """
    if not is_open:
        return None
    if versions is None or versions.status == "loading":
        return Box(Text("Loading versions…", dim=True), border="subtle")
    if versions.status == "error":
        return error_card(versions.error or "unknown error", copy=act.copy, title="Versions", what="error",
                          actions=retry_actions(act.retry, "versions", project_key(issue.key)))
    if not versions.items:
        return Box(Text("This project has no versions", dim=True), border="subtle")
    busy = fixing == issue.key
    current = set(issue.fix_versions)

    def option(version: UIJiraVersion) -> Button:
        mark = "☑" if version.name in current else "☐"
        return Button(f"{mark} {version.name}",
                      lambda: None if busy or version.name in current else act.set_fix(issue, version),
                      dim=busy or version.name not in current)

    shown = fix_version_options(versions.items, released)
    return Box(
        Box(Text("Fix version", dim=True), Button(f"{'◉' if released else '○'} Released", act.toggle_released, dim=True),
            row=True),
        len(current) > 1 and Text(f"Pressing one replaces all {len(current)} current versions", dim=True, wrap=True),
        *(option(v) for v in shown),
        not shown and Text("No released versions" if released else "No unreleased versions", dim=True),
        current and Button("✕ Clear", lambda: None if busy else act.set_fix(issue, None), dim=True),
        border="subtle",
    )


def actions(issue: UIJiraIssue, url: str, options, taking: Optional[str], moving: Optional[str],
            move_open: bool, fix_open: bool, plan, take, toggle_move, toggle_fix, width: int = 40) -> Box:
    choices = []
    if options["plan_workflow"]:
        choices.append(Option("▶ Plan", lambda: plan(issue.key)))
    if options["take_status"] and issue.status.strip().lower() != options["take_status"].strip().lower():
        choices.append(Option("Taking…" if taking == issue.key else "✋ Take", lambda: take(issue)))
    choices.append(Option("Moving…" if moving == issue.key else f"{'▾' if move_open else '▸'} Move", lambda: toggle_move(issue.key)))
    choices.append(Option(f"{'▾' if fix_open else '▸'} Fix version", lambda: toggle_fix(issue)))
    return Box(choice_card(choices, width=width - CARD_INSET, title="Actions"), url and Text(Link("↗ Open", url)))


def issue_card(issue: UIJiraIssue, url: str, options, taking: Optional[str], unfolded: bool,
               comments: Optional[Comments], comments_open: bool,
               act: CardActions, transitions: Optional[Transitions] = None,
               move_open: bool = False, moving: Optional[str] = None, versions: Optional[Versions] = None,
               fix_open: bool = False, fixing: Optional[str] = None, fix_released: bool = False,
               parent: Optional[Parent] = None, width: int = 40, resolving: Optional[str] = None) -> Box:
    """
    The open issue: its line, summary, who has it, status, description, comments,
    the AI summary, the statuses it can move to once asked; the actions always last.
    """
    assignee = format_person_name(issue.assignee) if issue.assignee and issue.assignee != "Unassigned" else ""
    return Box(
        issue_line(issue, True, act.select),
        Box(
            Text(issue.summary, bold=True, wrap=True),
            Box(
                Text("👤 ", assignee or Text("Unassigned", dim=True)),
                Text(f"{issue.status_icon} {issue.status}", dim=True),
                Text("🏷 ", ", ".join(issue.fix_versions)) if issue.fix_versions else Text("🏷 No fix version", dim=True),
                issue.priority and Text(f"Priority: {issue.priority}", dim=True),
            ),
            parent_section(issue.parent_key, parent, act.copy, act.retry),
            description(issue, unfolded, act.fold),
            comments_section(issue.key, comments, comments_open, act.toggle_comments, act.copy, act.retry),
            act.summary(issue),
            move_section(issue, transitions, move_open, moving, act, width, resolving),
            fix_version_section(issue, versions, fix_open, fixing, act, fix_released),
            actions(issue, url, options, taking, moving, move_open, fix_open, act.plan, act.take,
                    act.toggle_move, act.toggle_fix, width),
            gap=1,
        ),
        border="primary",
    )


def filter_names(filters: List[str], choices: Optional[Choices]) -> List[str]:
    saved = {filter_id(f): f.name for f in (choices.filters if choices else [])}
    names = []
    for f in filters:
        if f == MINE:
            names.append("Mine")
        elif f.startswith("component:"):
            names.append(f.split(":", 1)[1])
        elif f in saved:
            names.append(saved[f])
    return names


def section(title, color: str, *body) -> Box:
    """A titled, bordered group - the same shape the github mod uses for its own sections."""
    return Box(title if isinstance(title, Text) else Text(title, bold=True, color=color), *body, border=color)


def dropdown(label: str, summary: str, is_open: bool, toggle, *options) -> Box:
    """A line with what is picked; pressing it unfolds the options under it."""
    return Box(
        Button(f"{label:<8} {'▾' if is_open else '▸'} {summary}", toggle, dim=not is_open),
        is_open and Box(*options, indent=11),
    )


# What a section's border and padding, and a dropdown's indent, take off the screen's width.
CONTROL_INSET = 4 + 11
# A checkbox cell is at least this wide: "☐ " and a short label.
CELL_MIN = 12


def checkbox_grid(buttons: List[tuple], width: int) -> List[Columns]:
    """
    `(label, on_press, dim)` checkboxes in rows of equal columns for `width` columns: as many
    as the longest label allows, down to a single one (a plain list) on a narrow window.
    Each row is `Columns` of the same ratio, so the cells line up from one row to the next
    (a short last row is padded with empty cells to keep them as wide as the others).
    """
    if not buttons:
        return []
    cell = max(CELL_MIN, max(len(label) for label, _, _ in buttons) + 2)
    columns = max(1, width // cell)
    if columns == 1:
        return [Box(*(Button(label, press, dim=dim) for label, press, dim in buttons))]
    rows = []
    for i in range(0, len(buttons), columns):
        row = [Button(label, press, dim=dim) for label, press, dim in buttons[i:i + columns]]
        row += [Text("")] * (columns - len(row))
        rows.append(Columns(*row, ratio=(1,) * columns, gap=0))
    return rows


def status_control(statuses: List[str], choices: Optional[Choices], is_open: bool, toggle, toggle_status,
                   width: int = 120) -> Box:
    def option(name: str, label: str) -> tuple:
        on = name in statuses
        return (f"{'☑' if on else '☐'} {label}", lambda: toggle_status(name), not on)

    available = choices.statuses if choices else []
    return dropdown(
        "Status", ", ".join(statuses) if statuses else "Any", is_open, toggle,
        *checkbox_grid([option(s.name, f"{s.icon} {s.name}") for s in available], width - CONTROL_INSET),
        choices is not None and not available and Text("No statuses: pick at least one project", dim=True),
    )


def matching_projects(available: List[UIJiraProject], filter_text: str) -> List[UIJiraProject]:
    needle = filter_text.strip().lower()
    if not needle:
        return available
    return [p for p in available if needle in p.key.lower() or needle in p.name.lower()]


def projects_control(projects: List[str], choices: Optional[Choices], is_open: bool, toggle,
                     draft: str, change_draft, submit_draft, toggle_project,
                     browse_open: bool, toggle_browse, filter_text: str, change_filter,
                     show_count: int, show_more_projects) -> Box:
    """Folded like Status and Filters. Open, it offers typing the keys you know
    (comma-separated); "Browse" is the fallback when you don't - Jira can have
    hundreds of projects, so it only ever draws `show_count` of them, narrowed
    first by a text filter, with "Show more" raising that by `MAX_PROJECT_OPTIONS`."""
    def option(key: str, label: str) -> Button:
        on = key in projects
        return Button(f"{'☑' if on else '☐'} {label}", lambda: toggle_project(key), dim=not on)

    available = choices.projects if choices else []
    matches = matching_projects(available, filter_text)
    shown = matches[:show_count]
    more = len(matches) > len(shown)
    browse = f"{'▾' if browse_open else '▸'} Browse" + (f" ({len(available)})" if available else "")
    return dropdown(
        "Projects", ", ".join(projects) if projects else "All", is_open, toggle,
        Input(draft, "Key1, Key2… (empty = all)", change_draft, submit_draft),
        Button(browse, toggle_browse, dim=True),
        browse_open and Box(
            len(available) > MAX_PROJECT_OPTIONS and Input(filter_text, "Filter…", change_filter),
            *(option(p.key, f"{p.key} · {p.name}") for p in shown),
            more and Button("＋ Show more", show_more_projects, variant="default"),
            choices is None and Text("Loading…", dim=True),
            choices is not None and available and not matches and Text("No project matches", dim=True),
            choices is not None and not available and Text("No projects found", dim=True),
            indent=2,
        ),
    )


def filters_control(filters: List[str], choices: Optional[Choices], is_open: bool, toggle, toggle_filter,
                    width: int = 120) -> Box:
    def option(fid: str, label: str) -> tuple:
        on = fid in filters
        return (f"{'☑' if on else '☐'} {label}", lambda: toggle_filter(fid), not on)

    names = filter_names(filters, choices)
    components = choices.components if choices else []
    saved = choices.filters if choices else []
    room = width - CONTROL_INSET
    return dropdown(
        "Filters", " · ".join(names) if names else "None", is_open, toggle,
        *checkbox_grid([option(MINE, "Mine")], room),
        components and Text("Components", dim=True),
        *checkbox_grid([option(component_id(c.name), c.name) for c in components], room),
        saved and Text("Starred filters", dim=True),
        *checkbox_grid([option(filter_id(f), f.name) for f in saved], room),
        choices is None and Text("Loading…", dim=True),
    )


def search_control(draft: str, confirmed: str, change_search, submit_search, clear_search) -> Box:
    """The search box, big like GitHub's: typing only updates the shown draft; Enter confirms it
    and looks through the whole of the chosen projects, ignoring Status and Filters."""
    return Box(
        Input(draft, "Search issues: key, number or text…", change_search, submit_search, size="normal"),
        confirmed and Button("✕ Clear search", clear_search, dim=True),
        confirmed and Text("Search ignores Status and Filters", dim=True),
    )



def controls(w, toggle_status, toggle_filter, toggle_project, change_projects_draft, submit_projects,
             toggle_project_browse, change_project_filter, show_more_projects, change_search, submit_search,
             clear_search, open_control, statuses, filters, projects, width: int = 120) -> Box:
    """The search box, projects, status and filters: text fields, so they sit outside the columns."""
    confirmed = w.store.get("search", "")
    choices: Optional[Choices] = w.state.get("choices")
    shown = w.state.get("open_control")
    return Box(
        # Air above the screen's top edge, as GitHub's has; the box's own gap separates the rest.
        Text(" "),
        search_control(w.state.get("search_draft", confirmed), confirmed, change_search, submit_search, clear_search),
        section(
            "📁 Projects", "info",
            projects_control(projects, choices, shown == "projects", lambda: open_control("projects"),
                             w.state.get("projects_draft", ", ".join(projects)), change_projects_draft,
                             submit_projects, toggle_project, bool(w.state.get("project_browse_open")),
                             toggle_project_browse, w.state.get("project_filter", ""), change_project_filter,
                             w.state.get("project_show_count") or MAX_PROJECT_OPTIONS, show_more_projects),
        ),
        section(
            "⏚ Filters", "info",
            status_control(statuses, choices, shown == "status", lambda: open_control("status"), toggle_status, width),
            filters_control(filters, choices, shown == "filters", lambda: open_control("filters"), toggle_filter, width),
        ),
        gap=1,
    )


def issue_list(w, options, statuses: List[str], act: CardActions, show_more, width: int) -> Box:
    """The issues, each one line; the selected one is its whole card."""
    ready: Optional[Ready] = w.state.get("ready")
    if ready is None:
        return section(Text("🎫 Issues", bold=True, color="info"), "info", Text("Loading…", dim=True))
    if ready.error:
        title = Text(Text("🎫 Issues", bold=True, color="error"), Text(f" {ready.project or 'All projects'}", dim=True))
        return section(title, "error", error_card(ready.error, copy=w.ui.copy, what="error",
                                                  actions=[Button("↻ Retry", w.state.get("refresh"))]))
    count = " · loading…" if w.state.get("loading") else f" · {len(ready.issues)}{'+' if ready.more else ''}"
    title = Text(Text("🎫 Issues", bold=True, color="info"), Text(f" {ready.project or 'All projects'}{count}", dim=True))
    if not ready.issues:
        return section(title, "info", Text(f"Nothing in {', '.join(statuses)}" if statuses else "No issues", dim=True))
    selected = w.state.get("selected")
    more = ready.more and not w.state.get("loading")
    at_cap = (w.state.get("limit") or 0) >= SHOW_ALL
    return section(
        title, "info",
        Box(
            *(issue_line(i, i.key == selected, act.select) for i in ready.issues),
            more and not at_cap and Button("＋ Show all", show_more, variant="default"),
            more and at_cap and Text(f"Showing the first {SHOW_ALL}: narrow it with a status or a filter", dim=True, wrap=True),
        ),
    )


def detail(w, options, act: CardActions, width: int) -> Box:
    """The selected issue's card, or a line saying to pick one."""
    ready: Optional[Ready] = w.state.get("ready")
    selected = w.state.get("selected")
    issue = next((i for i in (ready.issues if ready else []) if i.key == selected), None)
    if issue is None:
        return section("📄 Issue", "info", Text("Pick an issue on the list", dim=True))
    transitions = w.state.get("transitions") or {}
    versions = w.state.get("versions") or {}
    parents = w.state.get("parents") or {}
    comments = w.state.get("comments") or {}
    return issue_card(issue, ready.urls.get(issue.key, ""), options, w.state.get("taking"),
                      w.state.get("unfolded") == issue.key, comments.get(issue.key),
                      w.state.get("comments_open") == issue.key, act, transitions.get(issue.key),
                      w.state.get("move_open") == issue.key, w.state.get("moving"),
                      versions.get(project_key(issue.key)), w.state.get("fix_open") == issue.key,
                      w.state.get("fixing"), bool(w.state.get("fix_released")),
                      parents.get(issue.parent_key) if issue.parent_key else None, width,
                      (w.state.get("resolving") or {}).get("status") if (w.state.get("resolving") or {}).get("key") == issue.key else None)


def draw(w, width: int, options, handlers, act: CardActions, statuses, filters, projects) -> Box:
    """The whole screen: the controls on top, then the list and the issue side by side (stacked when narrow)."""
    return Box(
        controls(w, *handlers[:-1], statuses, filters, projects, width),
        responsive_columns(
            width,
            [lambda cw: issue_list(w, options, statuses, act, handlers[-1], cw),
             lambda cw: detail(w, options, act, cw)],
            ratio=(3, 2), collapse_below=120,
        ),
        gap=1,
    )
