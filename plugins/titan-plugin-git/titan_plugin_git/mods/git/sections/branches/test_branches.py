"""Reading the branches to switch to, and switching through the client."""
from types import SimpleNamespace

from titan_cli.core.result import ClientError, ClientSuccess


def branch(name, current=False):
    return SimpleNamespace(name=name, is_current=current, formatted_date="2 d", upstream_info="")


def fake_git(status=None, branches=(), checkout=None):
    return SimpleNamespace(
        get_status=lambda: ClientSuccess(data=status or SimpleNamespace(
            branch="feature", modified_files=[], staged_files=[], untracked_files=[])),
        list_recent_branches=lambda limit: ClientSuccess(data=list(branches)),
        checkout=lambda name: checkout or ClientSuccess(data=None),
    )


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
