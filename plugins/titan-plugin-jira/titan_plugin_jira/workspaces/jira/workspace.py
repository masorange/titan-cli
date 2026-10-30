"""
jira workspace: a full screen for Jira, opened from its dock tile.

Issues from one or more projects, narrowed by status, components, starred filters or a search; the
open issue shows its description, comments, parent and an AI summary, and lets you plan it, take it,
move it to another status or set its fix version. Everything Jira-specific (the JQL, taking an
issue, the formatting) comes from the jira plugin and its readers, shared with the `jira_ready` mod
that keeps the summary in the side pane; this file wires reads, timers and actions and `draw.py`
draws from `w.state` only, so it never waits on the network. Picks live in `w.store`.
"""
from typing import List, Optional

from titan_cli.core.result import ClientError, ClientSuccess
from titan_cli.ui.components import AIResult, refresh_ai_chip
from titan_plugin_jira.operations import build_issue_summary_prompt, display_lines, take_issue
from titan_plugin_jira.readers import issues as reader
from titan_plugin_jira.readers.models import Choices, Comments, Parent, Transitions, Versions

from . import draw

TITLE = "Jira"
SUMMARY_TOKENS = 900


def active_statuses(w) -> List[str]:
    """The picked statuses still on offer (all of them while the offer is unknown)."""
    picked = list(w.store.get("statuses") or [])
    choices: Optional[Choices] = w.state.get("choices")
    if choices is None or "statuses" in choices.unknown:
        return picked
    offered = {s.name for s in choices.statuses}
    return [s for s in picked if s in offered]


def active_filters(w) -> List[str]:
    """The picked filters still on offer (all of them while the offer is unknown)."""
    picked = list(w.store.get("filters", []))
    choices: Optional[Choices] = w.state.get("choices")
    if choices is None:
        return picked
    offered = {reader.MINE}
    offered |= {reader.component_id(c.name) for c in choices.components}
    offered |= {reader.filter_id(f) for f in choices.filters}
    unknown_components, unknown_filters = "components" in choices.unknown, "filters" in choices.unknown
    return [
        f for f in picked
        if f in offered
        or (unknown_components and f.startswith("component:"))
        or (unknown_filters and f.startswith("filter:"))
    ]


def active_projects(w) -> List[str]:
    """The picked projects still on offer (all of them while the offer is unknown).
    Keys compare case-insensitively, as JQL does, and come back as Jira spells them."""
    picked = list(w.store.get("projects") or [])
    choices: Optional[Choices] = w.state.get("choices")
    if choices is None or "projects" in choices.unknown:
        return picked
    offered = {p.key.upper(): p.key for p in choices.projects}
    return [offered[p.upper()] for p in picked if p.upper() in offered]


def register(w, on, options):
    started = []

    def refresh_choices(w):
        """One call per project plus two flat ones: only worth repeating when the chosen
        projects change or on the timer, never on every status/filter/search tweak."""
        jira = w.client("jira")
        if jira is not None and w.store.get("projects") is None:
            w.store.set("projects", reader.default_projects(jira, options))
        if jira is not None:
            w.state.set("choices", reader.read_choices(jira, active_projects(w), w.state.get("choices")))

    def refresh_issues(w):
        jira = w.client("jira")
        statuses, filters, projects = active_statuses(w), active_filters(w), active_projects(w)
        search, limit = w.store.get("search", ""), w.state.get("limit")
        w.state.set("loading", True)
        try:
            result = reader.read_ready(jira, options, statuses, filters, w.state.get("choices"), projects, search, limit)
        except BaseException:
            w.state.set("loading", False)
            raise
        # A slower search started before the last change must not overwrite a newer one.
        current = (statuses, filters, active_projects(w), w.store.get("search", ""), w.state.get("limit"))
        if (statuses, filters, projects, search, limit) == current:
            w.state.set("ready", result)
            w.state.set("loading", False)

    def refresh(w):
        refresh_choices(w)
        refresh_issues(w)

    w.state.set("refresh", lambda: w.run(lambda: refresh(w)))

    def put(name, key, value):
        w.state.update(name, lambda all_: {**(all_ or {}), key: value}, default={})

    def load(name, key, loading, read):
        """Read one thing about an issue into `w.state[name][key]`, off the UI thread."""
        put(name, key, loading)
        put(name, key, read(w.client("jira")))

    def load_comments(w, key) -> List:
        load("comments", key, Comments("loading"), lambda jira: reader.read_comments(jira, key))
        known: Comments = w.state.get("comments")[key]
        return known.items if known.status == "done" else []

    def summary_work(issue):
        """What `ask_ai` runs for `issue`: its comments, then the AI's summary."""
        def work(w):
            known = (w.state.get("comments") or {}).get(issue.key)
            # A comment may refine or settle the description: never summarize without them.
            comments = known.items if known is not None and known.status == "done" else load_comments(w, issue.key)
            prompt, system = build_issue_summary_prompt(issue, comments)
            answer = w.ai.complete(prompt, system=system, max_tokens=SUMMARY_TOKENS)
            if not answer.ok:
                return answer
            return AIResult("done", answer.text, answer.model, value=tuple(display_lines(answer.text)))

        return work

    def act_on(issue, state_key, call, busy_extra=()):
        """Run a change on Jira off the UI thread, toast what came back and reread the list."""
        if w.state.get(state_key):
            return
        w.state.set(state_key, issue.key)
        for key in busy_extra:
            w.state.set(key, None)

        def work():
            jira = w.client("jira")
            try:
                result = call(jira) if jira else None
            finally:
                w.state.set(state_key, None)
            match result:
                case ClientSuccess(message=message):
                    w.ui.toast(message)
                case ClientError(error_message=message):
                    w.ui.toast(message, "error")
                case None:
                    w.ui.toast(reader.NO_JIRA, "error")
            refresh_issues(w)

        w.run(work)

    def search():
        w.run(lambda: refresh_issues(w))

    def reload():
        """Like `search`, but also rereads statuses/components/projects: for the handlers that change the projects."""
        w.run(lambda: refresh(w))

    def reset_and(then):
        w.state.set("limit", None)
        then()

    def open_control(name):
        w.state.set("open_control", None if w.state.get("open_control") == name else name)

    def toggle_status(name):
        on_now = active_statuses(w)
        w.store.set("statuses", [s for s in on_now if s != name] if name in on_now else [*on_now, name])
        reset_and(search)

    def toggle_filter(fid):
        on_now = active_filters(w)
        w.store.set("filters", [f for f in on_now if f != fid] if fid in on_now else [*on_now, fid])
        reset_and(search)

    def toggle_project(key):
        on_now = active_projects(w)
        updated = [p for p in on_now if p != key] if key in on_now else [*on_now, key]
        w.store.set("projects", updated)
        w.state.set("projects_draft", ", ".join(updated))
        reset_and(reload)

    def submit_projects(value):
        keys = [p.strip() for p in value.split(",") if p.strip()]
        w.store.set("projects", keys)
        w.state.set("projects_draft", ", ".join(keys))
        reset_and(reload)

    def toggle_project_browse():
        w.state.set("project_browse_open", not w.state.get("project_browse_open"))

    def change_project_filter(value):
        w.state.set("project_filter", value)
        w.state.set("project_show_count", draw.MAX_PROJECT_OPTIONS)

    def show_more_projects():
        w.state.set("project_show_count", (w.state.get("project_show_count") or draw.MAX_PROJECT_OPTIONS) + draw.MAX_PROJECT_OPTIONS)

    def submit_search(value):
        w.store.set("search", value.strip())
        reset_and(search)

    def clear_search():
        w.store.set("search", "")
        w.state.set("search_draft", "")
        reset_and(search)

    def show_more():
        w.state.set("limit", reader.SHOW_ALL)
        search()

    def select(key):
        opening = w.state.get("selected") != key
        w.state.set("selected", key if opening else None)
        if not opening:
            return
        known = (w.state.get("comments") or {}).get(key)
        if known is None or known.status == "error":
            w.run(lambda: load_comments(w, key))
        ready = w.state.get("ready")
        issue = reader.find_issue(ready.issues, key) if ready else None
        parent_key = issue.parent_key if issue else None
        if parent_key:
            known_parent = (w.state.get("parents") or {}).get(parent_key)
            if known_parent is None or known_parent.status == "error":
                w.run(lambda: load("parents", parent_key, Parent("loading"), lambda jira: reader.read_parent(jira, parent_key)))

    def toggle(state_key):
        return lambda key: w.state.set(state_key, None if w.state.get(state_key) == key else key)

    def toggle_move(key):
        opening = w.state.get("move_open") != key
        w.state.set("move_open", key if opening else None)
        if opening:
            w.run(lambda: load("transitions", key, Transitions("loading"), lambda jira: reader.read_transitions(jira, key)))

    def toggle_fix(issue):
        opening = w.state.get("fix_open") != issue.key
        w.state.set("fix_open", issue.key if opening else None)
        if opening:
            project = reader.project_key(issue.key)
            w.run(lambda: load("versions", project, Versions("loading"), lambda jira: reader.read_versions(jira, project)))

    handlers = (toggle_status, toggle_filter, toggle_project,
                lambda value: w.state.set("projects_draft", value), submit_projects, toggle_project_browse,
                change_project_filter, show_more_projects,
                lambda value: w.state.set("search_draft", value), submit_search, clear_search, open_control,
                show_more)

    def retry(what, key):
        """Read again what an error card says failed, off the UI thread."""
        reads = {
            "comments": lambda: load_comments(w, key),
            "parent": lambda: load("parents", key, Parent("loading"), lambda jira: reader.read_parent(jira, key)),
            "transitions": lambda: load("transitions", key, Transitions("loading"), lambda jira: reader.read_transitions(jira, key)),
            "versions": lambda: load("versions", key, Versions("loading"), lambda jira: reader.read_versions(jira, key)),
        }
        w.run(reads[what])

    def actions():
        return draw.CardActions(
            select, toggle("unfolded"),
            lambda key: w.workflows.run(options["plan_workflow"], {"jira_issue_key": key}),
            lambda issue: act_on(issue, "taking", lambda jira: take_issue(jira, issue, options["take_status"])),
            toggle("comments_open"),
            lambda issue: draw.summary_section(w, issue, summary_work(issue)),
            w.ui.copy, toggle_move,
            lambda issue, status: act_on(issue, "moving", lambda jira: jira.transition_issue(issue.key, status),
                                         busy_extra=("move_open",)),
            toggle_fix,
            lambda issue, version: act_on(issue, "fixing",
                                          lambda jira: jira.set_fix_version(issue.key, version.id if version else None),
                                          busy_extra=("fix_open",)),
            lambda: w.state.set("fix_released", not w.state.get("fix_released")),
            retry,
        )

    def view(width):
        return draw.draw(w, width, options, handlers, actions(), active_statuses(w), active_filters(w), active_projects(w))

    w.ui.view(view, title=TITLE)

    def start(w):
        started.append(True)
        w.ui.dock(TITLE, on_click=w.ui.open_workspace)
        w.clock.every(options["refresh_seconds"], lambda: refresh(w))
        w.run(lambda: refresh_ai_chip(w))
        if options.get("refresh_key"):
            w.keys.bind(options["refresh_key"], "Refresh Jira", lambda: w.run(lambda: refresh(w)))

    w.on_start(start)

    def focus(w, what):
        """Show the issue the mod's pane was pressed on, its card open, once the list has it."""
        if isinstance(what, dict) and what.get("issue"):
            select_key = what["issue"]
            w.state.set("selected", None)
            w.run(lambda: open_issue(w, select_key))

    def open_issue(w, key):
        ready = w.state.get("ready")
        if ready is None or reader.find_issue(ready.issues, key) is None:
            # Not on the list as filtered: search for exactly it so the card has something to open.
            w.store.set("search", key)
            w.state.set("search_draft", key)
            w.state.set("limit", None)
            refresh_issues(w)
        select(key)

    w.on_open(focus)

    # Workflows are what change Jira (plan, take, create), so reread right after one ends,
    # however it ended. Goes off the workflow's thread, so its end is never delayed.
    @on("workflow.run")
    def after_workflow(w, e, next):
        try:
            return next(e)
        finally:
            if not e.nested and started:
                w.run(lambda: refresh_issues(w))
