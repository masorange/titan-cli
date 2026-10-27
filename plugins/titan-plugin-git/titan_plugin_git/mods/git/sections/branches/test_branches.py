"""Reading the branches to switch to, and switching through the client."""
from types import SimpleNamespace

from titan_cli.core.result import ClientError, ClientSuccess


def branch(name, current=False):
    return SimpleNamespace(name=name, is_current=current, formatted_date="2 d", upstream_info="")


def fake_git(status=None, branches=(), checkout=None, pull=None, pulled=None, push=None, pushed=None,
             local=(), remote=(), checked_out=None):
    def do_checkout(name):
        if checked_out is not None:
            checked_out.append(name)
        return checkout or ClientSuccess(data=None)

    return SimpleNamespace(
        get_branches=lambda remote_=False, **kw: ClientSuccess(data=list(remote if kw.get("remote", remote_) else local)),
        get_status=lambda: ClientSuccess(data=status or SimpleNamespace(
            branch="feature", modified_files=[], staged_files=[], untracked_files=[])),
        list_recent_branches=lambda limit: ClientSuccess(data=list(branches)),
        checkout=do_checkout,
        pull=lambda remote, branch: (pulled is not None and pulled.append((remote, branch)),
                                     pull or ClientSuccess(data=None))[1],
        push=lambda remote, branch: (pushed is not None and pushed.append((remote, branch)),
                                     push or ClientSuccess(data=None))[1],
    )


def bus_for(git):
    """A mod API whose host hands out `git` and records its toasts."""
    from titan_cli.core.mods import ModBus

    toasts = []
    bus = ModBus()
    bus.host = SimpleNamespace(
        repaint=lambda mod: None,
        client=lambda name: git,
        toast=lambda mod, text, severity: toasts.append((text, severity)),
        run=lambda mod, fn: fn(),  # straight through, so a press is testable without a thread
    )
    return bus.api("git"), toasts


def test_read_branches_reports_the_branches_and_a_clean_tree(mod):
    git = fake_git(branches=[branch("feature", current=True), branch("main")])

    branches = mod.sections.branches.branches.read_branches(git, {"recent_branches": 8})

    assert [b.name for b in branches.items] == ["feature", "main"]
    assert (branches.current, branches.blocked, branches.error) == ("feature", None, None)


def test_read_branches_blocks_on_uncommitted_work_but_still_lists(mod):
    """The list stays, so the user sees where they could go once they commit."""
    status = SimpleNamespace(branch="feature", modified_files=["a.py"], staged_files=[], untracked_files=["new.md"])
    git = fake_git(status=status, branches=[branch("main")])

    branches = mod.sections.branches.branches.read_branches(git, {"recent_branches": 8})

    assert branches.blocked == "1 uncommitted file - commit or stash before switching"
    assert [b.name for b in branches.items] == ["main"]


def test_read_branches_without_git_says_so(mod):
    assert mod.sections.branches.branches.read_branches(None, {}).error == "git plugin not available"


def test_switch_to_checks_out_and_refreshes(mod):
    from titan_cli.core.mods import ModBus

    toasts, refreshed = [], []
    bus = ModBus()
    bus.host = SimpleNamespace(
        repaint=lambda mod: None,
        client=lambda name: fake_git(),
        toast=lambda mod, text, severity: toasts.append((text, severity)),
    )
    m = bus.api("git")
    m.state.set("refresh", lambda: refreshed.append(True))

    mod.sections.branches.branches.switch_to(m, "main")

    assert toasts == [("Switched to main", "information")]
    assert refreshed == [True]


def test_switch_to_reports_a_failed_checkout(mod):
    from titan_cli.core.mods import ModBus

    toasts, refreshed = [], []
    bus = ModBus()
    bus.host = SimpleNamespace(
        repaint=lambda mod: None,
        client=lambda name: fake_git(checkout=ClientError(error_message="would be overwritten")),
        toast=lambda mod, text, severity: toasts.append((text, severity)),
    )
    m = bus.api("git")
    m.state.set("refresh", lambda: refreshed.append(True))

    mod.sections.branches.branches.switch_to(m, "main")

    assert toasts == [("Could not switch to main: would be overwritten", "error")]
    assert refreshed == [True]  # the pane is redrawn from git either way


def test_a_press_shows_the_progress_until_the_answer_arrives(mod):
    """The claim is what the card draws its progress line from, and it is released after."""
    pulled, seen = [], []
    git = fake_git(pulled=pulled)
    m, toasts = bus_for(git)
    m.state.set("refresh", lambda: seen.append(mod.sections.branches.branches.running(m)))

    # m.run is synchronous here, so the claim is observed through the refresh.
    mod.sections.branches.branches.start_remote(m, "pull", "feature")

    assert pulled == [("origin", "feature")]
    assert toasts == [("Pulled origin/feature", "information")]
    assert seen == [None]  # cleared before the card is read again
    assert mod.sections.branches.branches.running(m) is None


def test_a_second_press_while_one_runs_does_nothing(mod):
    """Two quick presses both saw the branch free; only the first one sends."""
    pulled = []
    m, _ = bus_for(fake_git(pulled=pulled))
    m.state.set("remote_action", "pull")  # one already in flight

    mod.sections.branches.branches.start_remote(m, "pull", "feature")

    assert pulled == []
    assert mod.sections.branches.branches.running(m) == "pull"


def test_pull_pulls_the_branch_from_origin_and_refreshes(mod):
    pulled, refreshed = [], []
    m, toasts = bus_for(fake_git(pulled=pulled))
    m.state.set("refresh", lambda: refreshed.append(True))

    mod.sections.branches.branches.run_remote(m, "pull", "feature")

    assert pulled == [("origin", "feature")]
    assert toasts == [("Pulled origin/feature", "information")]
    assert refreshed == [True]


def test_pull_reports_a_refused_pull(mod):
    """Git refuses a pull over uncommitted work; the card says so instead of hiding it."""
    refreshed = []
    m, toasts = bus_for(fake_git(pull=ClientError(error_message="local changes would be overwritten")))
    m.state.set("refresh", lambda: refreshed.append(True))

    mod.sections.branches.branches.run_remote(m, "pull", "feature")

    assert toasts == [("Could not pull origin/feature: local changes would be overwritten", "error")]
    assert refreshed == [True]


def test_push_pushes_the_branch_to_origin(mod):
    pushed = []
    m, toasts = bus_for(fake_git(pushed=pushed))

    mod.sections.branches.branches.run_remote(m, "push", "feature")

    assert pushed == [("origin", "feature")]
    assert toasts == [("Pushed feature to origin", "information")]


def test_push_explains_a_rejected_push_instead_of_forcing_it(mod):
    """A force push would drop the remote's commits, so the pane only says so."""
    rejected = "! [rejected] feature -> feature (non-fast-forward)"
    m, toasts = bus_for(fake_git(push=ClientError(error_message=rejected)))

    mod.sections.branches.branches.run_remote(m, "push", "feature")

    (text, severity), = toasts
    assert severity == "error"
    assert rejected in text and "force push by hand" in text


def test_push_reports_any_other_failure_as_git_worded_it(mod):
    m, toasts = bus_for(fake_git(push=ClientError(error_message="fatal: no remote named origin")))

    mod.sections.branches.branches.run_remote(m, "push", "feature")

    assert toasts == [("Could not push feature: fatal: no remote named origin", "error")]


def test_a_failure_still_releases_the_claim(mod):
    """A card stuck on its progress line would need a restart to press again."""
    m, _ = bus_for(fake_git(push=ClientError(error_message="boom")))

    mod.sections.branches.branches.run_remote(m, "push", "feature")

    assert mod.sections.branches.branches.running(m) is None


def ui_branch(name, current=False, remote=False):
    from titan_plugin_git.models.view.branch import UIGitBranch
    return UIGitBranch(name=name, display_name=name, is_current=current, is_remote=remote)


def test_read_branches_also_lists_every_branch_a_checkout_reaches(mod):
    git = fake_git(branches=[branch("feature", current=True)],
                   local=[ui_branch("feature", current=True), ui_branch("main")],
                   remote=[ui_branch("origin/main", remote=True), ui_branch("origin/feat/theirs", remote=True)])

    branches = mod.sections.branches.branches.read_branches(git, {"recent_branches": 8})

    assert [(b.name, b.is_remote) for b in branches.all] == [("main", False), ("feat/theirs", True)]


def searching(mod, query, blocked=None):
    git_branches = [ui_branch("main"), ui_branch("feat/login"), ui_branch("feat/login-v2"), ui_branch("feat/theirs", remote=True)]
    checked_out = []
    m, toasts = bus_for(fake_git(checked_out=checked_out))
    m.state.set("branches", mod.models.Branches(items=git_branches[:1], all=git_branches, current="feature", blocked=blocked))
    m.state.set("branch_filter", query)
    mod.sections.branches.branches.switch_to_typed(m, query)
    return m, checked_out, toasts


def test_enter_switches_to_the_branch_named_exactly(mod):
    m, checked_out, toasts = searching(mod, "feat/login")
    assert checked_out == ["feat/login"]
    assert toasts == [("Switched to feat/login", "information")]
    assert m.state.get("branch_filter") == ""


def test_enter_switches_to_a_remote_only_branch_by_part_of_its_name(mod):
    _, checked_out, _ = searching(mod, "theirs")
    assert checked_out == ["feat/theirs"]


def test_enter_on_an_ambiguous_or_unknown_name_switches_nowhere(mod):
    m, checked_out, _ = searching(mod, "login")
    assert checked_out == []
    assert m.state.get("branch_search_error") == "2 branches match; type more of the name"

    m, checked_out, _ = searching(mod, "nope")
    assert checked_out == [] and m.state.get("branch_search_error") == "No branch named nope"


def test_enter_with_uncommitted_work_says_why_and_stays(mod):
    m, checked_out, _ = searching(mod, "main", blocked="1 uncommitted file - commit or stash before switching")
    assert checked_out == []
    assert m.state.get("branch_search_error") == "1 uncommitted file - commit or stash before switching"
