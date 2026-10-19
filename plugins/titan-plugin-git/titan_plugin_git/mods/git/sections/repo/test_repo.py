"""Reading the branch, its churn (new files included) and recent commits."""
from types import SimpleNamespace

from titan_cli.core.result import ClientSuccess


def test_read_repo_combines_status_numstat_and_log(mod, tmp_path):
    numstat_calls = []
    commit = SimpleNamespace(short_hash="abc1234", message_subject="feat: y (#9)", pr_number=9, formatted_date="2026-10-06")
    git = SimpleNamespace(
        get_status=lambda: ClientSuccess(data=SimpleNamespace(branch="feat/x", has_upstream=True, ahead=2, behind=1)),
        get_uncommitted_numstat=lambda include_untracked: numstat_calls.append(include_untracked) or ClientSuccess(
            data=[SimpleNamespace(additions=5, deletions=3), SimpleNamespace(additions=2, deletions=0)]
        ),
        get_commits=lambda root, limit: ClientSuccess(data=[commit]),
    )

    repo = mod.sections.repo.repo.read_repo(git, tmp_path, {"recent_commits": 10})

    assert (repo.branch, repo.ahead, repo.behind, repo.added, repo.removed) == ("feat/x", 2, 1, 7, 3)
    assert numstat_calls == [True]  # new files count too
    assert repo.commits == [commit]


def test_read_repo_without_git_says_so(mod, tmp_path):
    assert mod.sections.repo.repo.read_repo(None, tmp_path, {}).error == "git plugin not available"
