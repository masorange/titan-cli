"""Reading the branches to switch to, and switching through the client."""
from types import SimpleNamespace

from titan_cli.core.result import ClientError, ClientSuccess


def branch(name, current=False):
    return SimpleNamespace(name=name, is_current=current, formatted_date="2 d", upstream_info="")


def fake_git(status=None, branches=(), checkout=None, pull=None, pulled=None, push=None, pushed=None):
    return SimpleNamespace(
        get_status=lambda: ClientSuccess(data=status or SimpleNamespace(
            branch="feature", modified_files=[], staged_files=[], untracked_files=[])),
        list_recent_branches=lambda limit: ClientSuccess(data=list(branches)),
        checkout=lambda name: checkout or ClientSuccess(data=None),
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


def test_pull_current_pulls_the_branch_from_origin_and_refreshes(mod):
    pulled, refreshed = [], []
    m, toasts = bus_for(fake_git(pulled=pulled))
    m.state.set("refresh", lambda: refreshed.append(True))

    mod.sections.branches.branches.pull_current(m, "feature")

    assert pulled == [("origin", "feature")]
    assert toasts == [("Pulled origin/feature", "information")]
    assert refreshed == [True]


def test_pull_current_reports_a_refused_pull(mod):
    """Git refuses a pull over uncommitted work; the card says so instead of hiding it."""
    refreshed = []
    m, toasts = bus_for(fake_git(pull=ClientError(error_message="local changes would be overwritten")))
    m.state.set("refresh", lambda: refreshed.append(True))

    mod.sections.branches.branches.pull_current(m, "feature")

    assert toasts == [("Could not pull origin/feature: local changes would be overwritten", "error")]
    assert refreshed == [True]


def test_push_current_pushes_the_branch_to_origin_and_refreshes(mod):
    pushed, refreshed = [], []
    m, toasts = bus_for(fake_git(pushed=pushed))
    m.state.set("refresh", lambda: refreshed.append(True))

    mod.sections.branches.branches.push_current(m, "feature")

    assert pushed == [("origin", "feature")]
    assert toasts == [("Pushed feature to origin", "information")]
    assert refreshed == [True]


def test_push_current_explains_a_rejected_push_instead_of_forcing_it(mod):
    """A force push would drop the remote's commits, so the pane only says so."""
    rejected = "! [rejected] feature -> feature (non-fast-forward)"
    m, toasts = bus_for(fake_git(push=ClientError(error_message=rejected)))

    mod.sections.branches.branches.push_current(m, "feature")

    (text, severity), = toasts
    assert severity == "error"
    assert rejected in text and "force push by hand" in text


def test_push_current_reports_any_other_failure_as_git_worded_it(mod):
    m, toasts = bus_for(fake_git(push=ClientError(error_message="fatal: no remote named origin")))

    mod.sections.branches.branches.push_current(m, "feature")

    assert toasts == [("Could not push feature: fatal: no remote named origin", "error")]
