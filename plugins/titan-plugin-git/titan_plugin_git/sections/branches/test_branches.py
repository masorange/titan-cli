"""Reading the branches to switch to, and switching through the client."""
from types import SimpleNamespace

from titan_cli.core.result import ClientError, ClientSuccess
from titan_plugin_git.readers import Branches
from titan_plugin_git.sections.branches import branches as actions


def branch(name, current=False):
    return SimpleNamespace(name=name, is_current=current, formatted_date="2 d", upstream_info="")


def fake_git(status=None, branches=(), checkout=None, pull=None, pulled=None, push=None, pushed=None,
             local=(), remote=(), checked_out=None, stashes=(), stash=None, popped=None, stashed=None):
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
        list_stashes=lambda: ClientSuccess(data=list(stashes)),
        stash_push=lambda include_untracked=False: (stashed is not None and stashed.append(include_untracked),
                                                    stash or ClientSuccess(data=True))[1],
        stash_pop=lambda ref=None: (popped is not None and popped.append(True), stash or ClientSuccess(data=True))[1],
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


def test_read_branches_reports_the_branches_and_a_clean_tree():
    git = fake_git(branches=[branch("feature", current=True), branch("main")])

    branches = actions.read_branches(git, {"recent_branches": 8})

    assert [b.name for b in branches.items] == ["feature", "main"]
    assert (branches.current, branches.blocked, branches.error) == ("feature", None, None)


def test_read_branches_blocks_on_uncommitted_work_but_still_lists():
    """The list stays, so the user sees where they could go once they commit."""
    status = SimpleNamespace(branch="feature", modified_files=["a.py"], staged_files=[], untracked_files=["new.md"])
    git = fake_git(status=status, branches=[branch("main")])

    branches = actions.read_branches(git, {"recent_branches": 8})

    assert branches.blocked == "1 uncommitted file - commit or stash before switching"
    assert [b.name for b in branches.items] == ["main"]


def test_read_branches_without_git_says_so():
    assert actions.read_branches(None, {}).error == "git plugin not available"


def test_switch_to_checks_out_and_refreshes():
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

    actions.switch_to(m, "main")

    assert toasts == [("Switched to main", "information")]
    assert refreshed == [True]


def test_switch_to_reports_a_failed_checkout():
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

    actions.switch_to(m, "main")

    assert toasts == [("Could not switch to main: would be overwritten", "error")]
    assert refreshed == [True]  # the pane is redrawn from git either way


def test_a_press_shows_the_progress_until_the_answer_arrives():
    """The claim is what the card draws its progress line from, and it is released after."""
    pulled, seen = [], []
    git = fake_git(pulled=pulled)
    m, toasts = bus_for(git)
    m.state.set("refresh", lambda: seen.append(actions.running(m)))

    # m.run is synchronous here, so the claim is observed through the refresh.
    actions.start_remote(m, "pull", "feature")

    assert pulled == [("origin", "feature")]
    assert toasts == [("Pulled origin/feature", "information")]
    assert seen == [None]  # cleared before the card is read again
    assert actions.running(m) is None


def test_a_second_press_while_one_runs_does_nothing():
    """Two quick presses both saw the branch free; only the first one sends."""
    pulled = []
    m, _ = bus_for(fake_git(pulled=pulled))
    m.state.set("remote_action", "pull")  # one already in flight

    actions.start_remote(m, "pull", "feature")

    assert pulled == []
    assert actions.running(m) == "pull"


def test_pull_pulls_the_branch_from_origin_and_refreshes():
    pulled, refreshed = [], []
    m, toasts = bus_for(fake_git(pulled=pulled))
    m.state.set("refresh", lambda: refreshed.append(True))

    actions.run_remote(m, "pull", "feature")

    assert pulled == [("origin", "feature")]
    assert toasts == [("Pulled origin/feature", "information")]
    assert refreshed == [True]


def test_pull_reports_a_refused_pull():
    """Git refuses a pull over uncommitted work; the card says so instead of hiding it."""
    refreshed = []
    m, toasts = bus_for(fake_git(pull=ClientError(error_message="local changes would be overwritten")))
    m.state.set("refresh", lambda: refreshed.append(True))

    actions.run_remote(m, "pull", "feature")

    assert toasts == [("Could not pull origin/feature: local changes would be overwritten", "error")]
    assert refreshed == [True]


def test_push_pushes_the_branch_to_origin():
    pushed = []
    m, toasts = bus_for(fake_git(pushed=pushed))

    actions.run_remote(m, "push", "feature")

    assert pushed == [("origin", "feature")]
    assert toasts == [("Pushed feature to origin", "information")]


def test_push_explains_a_rejected_push_instead_of_forcing_it():
    """A force push would drop the remote's commits, so the pane only says so."""
    rejected = "! [rejected] feature -> feature (non-fast-forward)"
    m, toasts = bus_for(fake_git(push=ClientError(error_message=rejected)))

    actions.run_remote(m, "push", "feature")

    (text, severity), = toasts
    assert severity == "error"
    assert rejected in text and "force push by hand" in text


def test_push_reports_any_other_failure_as_git_worded_it():
    m, toasts = bus_for(fake_git(push=ClientError(error_message="fatal: no remote named origin")))

    actions.run_remote(m, "push", "feature")

    assert toasts == [("Could not push feature: fatal: no remote named origin", "error")]


def test_a_failure_still_releases_the_claim():
    """A card stuck on its progress line would need a restart to press again."""
    m, _ = bus_for(fake_git(push=ClientError(error_message="boom")))

    actions.run_remote(m, "push", "feature")

    assert actions.running(m) is None


def ui_branch(name, current=False, remote=False):
    from titan_plugin_git.models.view.branch import UIGitBranch
    return UIGitBranch(name=name, display_name=name, is_current=current, is_remote=remote)


def test_read_branches_also_lists_every_branch_a_checkout_reaches():
    git = fake_git(branches=[branch("feature", current=True)],
                   local=[ui_branch("feature", current=True), ui_branch("main")],
                   remote=[ui_branch("origin/main", remote=True), ui_branch("origin/feat/theirs", remote=True)])

    branches = actions.read_branches(git, {"recent_branches": 8})

    assert [(b.name, b.is_remote) for b in branches.all] == [("main", False), ("feat/theirs", True)]


def searching(query, blocked=None):
    git_branches = [ui_branch("main"), ui_branch("feat/login"), ui_branch("feat/login-v2"), ui_branch("feat/theirs", remote=True)]
    checked_out = []
    m, toasts = bus_for(fake_git(checked_out=checked_out))
    m.state.set("branches", Branches(items=git_branches[:1], all=git_branches, current="feature", blocked=blocked))
    m.state.set("branch_filter", query)
    actions.switch_to_typed(m, query)
    return m, checked_out, toasts


def test_enter_switches_to_the_branch_named_exactly():
    m, checked_out, toasts = searching("feat/login")
    assert checked_out == ["feat/login"]
    assert toasts == [("Switched to feat/login", "information")]
    assert m.state.get("branch_filter") == ""


def test_enter_switches_to_a_remote_only_branch_by_part_of_its_name():
    _, checked_out, _ = searching("theirs")
    assert checked_out == ["feat/theirs"]


def test_enter_on_an_ambiguous_or_unknown_name_switches_nowhere():
    m, checked_out, _ = searching("login")
    assert checked_out == []
    assert m.state.get("branch_search_error") == "2 branches match; type more of the name"

    m, checked_out, _ = searching("nope")
    assert checked_out == [] and m.state.get("branch_search_error") == "No branch named nope"


def test_enter_with_uncommitted_work_says_why_and_stays():
    m, checked_out, _ = searching("main", blocked="1 uncommitted file - commit or stash before switching")
    assert checked_out == []
    assert m.state.get("branch_search_error") == "1 uncommitted file - commit or stash before switching"


def test_a_switch_from_a_row_clears_the_search_too():
    m, _ = bus_for(fake_git())
    m.state.set("branch_filter", "log")
    m.state.set("open_branch", "feat/login")

    actions.switch_to(m, "feat/login")

    assert m.state.get("branch_filter") == ""
    assert m.state.get("open_branch") is None


def test_a_failed_switch_keeps_what_was_typed():
    m, _ = bus_for(fake_git(checkout=ClientError(error_message="conflict")))
    m.state.set("branch_filter", "log")

    actions.switch_to(m, "feat/login")

    assert m.state.get("branch_filter") == "log"


def test_read_branches_lists_the_stashes():
    stash = SimpleNamespace(ref="stash@{0}", branch="feature", message="m", formatted_date="1 h")
    branches = actions.read_branches(fake_git(branches=[branch("feature", current=True)], stashes=[stash]), {"recent_branches": 8})

    assert branches.stashes == [stash]


def test_stashing_takes_new_files_too_tells_the_user_and_releases_the_card():
    stashed = []
    m, toasts = bus_for(fake_git(stashed=stashed))
    m.state.set("refresh", lambda: toasts.append(("refreshed", actions.running(m))))

    actions.start_stash(m, "stash")

    assert stashed == [True]
    assert toasts == [("Stashed the uncommitted work", "information"), ("refreshed", None)]
    assert actions.running(m) is None


def test_popping_a_chosen_stash_hands_its_ref_to_git():
    asked = []
    git = fake_git()
    git.stash_pop = lambda ref=None: (asked.append(ref), ClientSuccess(data=True))[1]
    m, toasts = bus_for(git)

    actions.start_stash(m, "pop", "stash@{1}")

    assert asked == ["stash@{1}"] and toasts == [("Popped stash@{1}", "information")]


def test_popping_reports_git_when_it_refuses_and_still_releases_the_card():
    popped = []
    m, toasts = bus_for(fake_git(popped=popped, stash=ClientError(error_message="conflict")))

    actions.start_stash(m, "pop")

    assert popped == [True]
    assert toasts == [("Could not pop the stash: conflict", "error")]
    assert actions.running(m) is None
