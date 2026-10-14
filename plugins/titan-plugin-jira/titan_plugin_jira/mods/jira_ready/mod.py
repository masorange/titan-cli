"""
jira_ready: a side pane with Jira issues, narrowed by a status and by filters
picked from two drop-downs in the pane itself. Both read Jira: the statuses
of the project, its components, and the saved filters you starred, plus
"Mine". Nothing has to be picked: no status means any status, no filter
means every issue. Opening an issue shows its summary, assignee, status and
folded description, and lets you plan it (the plan workflow opens on it,
skipping its issue prompt) or take it (assigned to you and moved to the
working status).

Everything Jira-specific (the JQL, taking an issue, the description and name
formatting, the issue URL) comes from the jira plugin; this file only polls
and draws. Reads run on a background thread; drawing reads only `m.state`,
so it never waits on the network. The chosen status and filters live in
`m.store`, so they survive a restart.
"""
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from titan_cli.core.mods import Box, Button, Link, Text
from titan_cli.core.result import ClientError, ClientSuccess
from titan_plugin_jira.models import UIJiraComment, UIJiraComponent, UIJiraFilter, UIJiraIssue, UIJiraStatus
from titan_plugin_jira.operations import (
    DEFAULT_SEARCH_FIELDS,
    build_issue_jql,
    build_issue_summary_prompt,
    components_condition,
    display_lines,
    format_person_name,
    issue_description_lines,
    strip_order_by,
    take_issue,
)

PANE = "jira-ready"
TITLE = "Jira"
FIELDS = [*DEFAULT_SEARCH_FIELDS, "description"]
DESCRIPTION_LINES = 200
PREVIEW_LINES = 2
COMMENT_LINES = 60
SUMMARY_TOKENS = 900
MINE = "mine"
MINE_JQL = "assignee = currentUser()"
CATEGORY_ORDER = {"To Do": 0, "In Progress": 1, "Done": 2}


@dataclass(frozen=True)
class Choices:
    """What the drop-downs offer, as Jira has it."""
    statuses: List[UIJiraStatus] = field(default_factory=list)
    components: List[UIJiraComponent] = field(default_factory=list)
    filters: List[UIJiraFilter] = field(default_factory=list)


@dataclass(frozen=True)
class Comments:
    """An issue's comments, read when its card opens: loading, done or error."""
    status: str
    items: List[UIJiraComment] = field(default_factory=list)
    error: Optional[str] = None


@dataclass(frozen=True)
class Summary:
    """What an AI made of an issue and its comments: running, done or error."""
    status: str
    text: str = ""
    model: Optional[str] = None
    error: Optional[str] = None


@dataclass
class CardActions:
    """What the open card's buttons do; the pane's `render` wires them to `m`."""
    select: Callable[[str], None]
    fold: Callable[[str], None]
    plan: Callable[[str], None]
    take: Callable[[UIJiraIssue], None]
    toggle_comments: Callable[[str], None]
    summarize: Callable[[UIJiraIssue], None]
    copy_summary: Callable[[UIJiraIssue], None]
    pick_ai: Callable[[], None]


@dataclass(frozen=True)
class Ready:
    query: str
    issues: List[UIJiraIssue]
    project: str = ""  # empty: every project the user can see
    error: Optional[str] = None
    urls: Dict[str, str] = field(default_factory=dict)  # issue key -> its page


def component_id(name: str) -> str:
    return f"component:{name}"


def filter_id(f: UIJiraFilter) -> str:
    return f"filter:{f.id}"


def project_of(jira, options) -> str:
    """The mod's `project` option, else the jira plugin's default_project, else none."""
    return options["project"] or (jira.project_key if jira else "") or ""


def read_choices(jira, project: str) -> Choices:
    """Statuses and components need a project; the starred filters do not. A failed read offers nothing."""
    def data(result):
        match result:
            case ClientSuccess(data=items):
                return items
            case _:
                return []

    statuses = data(jira.list_statuses(project)) if project else []
    statuses = sorted(statuses, key=lambda s: CATEGORY_ORDER.get(s.category, 1))
    components = data(jira.list_components(project)) if project else []
    return Choices(statuses, components, data(jira.list_favourite_filters()))


def chosen_status(m) -> Optional[str]:
    """The picked status while Jira still offers it; None (any status) otherwise."""
    status = m.store.get("status")
    choices: Optional[Choices] = m.state.get("choices")
    if choices is not None and status not in {s.name for s in choices.statuses}:
        return None
    return status


def active_filters(m) -> List[str]:
    """The picked filters still on offer (all of them while the offer is still loading)."""
    picked = list(m.store.get("filters", []))
    choices: Optional[Choices] = m.state.get("choices")
    if choices is None:
        return picked
    offered = {MINE, *(component_id(c.name) for c in choices.components), *(filter_id(f) for f in choices.filters)}
    return [f for f in picked if f in offered]


def conditions(filters: List[str], choices: Optional[Choices]) -> List[str]:
    """The JQL of the active filters: components OR-ed together, everything else AND-ed."""
    saved = {filter_id(f): f.jql for f in (choices.filters if choices else [])}
    out = [MINE_JQL] if MINE in filters else []
    components = components_condition([f.split(":", 1)[1] for f in filters if f.startswith("component:")])
    if components:
        out.append(components)
    out += [strip_order_by(saved[f]) for f in filters if f in saved and strip_order_by(saved[f])]
    return out


def read_ready(jira, options, status: Optional[str], filters: List[str], choices: Optional[Choices]) -> Ready:
    if jira is None:
        return Ready("", [], error="Jira is not available here: enable and configure the jira plugin")
    project = project_of(jira, options)
    query = build_issue_jql(status, project, conditions(filters, choices))
    match jira.search_issues(query, max_results=options["shown"], fields=FIELDS):
        case ClientSuccess(data=issues):
            return Ready(query, issues, project, urls={i.key: jira.issue_url(i.key) for i in issues})
        case ClientError(error_message=message):
            return Ready(query, [], project, error=message)


def issue_line(issue: UIJiraIssue, selected: bool, select) -> Button:
    """One line per issue; pressing it opens (or closes) its card."""
    return Button(f"{'▾' if selected else '▸'} {issue.priority_icon} {issue.key} {issue.summary}", lambda: select(issue.key))


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


def comments_section(key: str, comments: Optional[Comments], is_open: bool, toggle) -> Optional[Box]:
    """A fold with the issue's comments, oldest first; nothing at all when it has none."""
    if comments is None or comments.status == "loading":
        return Box(Text("Comments…", dim=True))
    if comments.status == "error":
        return Box(Text(f"Comments: {comments.error}", color="error", wrap=True))
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


def summary_section(issue: UIJiraIssue, summary: Optional[Summary], ai_label: Optional[str], act: CardActions) -> Box:
    """The button that asks an AI what the issue asks for, who answers, and its last answer."""
    running = summary is not None and summary.status == "running"
    if running:
        label = f"… summarizing with {summary.model or 'AI routing'}"
    elif summary is not None and summary.status == "done":
        label = "✦ Summarize again"
    else:
        label = "✦ Summarize"
    done = summary is not None and summary.status == "done"
    return Box(
        Box(
            Button(label, lambda: None if running else act.summarize(issue), dim=running),
            Button(f"⟳ {ai_label or 'AI routing'}", act.pick_ai, dim=True),
            row=True,
        ),
        summary is not None and summary.status == "error" and Text(f"Could not summarize: {summary.error}", color="error", wrap=True),
        done and Box(
            Text(Text("✦ Summary", bold=True, color="accent"), Text(f" · {summary.model or 'AI'}", dim=True)),
            *(Text(line or " ", wrap=True) for line in display_lines(summary.text)),
            Button("⧉ Copy", lambda: act.copy_summary(issue), dim=True),
            border="accent",
        ),
    )


def actions(issue: UIJiraIssue, url: str, options, taking: Optional[str], plan, take) -> Box:
    buttons = []
    if options["plan_workflow"]:
        buttons.append(Button("▶ Plan", lambda: plan(issue.key), variant="default"))
    if options["take_status"] and issue.status.strip().lower() != options["take_status"].strip().lower():
        label = "Taking…" if taking == issue.key else "✋ Take"
        buttons.append(Button(label, lambda: take(issue), variant="default"))
    return Box(*buttons, url and Text(Link("↗ Open", url)), row=True)


def issue_card(issue: UIJiraIssue, url: str, options, taking: Optional[str], unfolded: bool,
               comments: Optional[Comments], comments_open: bool, summary: Optional[Summary],
               ai_label: Optional[str], act: CardActions) -> Box:
    """
    The open issue: its line, summary, who has it, status, description, comments,
    the AI summary; the actions always last.
    """
    assignee = format_person_name(issue.assignee) if issue.assignee and issue.assignee != "Unassigned" else ""
    return Box(
        issue_line(issue, True, act.select),
        Box(
            Text(issue.summary, bold=True, wrap=True),
            Box(
                Text("👤 ", assignee or Text("Unassigned", dim=True)),
                Text(f"{issue.status_icon} {issue.status}", dim=True),
            ),
            description(issue, unfolded, act.fold),
            comments_section(issue.key, comments, comments_open, act.toggle_comments),
            summary_section(issue, summary, ai_label, act),
            actions(issue, url, options, taking, act.plan, act.take),
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


def dropdown(label: str, summary: str, is_open: bool, toggle, *options) -> Box:
    """A line with what is picked; pressing it unfolds the options under it."""
    return Box(
        Button(f"{label:<8} {'▾' if is_open else '▸'} {summary}", toggle, dim=not is_open),
        is_open and Box(*options, indent=11),
    )


def status_control(status: Optional[str], choices: Optional[Choices], is_open: bool, toggle, pick_status) -> Box:
    def option(name: Optional[str], label: str) -> Button:
        on = name == status
        return Button(f"{'●' if on else '○'} {label}", lambda: pick_status(name), dim=not on)

    statuses = choices.statuses if choices else []
    return dropdown(
        "Status", status or "Any", is_open, toggle,
        option(None, "Any"),
        *(option(s.name, f"{s.icon} {s.name}") for s in statuses),
        choices is not None and not statuses and Text("No statuses without a project", dim=True),
    )


def filters_control(filters: List[str], choices: Optional[Choices], is_open: bool, toggle, toggle_filter) -> Box:
    def option(fid: str, label: str) -> Button:
        on = fid in filters
        return Button(f"{'☑' if on else '☐'} {label}", lambda: toggle_filter(fid), dim=not on)

    names = filter_names(filters, choices)
    components = choices.components if choices else []
    saved = choices.filters if choices else []
    return dropdown(
        "Filters", " · ".join(names) if names else "None", is_open, toggle,
        option(MINE, "Mine"),
        components and Text("Components", dim=True),
        *(option(component_id(c.name), c.name) for c in components),
        saved and Text("Starred filters", dim=True),
        *(option(filter_id(f), f.name) for f in saved),
        choices is None and Text("Loading…", dim=True),
    )


def draw(m, options, pick_status, toggle_filter, open_control, act: CardActions):
    status, filters = chosen_status(m), active_filters(m)
    choices: Optional[Choices] = m.state.get("choices")
    shown = m.state.get("open_control")
    controls = [
        status_control(status, choices, shown == "status", lambda: open_control("status"), pick_status),
        filters_control(filters, choices, shown == "filters", lambda: open_control("filters"), toggle_filter),
    ]

    ready: Optional[Ready] = m.state.get("ready")
    if ready is None or m.state.get("loading"):
        body = [Text("Loading…", dim=True)]
    elif ready.error:
        body = [Text(ready.error, color="error", wrap=True)]
    elif not ready.issues:
        body = [Text(f"Nothing in {status}" if status else "No issues", dim=True)]
    else:
        selected = m.state.get("selected")
        comments = m.state.get("comments") or {}
        summaries = m.state.get("summaries") or {}
        body = [
            issue_card(i, ready.urls.get(i.key, ""), options, m.state.get("taking"), m.state.get("unfolded") == i.key,
                       comments.get(i.key), m.state.get("comments_open") == i.key, summaries.get(i.key),
                       m.state.get("ai_label"), act)
            if i.key == selected else issue_line(i, False, act.select)
            for i in ready.issues
        ]
    if ready is not None and not ready.error:
        count = "" if m.state.get("loading") else f" · {len(ready.issues)}"
        scope = Text(f"{ready.project or 'All projects'}{count}", dim=True)
    else:
        scope = None
    return Box(Box(scope, *controls), Box(*body, gap=1), gap=1)


def register(on, options):
    def refresh(m):
        jira = m.client("jira")
        if jira is not None:
            m.state.set("choices", read_choices(jira, project_of(jira, options)))
        status, filters = chosen_status(m), active_filters(m)
        m.state.set("loading", True)
        result = read_ready(jira, options, status, filters, m.state.get("choices"))
        # A slower search started before the last change must not overwrite a newer one.
        if (status, filters) == (chosen_status(m), active_filters(m)):
            m.state.set("ready", result)
            m.state.set("loading", False)

    def load_comments(m, key) -> List[UIJiraComment]:
        """Read `key`'s comments into state; off the UI thread. The ones read, or none on failure."""
        def put(c):
            m.state.update("comments", lambda all_: {**(all_ or {}), key: c}, default={})

        jira = m.client("jira")
        if jira is None:
            put(Comments("error", error="Jira is not available here"))
            return []
        put(Comments("loading"))
        match jira.get_comments(key):
            case ClientSuccess(data=items):
                put(Comments("done", items))
                return items
            case ClientError(error_message=message):
                put(Comments("error", error=message))
                return []

    def summarize(m, issue: UIJiraIssue) -> None:
        """Ask the AI what `issue` asks for, its comments included; off the UI thread."""
        def put(s):
            m.state.update("summaries", lambda all_: {**(all_ or {}), issue.key: s}, default={})

        put(Summary("running", model=m.state.get("ai_label")))
        known: Optional[Comments] = (m.state.get("comments") or {}).get(issue.key)
        # A comment may refine or settle the description: never summarize without them.
        comments = known.items if known is not None and known.status == "done" else load_comments(m, issue.key)
        prompt, system = build_issue_summary_prompt(issue, comments)
        answer = m.ai.complete(prompt, system=system, max_tokens=SUMMARY_TOKENS)
        if answer.ok:
            put(Summary("done", answer.text, answer.model))
        else:
            put(Summary("error", error=answer.error))

    def refresh_ai_label(m) -> None:
        m.state.set("ai_label", m.ai.describe())

    @on("app.start")
    def start(m, e, next):
        m.ui.open(PANE, TITLE)
        m.clock.every(options["refresh_seconds"], lambda: refresh(m))
        m.run(lambda: refresh_ai_label(m))
        return next(e)

    @on("ui.render", match={"component": "Pane", "pane": PANE})
    def render(m, e, next):
        def search():
            m.run(lambda: refresh(m))

        def open_control(name):
            m.state.set("open_control", None if m.state.get("open_control") == name else name)

        def pick_status(status):
            m.store.set("status", status)
            m.state.set("open_control", None)
            search()

        def toggle_filter(fid):
            on_now = active_filters(m)
            m.store.set("filters", [f for f in on_now if f != fid] if fid in on_now else [*on_now, fid])
            search()

        def select(key):
            opening = m.state.get("selected") != key
            m.state.set("selected", key if opening else None)
            known: Optional[Comments] = (m.state.get("comments") or {}).get(key)
            if opening and (known is None or known.status == "error"):
                m.run(lambda: load_comments(m, key))

        def toggle_comments(key):
            m.state.set("comments_open", None if m.state.get("comments_open") == key else key)

        def copy_summary(issue):
            summary: Optional[Summary] = (m.state.get("summaries") or {}).get(issue.key)
            if summary is not None and summary.status == "done":
                m.ui.copy(f"{issue.key} {issue.summary}\n\n{summary.text}\n", f"{issue.key} summary")

        def pick_ai():
            m.ai.configure("Jira issue summary", on_done=lambda: m.run(lambda: refresh_ai_label(m)))

        def fold(key):
            m.state.set("unfolded", None if m.state.get("unfolded") == key else key)

        def plan(key):
            m.workflows.run(options["plan_workflow"], {"jira_issue_key": key})

        def take(issue):
            if m.state.get("taking"):
                return
            m.state.set("taking", issue.key)

            def work():
                jira = m.client("jira")
                result = take_issue(jira, issue, options["take_status"]) if jira else None
                m.state.set("taking", None)
                match result:
                    case ClientSuccess(message=message):
                        m.ui.toast(message)
                    case ClientError(error_message=message):
                        m.ui.toast(message, "error")
                    case None:
                        m.ui.toast("Jira is not available here", "error")
                refresh(m)

            m.run(work)

        act = CardActions(select, fold, plan, take, toggle_comments,
                          lambda issue: m.run(lambda: summarize(m, issue)), copy_summary, pick_ai)
        return draw(m, options, pick_status, toggle_filter, open_control, act)
