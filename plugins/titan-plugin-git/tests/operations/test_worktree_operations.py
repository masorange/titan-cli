"""
Tests for Worktree Operations

Tests for pure business logic about which worktrees may be removed.
"""

from titan_plugin_git.models.view.worktree import UIGitWorktree
from titan_plugin_git.operations.worktree_operations import (
    main_worktree_path,
    removable_worktrees,
    removal_blocked_by,
    same_path,
)


def worktree(path, bare=False):
    return UIGitWorktree(path=path, path_short=path.rsplit("/", 1)[-1], is_bare=bare)


class TestMainWorktreePath:
    """Tests for main_worktree_path function."""

    def test_the_first_one_git_prints_is_the_main_worktree(self):
        assert main_worktree_path([worktree("/repo"), worktree("/repo-review")]) == "/repo"

    def test_no_worktrees_has_no_main(self):
        assert main_worktree_path([]) == ""


class TestSamePath:
    """Tests for same_path function."""

    def test_a_trailing_slash_is_the_same_place(self, tmp_path):
        assert same_path(str(tmp_path), f"{tmp_path}/") is True

    def test_different_paths_are_not(self, tmp_path):
        assert same_path(str(tmp_path), str(tmp_path / "other")) is False

    def test_an_empty_path_matches_nothing(self):
        assert same_path("", "") is False
        assert same_path("/repo", "") is False


class TestRemovalBlockedBy:
    """Tests for removal_blocked_by function."""

    def test_another_worktree_can_be_removed(self):
        assert removal_blocked_by(worktree("/repo-review"), "/repo", "/repo") is None

    def test_the_main_worktree_cannot(self):
        """Git itself refuses it."""
        assert removal_blocked_by(worktree("/repo"), "/repo", "/elsewhere") == "the main worktree"

    def test_the_one_you_are_in_cannot(self):
        """Removing it would pull the floor from under the running session."""
        assert removal_blocked_by(worktree("/repo-review"), "/repo", "/repo-review") == "the worktree you are in"

    def test_a_bare_repository_cannot(self):
        assert removal_blocked_by(worktree("/repo.git", bare=True), "/other", "/other") == "the bare repository"


class TestRemovableWorktrees:
    """Tests for removable_worktrees function."""

    def test_keeps_only_what_can_go(self):
        worktrees = [worktree("/repo"), worktree("/repo-review"), worktree("/repo-hotfix")]

        removable = removable_worktrees(worktrees, current_path="/repo-hotfix")

        assert [w.path for w in removable] == ["/repo-review"]
