"""Jira issues and what hangs from them, read through the jira plugin client into snapshots."""
from typing import List, Optional, Sequence

from titan_cli.core.result import ClientError, ClientSuccess
from titan_plugin_jira.models import UIJiraFilter, UIJiraIssue
from titan_plugin_jira.operations import (
    DEFAULT_SEARCH_FIELDS,
    build_issue_jql,
    components_condition,
    search_condition,
    strip_order_by,
)

from .models import Choices, Comments, Parent, Ready, Transitions, Versions

FIELDS = [*DEFAULT_SEARCH_FIELDS, "description", "fixVersions", "parent"]
SHOW_ALL = 99  # below Jira's 100-result search cap, so the +1 probe can still detect truncation
ORDER_BY = "key ASC"  # Jira sorts an issue key by its number, not as text: PROJ-2 before PROJ-10
MINE = "mine"
MINE_JQL = "assignee = currentUser()"
CATEGORY_ORDER = {"To Do": 0, "In Progress": 1, "Done": 2}
NO_JIRA = "Jira is not available here"


def component_id(name: str) -> str:
    return f"component:{name}"


def filter_id(f: UIJiraFilter) -> str:
    return f"filter:{f.id}"


def project_key(issue_key: str) -> str:
    """`ECAPP` for `ECAPP-2262`."""
    return issue_key.rsplit("-", 1)[0]


def find_issue(issues: List[UIJiraIssue], key: str) -> Optional[UIJiraIssue]:
    """The issue with this key, or None. A plain loop, not the builtin `next`:
    a hook's own parameter is often named `next` and shadows it in that scope."""
    for i in issues:
        if i.key == key:
            return i
    return None


def default_projects(jira, options) -> List[str]:
    """The `project` option (comma-separated keys), else the jira plugin's
    default_project, else none (every project the user can see)."""
    configured = [p.strip() for p in options["project"].split(",") if p.strip()]
    if configured:
        return configured
    return [jira.project_key] if jira and jira.project_key else []


def read_choices(jira, projects: List[str], previous: Optional[Choices] = None) -> Choices:
    """Statuses and components need at least one project - with several, every
    project's own are merged (by name, so the same status offered by two projects
    appears once). The starred filters and the project list itself need none.
    A list whose read fails keeps what `previous` offered for it, or is marked
    unknown when there is nothing earlier, so a hiccup never narrows the picks."""
    failed: set = set()

    def data(name, result):
        match result:
            case ClientSuccess(data=items):
                return items
            case _:
                failed.add(name)
                return []

    def merged(name, fetch):
        by_name = {}
        for p in projects:
            for item in data(name, fetch(p)):
                by_name.setdefault(item.name, item)
        return list(by_name.values())

    statuses = sorted(merged("statuses", jira.list_statuses), key=lambda s: CATEGORY_ORDER.get(s.category, 1))
    components = merged("components", jira.list_components)
    filters = data("filters", jira.list_favourite_filters())
    all_projects = sorted(data("projects", jira.list_projects()), key=lambda p: p.key)
    fresh = {"statuses": statuses, "components": components, "filters": filters, "projects": all_projects}

    unknown = set()
    for name in failed:
        if previous is not None and name not in previous.unknown:
            fresh[name] = getattr(previous, name)
        else:
            unknown.add(name)
    return Choices(**fresh, unknown=frozenset(unknown))


def conditions(filters: List[str], choices: Optional[Choices], query: str = "", projects: Sequence[str] = ()) -> List[str]:
    """The JQL of the active filters: components OR-ed together, everything else AND-ed."""
    saved = {filter_id(f): f.jql for f in (choices.filters if choices else [])}
    out = [MINE_JQL] if MINE in filters else []
    components = components_condition([f.split(":", 1)[1] for f in filters if f.startswith("component:")])
    if components:
        out.append(components)
    out += [strip_order_by(saved[f]) for f in filters if f in saved and strip_order_by(saved[f])]
    search = search_condition(query, projects)
    if search:
        out.append(search)
    return out


def search_fields(jira) -> List[str]:
    """`FIELDS`, plus the site's "Parent Link" custom field when it has one - some
    Jira sites link a story to its epic there instead of the native "parent" field."""
    match jira.get_parent_link_field_id():
        case ClientSuccess(data=field_id) if field_id:
            return [*FIELDS, field_id]
        case _:
            return FIELDS


def read_ready(jira, options, statuses: List[str], filters: List[str], choices: Optional[Choices],
               projects: List[str] = (), search: str = "", limit: Optional[int] = None) -> Ready:
    """The first `limit` issues (the `shown` option unless "Show all" raised it); one extra is read to know if more remain."""
    limit = limit or options["shown"]
    if jira is None:
        return Ready("", [], error=f"{NO_JIRA}: enable and configure the jira plugin")
    scope = ", ".join(projects)
    if search.strip():
        statuses, filters = [], []  # a search looks through the whole of the chosen projects
    query = build_issue_jql(list(statuses), list(projects), conditions(filters, choices, search, projects), order_by=ORDER_BY)
    match jira.search_issues(query, max_results=limit + 1, fields=search_fields(jira)):
        case ClientSuccess(data=found):
            issues = found[:limit]
            return Ready(query, issues, scope, urls={i.key: jira.issue_url(i.key) for i in issues},
                         more=len(found) > limit)
        case ClientError(error_message=message):
            return Ready(query, [], scope, error=message)


def read_mine(jira, projects: List[str], limit: int) -> Ready:
    """The unfinished issues assigned to the user, latest touched first: what needs them."""
    if jira is None:
        return Ready("", [], error=f"{NO_JIRA}: enable and configure the jira plugin")
    scope = ", ".join(projects)
    query = build_issue_jql(None, list(projects), [MINE_JQL, "statusCategory != Done"], order_by="updated DESC")
    match jira.search_issues(query, max_results=limit + 1, fields=DEFAULT_SEARCH_FIELDS):
        case ClientSuccess(data=found):
            issues = found[:limit]
            return Ready(query, issues, scope, urls={i.key: jira.issue_url(i.key) for i in issues},
                         more=len(found) > limit)
        case ClientError(error_message=message):
            return Ready(query, [], scope, error=message)


def read_comments(jira, key: str) -> Comments:
    if jira is None:
        return Comments("error", error=NO_JIRA)
    match jira.get_comments(key):
        case ClientSuccess(data=items):
            return Comments("done", items)
        case ClientError(error_message=message):
            return Comments("error", error=message)


def read_parent(jira, key: str) -> Parent:
    if jira is None:
        return Parent("error", error=NO_JIRA)
    match jira.get_issue(key):
        case ClientSuccess(data=issue):
            return Parent("done", issue, jira.issue_url(key))
        case ClientError(error_message=message):
            return Parent("error", error=message)


def read_transitions(jira, key: str) -> Transitions:
    if jira is None:
        return Transitions("error", error=NO_JIRA)
    match jira.get_transitions(key):
        case ClientSuccess(data=items):
            return Transitions("done", items)
        case ClientError(error_message=message):
            return Transitions("error", error=message)


def read_versions(jira, project: str) -> Versions:
    if jira is None:
        return Versions("error", error=NO_JIRA)
    match jira.list_project_versions(project):
        case ClientSuccess(data=items):
            return Versions("done", items)
        case ClientError(error_message=message):
            return Versions("error", error=message)
