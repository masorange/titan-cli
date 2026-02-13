"""
Tests for JQL Operations

Tests for pure business logic related to JQL query handling.
"""

from titan_plugin_jira.operations.jql_operations import (
    substitute_jql_variables,
    format_jql_with_project,
    merge_query_collections,
    build_query_not_found_message,
)


class TestSubstituteJQLVariables:
    """Tests for substitute_jql_variables function."""

    def test_substitute_single_variable(self):
        """Should substitute single variable."""
        jql = "project = ${project}"
        context = {"project": "MYPROJ"}
        result = substitute_jql_variables(jql, context)
        assert result == "project = MYPROJ"

    def test_substitute_multiple_variables(self):
        """Should substitute multiple variables."""
        jql = "project = ${project} AND status = ${status}"
        context = {"project": "MYPROJ", "status": "Open"}
        result = substitute_jql_variables(jql, context)
        assert result == "project = MYPROJ AND status = Open"

    def test_missing_variable_keeps_placeholder(self):
        """Should keep placeholder when variable not in context."""
        jql = "project = ${project}"
        context = {}
        result = substitute_jql_variables(jql, context)
        assert result == "project = ${project}"

    def test_partial_substitution(self):
        """Should substitute available variables and keep others."""
        jql = "project = ${p1} AND status = ${p2}"
        context = {"p1": "MYPROJ"}
        result = substitute_jql_variables(jql, context)
        assert result == "project = MYPROJ AND status = ${p2}"

    def test_no_variables(self):
        """Should return unchanged when no variables."""
        jql = "project = MYPROJ"
        context = {"project": "OTHER"}
        result = substitute_jql_variables(jql, context)
        assert result == "project = MYPROJ"

    def test_numeric_values(self):
        """Should convert numeric values to strings."""
        jql = "priority = ${priority}"
        context = {"priority": 1}
        result = substitute_jql_variables(jql, context)
        assert result == "priority = 1"

    def test_complex_jql(self):
        """Should handle complex JQL queries."""
        jql = "project = ${proj} AND fixVersion = ${version} AND status IN (${status1}, ${status2})"
        context = {"proj": "MYPROJ", "version": "1.0", "status1": "Open", "status2": "In Progress"}
        result = substitute_jql_variables(jql, context)
        assert "MYPROJ" in result
        assert "1.0" in result
        assert "Open" in result
        assert "In Progress" in result


class TestFormatJQLWithProject:
    """Tests for format_jql_with_project function."""

    def test_format_with_project(self):
        """Should format JQL with project parameter."""
        jql = "project = {project} AND status = Open"
        formatted, error = format_jql_with_project(jql, "MYPROJ")
        assert formatted == "project = MYPROJ AND status = Open"
        assert error is None

    def test_no_project_placeholder(self):
        """Should return unchanged when no project placeholder."""
        jql = "status = Open"
        formatted, error = format_jql_with_project(jql, "MYPROJ")
        assert formatted == "status = Open"
        assert error is None

    def test_missing_project_when_required(self):
        """Should return error when project required but missing."""
        jql = "project = {project}"
        formatted, error = format_jql_with_project(jql, None)
        assert formatted == "project = {project}"
        assert error is not None
        assert "project parameter" in error

    def test_no_project_when_not_needed(self):
        """Should work fine when no project needed and none provided."""
        jql = "status = Open"
        formatted, error = format_jql_with_project(jql, None)
        assert formatted == "status = Open"
        assert error is None


class TestMergeQueryCollections:
    """Tests for merge_query_collections function."""

    def test_merge_no_overlap(self):
        """Should merge queries with no overlap."""
        predefined = {"q1": "jql1", "q2": "jql2"}
        custom = {"q3": "jql3", "q4": "jql4"}
        merged = merge_query_collections(predefined, custom)
        assert len(merged) == 4
        assert merged["q1"] == "jql1"
        assert merged["q3"] == "jql3"

    def test_custom_overrides_predefined(self):
        """Should let custom queries override predefined ones."""
        predefined = {"q1": "predefined_jql", "q2": "jql2"}
        custom = {"q1": "custom_jql"}
        merged = merge_query_collections(predefined, custom)
        assert merged["q1"] == "custom_jql"
        assert merged["q2"] == "jql2"

    def test_empty_custom(self):
        """Should work with empty custom queries."""
        predefined = {"q1": "jql1"}
        custom = {}
        merged = merge_query_collections(predefined, custom)
        assert merged == predefined

    def test_empty_predefined(self):
        """Should work with empty predefined queries."""
        predefined = {}
        custom = {"q1": "jql1"}
        merged = merge_query_collections(predefined, custom)
        assert merged == custom

    def test_both_empty(self):
        """Should work with both empty."""
        merged = merge_query_collections({}, {})
        assert merged == {}


class TestBuildQueryNotFoundMessage:
    """Tests for build_query_not_found_message function."""

    def test_basic_message(self):
        """Should build message with query name."""
        predefined = {"q1": "jql1"}
        custom = {}
        msg = build_query_not_found_message("missing", predefined, custom)
        assert "missing" in msg
        assert "not found" in msg

    def test_lists_predefined_queries(self):
        """Should list predefined queries."""
        predefined = {"q1": "jql1", "q2": "jql2"}
        custom = {}
        msg = build_query_not_found_message("missing", predefined, custom)
        assert "q1" in msg
        assert "q2" in msg

    def test_limits_predefined_list(self):
        """Should limit number of predefined queries shown."""
        predefined = {f"q{i}": f"jql{i}" for i in range(20)}
        custom = {}
        msg = build_query_not_found_message("missing", predefined, custom, max_predefined_shown=5)
        # Should show first 5
        assert "q0" in msg or "q1" in msg
        # Should indicate more available
        assert "more" in msg

    def test_lists_custom_queries(self):
        """Should list custom queries separately."""
        predefined = {"q1": "jql1"}
        custom = {"c1": "custom1", "c2": "custom2"}
        msg = build_query_not_found_message("missing", predefined, custom)
        assert "Custom" in msg or "custom" in msg
        assert "c1" in msg
        assert "c2" in msg

    def test_hints_when_no_custom(self):
        """Should provide hint when no custom queries."""
        predefined = {"q1": "jql1"}
        custom = {}
        msg = build_query_not_found_message("missing", predefined, custom)
        assert "config.toml" in msg or ".titan" in msg

    def test_includes_query_name(self):
        """Should include the missing query name."""
        msg = build_query_not_found_message("my_missing_query", {"q1": "jql"}, {})
        assert "my_missing_query" in msg
