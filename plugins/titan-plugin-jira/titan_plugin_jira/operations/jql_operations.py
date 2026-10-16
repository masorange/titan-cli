"""
JQL Operations

Pure business logic for JQL query handling.
These functions can be used by any step and are easily testable.
"""

import re
from typing import Dict, Optional, Sequence, Tuple, Union


def substitute_jql_variables(jql: str, context_data: Dict[str, any]) -> str:
    """
    Substitute variables in JQL query with values from context.

    Replaces ${variable_name} patterns with values from context_data.

    Args:
        jql: JQL query string with ${variable} placeholders
        context_data: Dictionary of variable names to values

    Returns:
        JQL string with variables substituted

    Examples:
        >>> substitute_jql_variables("project = ${project}", {"project": "MYPROJ"})
        'project = MYPROJ'
        >>> substitute_jql_variables("status = ${status}", {})
        'status = ${status}'
        >>> substitute_jql_variables("project = ${p1} AND status = ${p2}", {"p1": "A", "p2": "Done"})
        'project = A AND status = Done'
    """
    def replace_var(match):
        var_name = match.group(1)
        value = context_data.get(var_name)
        if value is None:
            # Variable not found in context, keep original placeholder
            return match.group(0)
        return str(value)

    # Replace ${variable} patterns
    return re.sub(r'\$\{([^}]+)\}', replace_var, jql)


def format_jql_with_project(jql: str, project_key: Optional[str]) -> Tuple[str, Optional[str]]:
    """
    Format JQL query with project parameter.

    Args:
        jql: JQL query potentially containing {project} placeholder
        project_key: Project key to substitute, or None

    Returns:
        Tuple of (formatted_jql, error_message)
        - If successful: (formatted_jql, None)
        - If project required but missing: (original_jql, error_message)

    Examples:
        >>> format_jql_with_project("project = {project}", "MYPROJ")
        ('project = MYPROJ', None)
        >>> format_jql_with_project("status = Open", None)
        ('status = Open', None)
        >>> jql, err = format_jql_with_project("project = {project}", None)
        >>> err is not None
        True
    """
    if "{project}" not in jql:
        # No project parameter needed
        return jql, None

    if not project_key:
        error = f"Query requires project parameter but none provided: {jql}"
        return jql, error

    formatted_jql = jql.format(project=project_key)
    return formatted_jql, None


def merge_query_collections(
    predefined_queries: Dict[str, str],
    custom_queries: Dict[str, str]
) -> Dict[str, str]:
    """
    Merge predefined and custom queries, with custom queries taking precedence.

    Args:
        predefined_queries: Built-in queries
        custom_queries: User-defined queries from config

    Returns:
        Merged dictionary with custom queries overriding predefined ones

    Examples:
        >>> predefined = {"q1": "jql1", "q2": "jql2"}
        >>> custom = {"q2": "custom_jql2", "q3": "jql3"}
        >>> merged = merge_query_collections(predefined, custom)
        >>> merged["q1"]
        'jql1'
        >>> merged["q2"]
        'custom_jql2'
        >>> merged["q3"]
        'jql3'
    """
    return {**predefined_queries, **custom_queries}


def build_query_not_found_message(
    query_name: str,
    predefined_queries: Dict[str, str],
    custom_queries: Dict[str, str],
    max_predefined_shown: int = 15
) -> str:
    """
    Build a helpful error message when a query is not found.

    Args:
        query_name: The query that wasn't found
        predefined_queries: Available predefined queries
        custom_queries: Available custom queries
        max_predefined_shown: Maximum predefined queries to list (default: 15)

    Returns:
        Formatted error message with available queries

    Examples:
        >>> predefined = {"q1": "jql1", "q2": "jql2"}
        >>> custom = {"c1": "custom1"}
        >>> msg = build_query_not_found_message("missing", predefined, custom, max_predefined_shown=2)
        >>> "missing" in msg
        True
        >>> "q1" in msg or "q2" in msg
        True
    """
    predefined_list = list(predefined_queries.keys())
    custom_list = list(custom_queries.keys())

    error_msg = f"Query '{query_name}' not found\n\n"
    error_msg += "Available predefined queries:\n  "

    # Show limited number of predefined queries
    shown_queries = predefined_list[:max_predefined_shown]
    error_msg += "\n  ".join(shown_queries)

    if len(predefined_list) > max_predefined_shown:
        remaining = len(predefined_list) - max_predefined_shown
        error_msg += f"\n  ... and {remaining} more"

    if custom_list:
        error_msg += "\n\nCustom queries:\n  "
        error_msg += "\n  ".join(custom_list)
    else:
        error_msg += "\n\nNo custom queries defined. Add them in .titan/config.toml:\n"
        error_msg += "[jira.saved_queries]\nmy_query = \"project = MYPROJ\""

    return error_msg


def jql_string(value: str) -> str:
    """`value` as a quoted JQL string, its quotes and backslashes escaped."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _scope_condition(field: str, value: Union[str, Sequence[str], None]) -> Optional[str]:
    """`field = "x"` for one value, `field in ("x", "y")` for several, nothing for none."""
    values = [value] if isinstance(value, str) else list(value or [])
    if len(values) == 1:
        return f"{field} = {jql_string(values[0])}"
    if values:
        return f"{field} in ({', '.join(jql_string(v) for v in values)})"
    return None


def build_issue_jql(
    status: Union[str, Sequence[str], None] = None,
    project: Union[str, Sequence[str], None] = None,
    conditions: Sequence[str] = (),
    order_by: str = "priority DESC, updated DESC",
) -> str:
    """
    JQL for the issues in `project` and `status` (each one key, several, or none for
    every one the user can see), matching every one of `conditions`.
    """
    where = [c for c in (_scope_condition("project", project), _scope_condition("status", status)) if c]
    where += [f"({condition})" for condition in conditions]
    jql = " AND ".join(where)
    return " ".join(part for part in (jql, f"ORDER BY {order_by}" if order_by else "") if part)


# A quoted string is skipped whole, so an "order by" inside a value is not a clause.
_QUOTED_OR_ORDER_BY = re.compile(
    r"""(?P<quoted>"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')|(?P<order>\bORDER\s+BY\b)""",
    re.IGNORECASE,
)


def strip_order_by(jql: str) -> str:
    """`jql` without its ORDER BY clause, so it can be one condition of another query."""
    for match in _QUOTED_OR_ORDER_BY.finditer(jql):
        if match.group("order"):
            return jql[: match.start()].strip()
    return jql.strip()


def components_condition(names: Sequence[str]) -> str:
    """JQL for issues in any of the components `names` (empty when there are none)."""
    if not names:
        return ""
    return f"component in ({', '.join(jql_string(n) for n in names)})"


_ISSUE_KEY = re.compile(r"^[A-Za-z][A-Za-z0-9]*-\d+$")
_ISSUE_NUMBER = re.compile(r"^[A-Za-z]*-?(\d+)$")  # a bare number, or any prefix (typo'd or not) before it


_TEXT_SEARCH_RESERVED = re.compile(r'([+\-&|!(){}\[\]^~*?\\:])')


def _text_term(term: str) -> str:
    """`term` with Jira's text-search operators escaped, so it is searched as typed."""
    return _TEXT_SEARCH_RESERVED.sub(r"\\\1", term)


def search_condition(query: str, projects: Sequence[str] = ()) -> str:
    """
    JQL for free-text `query`. Just a number, or a number with any letters/dash in
    front of it (a typo'd project prefix included), matches that number in every one
    of `projects` - so typing "2268" or "ESHOPP-2268" with ECAPP and ESHOP picked
    finds ECAPP-2268 and/or ESHOP-2268 without needing the right prefix. A well-formed
    key with no project picked matches exactly; anything else matches summary,
    description and comments, each word as a prefix. Empty when `query` is blank.
    """
    query = query.strip()
    if not query:
        return ""
    number_match = _ISSUE_NUMBER.match(query)
    if number_match and projects:
        keys = [f"{p}-{number_match.group(1)}" for p in projects]
        return _scope_condition("key", keys)
    if _ISSUE_KEY.match(query):
        return f"key = {jql_string(query)}"
    return f"text ~ {jql_string(' '.join(_text_term(t) + '*' for t in query.split()))}"


__all__ = [
    "substitute_jql_variables",
    "format_jql_with_project",
    "merge_query_collections",
    "build_query_not_found_message",
    "jql_string",
    "build_issue_jql",
    "strip_order_by",
    "components_condition",
    "search_condition",
]
