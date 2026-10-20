"""Reading the branch, its churn (new files included) and recent commits."""
from types import SimpleNamespace

from titan_cli.core.result import ClientSuccess
from titan_plugin_git.models.view import UIGitCommit


def _commit(sha: str, *parents: str) -> UIGitCommit:
    return UIGitCommit(
        hash=sha, short_hash=sha[:7], message=sha, message_subject=sha,
        author="A <a@b.c>", author_short="A", date="2026-10-20", formatted_date="2026-10-20",
        parents=list(parents),
    )


def test_read_repo_combines_status_numstat_and_log(mod, tmp_path):
    numstat_calls = []
    commit = _commit("abc1234567")
    git = SimpleNamespace(
        get_status=lambda: ClientSuccess(data=SimpleNamespace(branch="feat/x", has_upstream=True, ahead=2, behind=1)),
        get_uncommitted_numstat=lambda include_untracked: numstat_calls.append(include_untracked) or ClientSuccess(
            data=[SimpleNamespace(additions=5, deletions=3), SimpleNamespace(additions=2, deletions=0)]
        ),
        get_commits=lambda root, limit, all_branches=False: ClientSuccess(data=[commit]),
    )

    repo = mod.sections.repo.repo.read_repo(git, tmp_path, {"recent_commits": 10})

    assert (repo.branch, repo.ahead, repo.behind, repo.added, repo.removed) == ("feat/x", 2, 1, 7, 3)
    assert numstat_calls == [True]  # new files count too
    assert repo.commits == [commit]


def test_read_repo_without_git_says_so(mod, tmp_path):
    assert mod.sections.repo.repo.read_repo(None, tmp_path, {}).error == "git plugin not available"


def test_read_repo_lays_the_commits_out_in_lanes(mod, tmp_path):
    merge = _commit("m", "trunk", "side")
    git = SimpleNamespace(
        get_status=lambda: ClientSuccess(data=SimpleNamespace(branch="feat/x", has_upstream=True, ahead=0, behind=0)),
        get_uncommitted_numstat=lambda include_untracked: ClientSuccess(data=[]),
        get_commits=lambda root, limit, all_branches=False: ClientSuccess(
            data=[merge, _commit("trunk", "base"), _commit("side", "base"), _commit("base")]
        ),
    )

    repo = mod.sections.repo.repo.read_repo(git, tmp_path, {"recent_commits": 10})

    # One row per commit plus the link row the merge's two parents need.
    assert len(repo.rows) == 5
    assert repo.rows[0].commit is merge
    assert repo.rows[1].is_link


def test_read_repo_walks_every_branch_unless_told_not_to(mod, tmp_path):
    asked = []
    git = SimpleNamespace(
        get_status=lambda: ClientSuccess(data=SimpleNamespace(branch="master", has_upstream=True, ahead=0, behind=0)),
        get_uncommitted_numstat=lambda include_untracked: ClientSuccess(data=[]),
        get_commits=lambda root, limit, all_branches=False: asked.append(all_branches) or ClientSuccess(data=[]),
    )

    mod.sections.repo.repo.read_repo(git, tmp_path, {"recent_commits": 10})
    mod.sections.repo.repo.read_repo(git, tmp_path, {"recent_commits": 10, "graph_all_branches": False})

    assert asked == [True, False]
