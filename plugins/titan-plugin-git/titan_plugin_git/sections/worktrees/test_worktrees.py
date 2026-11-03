"""Reading the worktrees, and removing one through the client."""
from types import SimpleNamespace

from titan_cli.core.result import ClientError, ClientSuccess
from titan_plugin_git.sections.worktrees import worktrees as actions


def worktree(path, branch="main"):
    return SimpleNamespace(
        path=path, path_short=path.rsplit("/", 1)[-1], branch=branch,
        branch_display=branch, commit_short="abc1234", is_bare=False,
        is_detached=False, status_icon="📂",
    )


def fake_git(worktrees=(), removal=None, prune=None):
    return SimpleNamespace(
        list_worktrees=lambda: ClientSuccess(data=list(worktrees)),
        remove_worktree=lambda path, force=False: removal or ClientSuccess(data=None),
        prune_worktrees=lambda: prune or ClientSuccess(data=None, message="Pruned stale worktree metadata"),
    )


def bus_with(git, toasts):
    from titan_cli.core.mods import ModBus

    bus = ModBus()
    bus.host = SimpleNamespace(
        repaint=lambda mod: None,
        client=lambda name: git,
        toast=lambda mod, text, severity: toasts.append((text, severity)),
    )
    return bus.api("git")


def test_read_worktrees_marks_the_main_one_and_where_we_are(tmp_path):
    git = fake_git([worktree("/repo"), worktree(str(tmp_path), "feature")])

    worktrees = actions.read_worktrees(git, tmp_path, {})

    assert [w.path for w in worktrees.items] == ["/repo", str(tmp_path)]
    assert worktrees.main_path == "/repo"
    assert worktrees.current_path == str(tmp_path)


def test_blocked_removal_names_the_untouchable_ones(tmp_path):
    here, other = worktree(str(tmp_path)), worktree("/repo-review")
    git = fake_git([worktree("/repo"), here, other])

    worktrees = actions.read_worktrees(git, tmp_path, {})
    blocked = actions.blocked_removal

    assert blocked(worktrees, worktrees.items[0]) == "the main worktree"
    assert blocked(worktrees, here) == "the worktree you are in"
    assert blocked(worktrees, other) == ""


def test_read_worktrees_without_git_says_so(tmp_path):
    assert actions.read_worktrees(None, tmp_path, {}).error == "git plugin not available"


def test_removing_a_worktree_clears_the_confirmation_and_refreshes():
    toasts, refreshed = [], []
    m = bus_with(fake_git(), toasts)
    m.state.set("refresh", lambda: refreshed.append(True))
    m.state.set("worktree_confirm", "/repo-review")

    actions.remove_worktree(m, "/repo-review")

    assert toasts == [("Worktree removed: /repo-review", "information")]
    assert m.state.get("worktree_confirm") is None and refreshed == [True]


def test_a_refused_removal_offers_the_forced_one_on_that_row():
    """Git refuses a worktree holding work; the force button appears only then."""
    toasts, refreshed = [], []
    m = bus_with(fake_git(removal=ClientError(error_message="contains modified files")), toasts)
    m.state.set("refresh", lambda: refreshed.append(True))

    actions.remove_worktree(m, "/repo-review")

    assert toasts == [("Could not remove /repo-review: contains modified files", "error")]
    assert m.state.get("worktree_force") == "/repo-review"
    assert m.state.get("worktree_confirm") is None and refreshed == [True]


def test_pruning_reports_what_git_said():
    toasts, refreshed = [], []
    m = bus_with(fake_git(), toasts)
    m.state.set("refresh", lambda: refreshed.append(True))

    actions.prune_worktrees(m)

    assert toasts == [("Pruned stale worktree metadata", "information")]
    assert refreshed == [True]
