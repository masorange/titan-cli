"""
Tests for Branch Operations

Tests for pure business logic related to Git branch management.
"""

from titan_plugin_git.models.view.branch import UIGitBranch
from titan_plugin_git.models.view.status import UIGitStatus
from titan_plugin_git.operations.branch_operations import (
    check_branch_exists,
    determine_safe_checkout_target,
    filter_branches,
    merge_sources,
    order_branches_by_use,
    parse_checkout_targets,
    push_rejected_hint,
    should_delete_before_create,
    switching_blocked_by,
)


def branch(name, current=False):
    return UIGitBranch(name=name, display_name=name, is_current=current, is_remote=False)


def status(modified=(), staged=(), untracked=()):
    return UIGitStatus(
        branch="feature",
        is_clean=not (modified or staged or untracked),
        modified_files=list(modified),
        untracked_files=list(untracked),
        staged_files=list(staged),
    )


class TestCheckBranchExists:
    """Tests for check_branch_exists function."""

    def test_branch_exists(self):
        """Should return True when branch exists."""
        assert check_branch_exists("main", ["main", "develop"]) is True

    def test_branch_does_not_exist(self):
        """Should return False when branch doesn't exist."""
        assert check_branch_exists("feature", ["main", "develop"]) is False

    def test_empty_branch_list(self):
        """Should return False for empty branch list."""
        assert check_branch_exists("main", []) is False

    def test_case_sensitive(self):
        """Should be case-sensitive."""
        assert check_branch_exists("Main", ["main"]) is False
        assert check_branch_exists("main", ["main"]) is True


class TestDetermineSafeCheckoutTarget:
    """Tests for determine_safe_checkout_target function."""

    def test_not_on_target_branch(self):
        """Should return None when not on the branch to delete."""
        result = determine_safe_checkout_target(
            current_branch="feature",
            branch_to_delete="other",
            main_branch="main",
            all_branches=["main", "feature", "other"]
        )
        assert result is None

    def test_on_target_with_available_main(self):
        """Should return main branch when on target and main exists."""
        result = determine_safe_checkout_target(
            current_branch="feature",
            branch_to_delete="feature",
            main_branch="main",
            all_branches=["main", "feature"]
        )
        assert result == "main"

    def test_on_target_main_not_available(self):
        """Should return None when main branch doesn't exist."""
        result = determine_safe_checkout_target(
            current_branch="feature",
            branch_to_delete="feature",
            main_branch="main",
            all_branches=["feature", "develop"]
        )
        assert result is None

    def test_trying_to_delete_main_itself(self):
        """Should return None when trying to delete main branch."""
        result = determine_safe_checkout_target(
            current_branch="main",
            branch_to_delete="main",
            main_branch="main",
            all_branches=["main", "develop"]
        )
        assert result is None

    def test_on_main_deleting_other(self):
        """Should return None when on main and deleting another branch."""
        result = determine_safe_checkout_target(
            current_branch="main",
            branch_to_delete="feature",
            main_branch="main",
            all_branches=["main", "feature"]
        )
        assert result is None

    def test_master_as_main_branch(self):
        """Should work with 'master' as main branch name."""
        result = determine_safe_checkout_target(
            current_branch="feature",
            branch_to_delete="feature",
            main_branch="master",
            all_branches=["master", "feature"]
        )
        assert result == "master"


class TestShouldDeleteBeforeCreate:
    """Tests for should_delete_before_create function."""

    def test_exists_and_should_delete(self):
        """Should return True when branch exists and deletion requested."""
        assert should_delete_before_create(
            branch_exists=True,
            delete_if_exists=True
        ) is True

    def test_exists_but_no_delete_flag(self):
        """Should return False when branch exists but no deletion requested."""
        assert should_delete_before_create(
            branch_exists=True,
            delete_if_exists=False
        ) is False

    def test_does_not_exist_with_delete_flag(self):
        """Should return False when branch doesn't exist (even with delete flag)."""
        assert should_delete_before_create(
            branch_exists=False,
            delete_if_exists=True
        ) is False

    def test_does_not_exist_no_delete_flag(self):
        """Should return False when branch doesn't exist and no deletion requested."""
        assert should_delete_before_create(
            branch_exists=False,
            delete_if_exists=False
        ) is False


class TestParseCheckoutTargets:
    """Tests for parse_checkout_targets function."""

    def test_reads_the_branches_head_moved_to(self):
        """Should return checkout targets, newest first."""
        reflog = "\n".join([
            "checkout: moving from main to feature",
            "commit: feat: something",
            "checkout: moving from feature to main",
        ])
        assert parse_checkout_targets(reflog) == ["feature", "main"]

    def test_keeps_each_branch_once(self):
        """Should keep only the most recent visit to a branch."""
        reflog = "\n".join([
            "checkout: moving from main to feature",
            "checkout: moving from feature to main",
            "checkout: moving from main to feature",
        ])
        assert parse_checkout_targets(reflog) == ["feature", "main"]

    def test_ignores_everything_that_is_not_a_checkout(self):
        """Should ignore commits, merges, resets and empty output."""
        assert parse_checkout_targets("commit: feat: x\nmerge main: Fast-forward") == []
        assert parse_checkout_targets("") == []


class TestOrderBranchesByUse:
    """Tests for order_branches_by_use function."""

    def test_current_branch_leads_then_the_visited_ones(self):
        """Should put the current branch first and the rest in visit order."""
        branches = [branch("main"), branch("feature", current=True), branch("old")]

        ordered = order_branches_by_use(branches, ["main", "feature"])

        assert [b.name for b in ordered] == ["feature", "main", "old"]

    def test_unvisited_branches_keep_the_order_given(self):
        """Should fall back to the caller's order (last commit date) for the rest."""
        branches = [branch("recent"), branch("older"), branch("oldest")]

        ordered = order_branches_by_use(branches, [])

        assert [b.name for b in ordered] == ["recent", "older", "oldest"]

    def test_unknown_visited_branches_are_dropped(self):
        """Should ignore reflog entries that are not local branches (a detached hash)."""
        ordered = order_branches_by_use([branch("main")], ["a1b2c3d", "gone"])

        assert [b.name for b in ordered] == ["main"]

    def test_limit_cuts_the_tail(self):
        """Should return at most `limit` branches."""
        branches = [branch("a"), branch("b"), branch("c")]

        assert len(order_branches_by_use(branches, [], limit=2)) == 2
        assert len(order_branches_by_use(branches, [], limit=None)) == 3


class TestFilterBranches:
    """Tests for filter_branches function."""

    def test_matches_part_of_the_name_ignoring_case(self):
        branches = [branch("feature/login"), branch("main")]

        assert [b.name for b in filter_branches(branches, "LOG")] == ["feature/login"]

    def test_empty_query_keeps_everything(self):
        branches = [branch("feature/login"), branch("main")]

        assert len(filter_branches(branches, "  ")) == 2


class TestMergeSources:
    """Tests for merge_sources function."""

    def test_the_base_branch_comes_first(self):
        branches = [branch("feature/login"), branch("release"), branch("main")]

        assert [b.name for b in merge_sources(branches, "feature/x", "main")] == [
            "main", "feature/login", "release",
        ]

    def test_the_target_is_never_a_source(self):
        """A branch cannot be merged into itself."""
        branches = [branch("main"), branch("feature/login")]

        assert [b.name for b in merge_sources(branches, "main", "main")] == ["feature/login"]

    def test_without_a_base_branch_the_order_is_kept(self):
        branches = [branch("feature/login"), branch("release")]

        assert [b.name for b in merge_sources(branches, "feature/x", "")] == ["feature/login", "release"]

    def test_a_base_branch_that_is_not_listed_changes_nothing(self):
        branches = [branch("feature/login"), branch("release")]

        assert [b.name for b in merge_sources(branches, "feature/x", "develop")] == ["feature/login", "release"]


class TestPushRejectedHint:
    """Tests for push_rejected_hint function."""

    def test_a_rejected_push_is_explained(self):
        error = "! [rejected] feat/x -> feat/x (non-fast-forward)"

        assert "force push by hand" in push_rejected_hint(error)

    def test_fetch_first_counts_as_a_rejection(self):
        assert push_rejected_hint("Updates were rejected because the remote contains work. fetch first") is not None

    def test_any_other_failure_has_no_hint(self):
        """Nothing to force here, so suggesting it would be wrong."""
        assert push_rejected_hint("fatal: 'origin' does not appear to be a git repository") is None

    def test_no_message_has_no_hint(self):
        assert push_rejected_hint("") is None


class TestSwitchingBlockedBy:
    """Tests for switching_blocked_by function."""

    def test_clean_tree_does_not_block(self):
        assert switching_blocked_by(status()) is None

    def test_untracked_files_do_not_block(self):
        """Untracked files follow HEAD anywhere, so git never refuses over them."""
        assert switching_blocked_by(status(untracked=["notes.md"])) is None

    def test_modified_and_staged_files_block(self):
        reason = switching_blocked_by(status(modified=["a.py"], staged=["b.py"]))

        assert reason == "2 uncommitted files - commit or stash before switching"

    def test_a_file_both_modified_and_staged_counts_once(self):
        reason = switching_blocked_by(status(modified=["a.py"], staged=["a.py"]))

        assert reason == "1 uncommitted file - commit or stash before switching"


def test_format_relative_reads_git_timestamps():
    from datetime import datetime, timedelta, timezone

    from titan_plugin_git.models.formatting import format_relative

    now = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)

    assert format_relative("2026-10-19T09:00:00+00:00", now) == "today"
    assert format_relative("2026-10-18T09:00:00+00:00", now) == "yesterday"
    assert format_relative("2026-10-16T09:00:00+00:00", now) == "3 d"
    assert format_relative("2026-10-01T09:00:00+00:00", now) == "2 w"
    assert format_relative("2026-06-01T09:00:00+00:00", now) == "4 mo"
    assert format_relative("2024-06-01T09:00:00+00:00", now) == "2 y"
    # `--date=iso8601` prints a space before the zone, and a zone of its own
    assert format_relative("2026-10-16 09:00:00 +0200", now) == "3 d"
    # Nothing readable is shown as nothing, never as an error
    assert format_relative("", now) == ""
    assert format_relative("not a date", now) == ""
    assert format_relative(now - timedelta(days=2), now) == "2 d"


def test_branch_mapper_formats_the_last_commit_date():
    from titan_plugin_git.models.mappers.branch_mapper import from_network_branch
    from titan_plugin_git.models.network.branch import NetworkGitBranch

    mapped = from_network_branch(NetworkGitBranch(name="feature", last_commit_date="2026-10-19T09:00:00+00:00"))

    assert mapped.last_commit_date == "2026-10-19T09:00:00+00:00"
    assert mapped.formatted_date  # the relative wording itself is tested above


# --- Naming a new branch -------------------------------------------------


def test_branch_prefixes_come_from_the_branches_the_repo_already_has():
    """The convention is whatever the repository does, so it is read, never assumed."""
    from titan_plugin_git.operations.branch_operations import branch_name_prefixes

    names = ["feat/login", "feat/logout", "fix/crash", "main", "improvement/speed"]

    assert branch_name_prefixes(names) == ["feat", "fix", "improvement"]
    assert branch_name_prefixes(names, limit=1) == ["feat"]
    assert branch_name_prefixes(["main", "develop"]) == []


def test_a_new_branch_name_is_judged_before_git_is_asked():
    from titan_plugin_git.operations.branch_operations import validate_branch_name

    assert validate_branch_name("feat/login") is None
    assert validate_branch_name("  ") == "the name is empty"
    assert validate_branch_name("feat/login", ["feat/login"]) == "that branch already exists"
    assert validate_branch_name("feat//login").startswith("a name cannot")
    assert validate_branch_name("feat/login.lock") == "git does not allow that name"
    assert validate_branch_name("feat/log in").startswith("no spaces")
    assert validate_branch_name("feat/log..in").startswith("no spaces")


def test_a_typed_name_is_put_in_the_shape_git_accepts():
    from titan_plugin_git.operations.branch_operations import normalize_branch_name

    assert normalize_branch_name("  Feat/Switch  Branch ") == "feat/switch-branch"
    assert normalize_branch_name("feat/log_in") == "feat/log-in"
    assert normalize_branch_name("feat/a:b") == "feat/a-b"
    assert normalize_branch_name("/feat/x/") == "feat/x"
    assert normalize_branch_name("   ") == ""


def test_the_name_is_read_out_of_whatever_wrapping_the_model_puts_around_it():
    from titan_plugin_git.operations.branch_operations import parse_suggested_branch_name

    assert parse_suggested_branch_name("feat/switch-branch") == "feat/switch-branch"
    assert parse_suggested_branch_name("Branch: `feat/Switch Branch`") == "feat/switch-branch"
    assert parse_suggested_branch_name("```\nfix/null-pointer\n```") == "fix/null-pointer"
    assert parse_suggested_branch_name("- improvement/faster-diff") == "improvement/faster-diff"
    assert parse_suggested_branch_name("") == ""


def test_the_prompt_carries_the_repo_s_prefixes_and_pr_labels():
    """Both differ in every repository, so the model is told instead of guessing."""
    from titan_plugin_git.operations.branch_operations import build_branch_name_prompt

    prompt, system = build_branch_name_prompt("api.py | 2 +-", "@@ -1 +1 @@", ["feat", "fix"], ["bug"])

    assert "feat, fix" in prompt and "bug" in prompt
    assert "api.py | 2 +-" in prompt and "@@ -1 +1 @@" in prompt
    assert "branch name only" in system

    # Nothing to say about either is said as nothing, not as an empty list.
    bare, _ = build_branch_name_prompt("api.py | 2 +-", "")
    assert "Prefixes" not in bare and "Labels" not in bare and "Diff:" not in bare
