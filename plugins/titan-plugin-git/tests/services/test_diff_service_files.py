"""Diff service: the per-file reads behind the git workspace, against a real repository."""
import subprocess

import pytest
from titan_cli.core.result import ClientError, ClientSuccess
from titan_plugin_git.clients.network import GitNetwork
from titan_plugin_git.clients.services.diff_service import DiffService


def _git(root, *args):
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "keep.txt").write_text("one\ntwo\n")
    (tmp_path / "gone.txt").write_text("bye\n")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "first")
    (tmp_path / "keep.txt").write_text("one\nTWO\nthree\n")
    (tmp_path / "new.txt").write_text("fresh\n")
    (tmp_path / "gone.txt").unlink()
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "second")
    return tmp_path


@pytest.fixture
def service(repo):
    return DiffService(GitNetwork(repo_path=str(repo)))


def _by_path(files):
    return {f.path: f for f in files}


def test_commit_files_report_state_and_counters(service):
    result = service.get_commit_files("HEAD")

    assert isinstance(result, ClientSuccess)
    files = _by_path(result.data)
    assert (files["keep.txt"].status, files["keep.txt"].additions, files["keep.txt"].deletions) == ("M", 2, 1)
    assert (files["new.txt"].status, files["new.txt"].additions) == ("A", 1)
    assert (files["gone.txt"].status, files["gone.txt"].deletions) == ("D", 1)


def test_root_commit_lists_its_files(service):
    result = service.get_commit_files("HEAD~1")

    assert {f.path for f in result.data} == {"keep.txt", "gone.txt"}


def test_commit_file_diff_is_parsed(service):
    result = service.get_commit_file_diff("HEAD", "keep.txt")

    assert isinstance(result, ClientSuccess)
    kinds = [line.kind for line in result.data.hunks[0].lines]
    assert kinds == ["context", "del", "add", "add"]


def test_unknown_commit_is_an_error(service):
    assert isinstance(service.get_commit_files("nope"), ClientError)
    assert isinstance(service.get_commit_file_diff("nope", "keep.txt"), ClientError)


def test_uncommitted_files_keep_index_and_working_tree_apart(service, repo):
    (repo / "keep.txt").write_text("one\nTWO\nthree\nfour\n")
    _git(repo, "add", "keep.txt")
    (repo / "keep.txt").write_text("one\nTWO\nthree\nfour\nfive\n")
    (repo / "loose.txt").write_text("a\nb\n")

    result = service.get_uncommitted_files()

    assert isinstance(result, ClientSuccess)
    assert [(f.path, f.status, f.additions) for f in result.data.staged] == [("keep.txt", "M", 1)]
    unstaged = _by_path(result.data.unstaged)
    assert (unstaged["keep.txt"].status, unstaged["keep.txt"].additions) == ("M", 1)
    assert (unstaged["loose.txt"].status, unstaged["loose.txt"].additions) == ("?", 2)


def test_worktree_file_diff_reads_the_side_asked_for(service, repo):
    (repo / "keep.txt").write_text("one\nTWO\nthree\nfour\n")
    _git(repo, "add", "keep.txt")
    (repo / "keep.txt").write_text("one\nTWO\nthree\nfour\nfive\n")

    staged = service.get_worktree_file_diff("keep.txt", staged=True).data
    unstaged = service.get_worktree_file_diff("keep.txt", staged=False).data

    assert [line.text for h in staged.hunks for line in h.lines if line.kind == "add"] == ["four"]
    assert [line.text for h in unstaged.hunks for line in h.lines if line.kind == "add"] == ["five"]


def test_untracked_file_diff_is_all_additions_and_leaves_the_index_alone(service, repo):
    (repo / "loose.txt").write_text("a\nb\n")

    diff = service.get_worktree_file_diff("loose.txt").data

    assert [line.kind for h in diff.hunks for line in h.lines] == ["add", "add"]
    staged = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=repo, capture_output=True, text=True)
    assert staged.stdout == ""
