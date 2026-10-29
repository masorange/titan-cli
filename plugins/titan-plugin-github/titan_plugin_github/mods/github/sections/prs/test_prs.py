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


def test_read_others_is_its_own_read(mod, pr):
    github = SimpleNamespace(list_all_prs=lambda: ClientSuccess(data=[pr(4)]))
    assert [p.number for p in mod.sections.prs.prs.read_others(github).prs] == [4]

    github.list_all_prs = lambda: ClientError(error_message="i/o timeout")
    assert mod.sections.prs.prs.read_others(github).error == "i/o timeout"


def test_a_review_decision_github_leaves_empty_does_not_block_the_merge(mod, pr):
    blockers = mod.sections.prs.merge.blockers

    assert blockers(pr(1, review="ready for review")) == []
    assert blockers(pr(1, review="review required")) == ["not approved"]


def test_unresolved_conversations_block_the_merge_and_are_counted(mod, pr):
    blockers = mod.sections.prs.merge.blockers

    assert blockers(pr(1, review="approved"), unresolved=1) == ["1 unresolved conversation"]
    assert blockers(pr(1, review="ready for review"), unresolved=3) == ["3 unresolved conversations"]


def test_threads_are_read_into_state_and_unknown_counts_as_none(mod):
    from types import SimpleNamespace
    from titan_cli.core.mods import ModBus
    from titan_cli.core.result import ClientSuccess

    m = ModBus().api("github")
    threads = mod.sections.prs.threads
    assert threads.unresolved(m, 7) == 0

    asked = []
    github = SimpleNamespace(get_pr_review_threads=lambda n, include_resolved: asked.append((n, include_resolved)) or ClientSuccess(data=[1, 2]))
    m.client = lambda name: github

    threads.read(m, 7)

    assert asked == [(7, False)] and threads.unresolved(m, 7) == 2


def test_a_failed_threads_read_blocks_nothing(mod):
    from types import SimpleNamespace
    from titan_cli.core.mods import ModBus
    from titan_cli.core.result import ClientError

    m = ModBus().api("github")
    m.client = lambda name: SimpleNamespace(get_pr_review_threads=lambda n, include_resolved: ClientError(error_message="boom"))

    mod.sections.prs.threads.read(m, 7)

    assert mod.sections.prs.threads.of(m, 7).status == "error" and mod.sections.prs.threads.unresolved(m, 7) == 0


def test_a_threads_read_that_raises_is_an_error_and_never_stays_running(mod):
    from types import SimpleNamespace
    from titan_cli.core.mods import ModBus

    m = ModBus().api("github")
    m.client = lambda name: SimpleNamespace(get_pr_review_threads=lambda n, include_resolved: 1 / 0)

    mod.sections.prs.threads.read(m, 7)

    assert mod.sections.prs.threads.of(m, 7).status == "error"


def test_only_the_open_rows_of_my_prs_are_read_again(mod, pr):
    from titan_cli.core.mods import ModBus

    m = ModBus().api("github")
    started = []
    m.run = lambda fn: started.append(True)

    mod.sections.prs.threads.reread_open(m, [pr(1), pr(2)], lambda number: number == 2)

    assert list((m.state.get("threads") or {}).keys()) == ["2"] and started == [True]
