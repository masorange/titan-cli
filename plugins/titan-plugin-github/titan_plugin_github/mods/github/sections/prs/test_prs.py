"""Reading review requests and the user's own PRs."""
from types import SimpleNamespace

from titan_cli.core.result import ClientError, ClientSuccess


def test_read_prs_and_the_error_path(mod, pr):
    github = SimpleNamespace(
        get_repo_full_name=lambda: "o/r",
        list_pending_review_prs=lambda: ClientSuccess(data=[pr(1)]),
        list_my_prs=lambda: ClientSuccess(data=[pr(2), pr(3)]),
        count_open_prs=lambda: ClientSuccess(data=742),
    )
    prs = mod.sections.prs.prs.read_prs(github)
    assert ([p.number for p in prs.to_review], [p.number for p in prs.mine], prs.open_count, prs.repo) == ([1], [2, 3], 742, "o/r")

    github.list_my_prs = lambda: ClientError(error_message="gh: not logged in")
    assert mod.sections.prs.prs.read_prs(github).error == "gh: not logged in"


def test_new_review_requests_only_after_a_good_poll(mod, pr):
    first = mod.models.Prs(to_review=[pr(1)])
    second = mod.models.Prs(to_review=[pr(1), pr(5)])
    assert mod.sections.prs.prs.new_review_requests(None, first) == []
    assert mod.sections.prs.prs.new_review_requests(first, second) == [5]
    assert mod.sections.prs.prs.new_review_requests(mod.models.Prs(error="down"), second) == []
