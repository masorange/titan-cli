"""The git mod: its reading and drawing are plain functions over a fake client."""
from types import SimpleNamespace

import pytest

# What the loader hands `register`: every option in mod.toml, at its default.
OPTIONS = {
    "repo_refresh_seconds": 30,
    "refresh_key": "f5",
    "recent_commits": 10,
    "branches_refresh_seconds": 60,
    "recent_branches": 8,
    "branch_filter_threshold": 8,
    "commit_workflow": "commit-ai",
    "merge_workflow": "merge-branch",
    "worktrees_refresh_seconds": 120,
}


def test_draw_shows_branch_and_commits(mod, flatten):
    from titan_cli.core.mods import ModBus

    m = ModBus().api("git")
    m.state.set("repo", mod.models.Repo(branch="feat/x", has_upstream=True, ahead=1, added=4, commits=[
        SimpleNamespace(short_hash="abc", message_subject="feat: y (#9)", pr_number=9, formatted_date="today"),
    ]))

    lines = flatten(mod.draw.draw(m, 44))

    assert lines[0] == "⎇ feat/x ↑1 ↓0 +4"
    assert "▸ #9 feat: y" in lines


def test_a_branch_without_upstream_says_so(mod, flatten):
    from titan_cli.core.mods import ModBus

    m = ModBus().api("git")
    m.state.set("repo", mod.models.Repo(branch="feat/x"))
    assert flatten(mod.draw.draw(m, 44))[0] == "⎇ feat/x no upstream"


def test_refresh_key_is_bound_at_start_and_refreshes_the_repo(mod, tmp_path):
    from titan_cli.core.mods import AppStart, ModBus

    keys, runs = {}, []
    host = SimpleNamespace(
        open_pane=lambda *a: None, every=lambda *a: None, repaint=lambda mod: None,
        run=lambda mod, fn: runs.append(fn), client=lambda name: None,
        bind_key=lambda mod, key, description, fn: keys.setdefault(key, (description, fn)) and None,
    )
    bus = ModBus()
    bus.host = host
    options = dict(OPTIONS, refresh_key="f5")
    mod.register(bus.on_for("git"), options)

    bus.dispatch("app.start", AppStart(project_root=str(tmp_path)), lambda e: None)
    assert list(keys) == ["f5"] and keys["f5"][0] == "Refresh status"

    runs.clear()
    keys["f5"][1]()
    assert len(runs) == 1  # the refresh goes off the UI thread
    runs[0]()
    state = bus.api("git").state
    assert state.get("repo").error == "git plugin not available"


def test_a_finished_or_aborted_workflow_refreshes_off_its_thread(mod, tmp_path):
    from titan_cli.core.mods import AppStart, ModBus, WorkflowRun

    runs = []
    host = SimpleNamespace(
        open_pane=lambda *a: None, every=lambda *a: None, repaint=lambda mod: None,
        run=lambda mod, fn: runs.append(fn), client=lambda name: None, bind_key=lambda *a: None,
    )
    bus = ModBus()
    bus.host = host
    mod.register(bus.on_for("git"), dict(OPTIONS, refresh_key=""))
    bus.dispatch("app.start", AppStart(project_root=str(tmp_path)), lambda e: None)
    state = bus.api("git").state
    runs.clear()

    bus.dispatch("workflow.run", WorkflowRun("review-pr", "plugin", nested=True), lambda e: None)
    assert runs == [] and state.get("repo") is None  # a nested workflow is part of its parent

    bus.dispatch("workflow.run", WorkflowRun("review-pr", "plugin", nested=False), lambda e: None)
    assert state.get("repo") is None  # not on the workflow's thread
    runs[-1]()
    assert state.get("repo") is not None

    runs.clear()

    def aborted(e):
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        bus.dispatch("workflow.run", WorkflowRun("review-pr", "plugin", nested=False), aborted)
    assert len(runs) == 1  # an aborted run refreshes too


def branches_state(mod, blocked=None, names=("main", "feature/login"), current=None):
    return mod.models.Branches(
        items=[SimpleNamespace(name=n, is_current=n == current, formatted_date="2 d")
               for n in ((current,) + names if current else names)],
        current="feat/x",
        blocked=blocked,
        main_branch="main",
    )


def test_the_switcher_folds_and_lists_the_branches(mod, flatten):
    from titan_cli.core.mods import ModBus

    m = ModBus().api("git")
    m.state.set("repo", mod.models.Repo(branch="feat/x"))
    m.state.set("branches", branches_state(mod))

    assert "▸ Switch branch (2)" in flatten(mod.draw.draw(m, 44, OPTIONS))

    m.state.set("branches_open", True)
    lines = flatten(mod.draw.draw(m, 44, OPTIONS))

    assert "▾ Switch branch (2)" in lines
    assert "▸ main · 2 d" in lines and "▸ feature/login · 2 d" in lines


def test_the_filter_keeps_only_the_branches_that_match(mod, flatten):
    from titan_cli.core.mods import ModBus

    m = ModBus().api("git")
    m.state.set("repo", mod.models.Repo(branch="feat/x"))
    m.state.set("branches", branches_state(mod))
    m.state.set("branches_open", True)
    m.state.set("branch_filter", "login")

    lines = flatten(mod.draw.draw(m, 44, OPTIONS))

    assert "▸ feature/login · 2 d" in lines and "▸ main · 2 d" not in lines


def test_uncommitted_work_leaves_a_branch_with_no_actions(mod, flatten):
    """The reason is shown, a row opens but offers nothing, and a commit is offered."""
    from titan_cli.core.mods import ModBus

    m = ModBus().api("git")
    m.state.set("repo", mod.models.Repo(branch="feat/x"))
    m.state.set("branches", branches_state(mod, blocked="2 uncommitted files - commit or stash before switching"))
    m.state.set("branches_open", True)
    m.state.set("open_branch", "main")

    lines = flatten(mod.draw.draw(m, 44, OPTIONS))

    assert "⚠ 2 uncommitted files - commit or stash before switching" in lines
    assert "✦ Commit with AI" in lines
    assert "commit or stash to use this branch" in lines
    assert "⎇ Switch to it" not in lines and not any("Merge" in line for line in lines)



def test_a_branch_unfolds_into_its_actions(mod, flatten):
    """Switching, and the picker of branches to merge in."""
    from titan_cli.core.mods import ModBus

    m = ModBus().api("git")
    m.state.set("repo", mod.models.Repo(branch="feat/x"))
    m.state.set("branches", branches_state(mod))
    m.state.set("branches_open", True)

    closed = flatten(mod.draw.draw(m, 44, OPTIONS))
    assert "⎇ Switch to it" not in closed  # a row shows nothing until it is opened

    m.state.set("open_branch", "feature/login")
    lines = flatten(mod.draw.draw(m, 44, OPTIONS))

    assert "▾ feature/login · 2 d" in lines
    assert "⎇ Switch to it" in lines
    assert "▸ Merge a branch into it…" in lines
    assert "main" not in lines[lines.index("▸ Merge a branch into it…") + 1:]  # the picker is closed

    m.state.set("merge_source_for", "feature/login")
    picking = flatten(mod.draw.draw(m, 44, OPTIONS))

    assert "▾ Merge a branch into it…" in picking
    assert "main" in picking[picking.index("▾ Merge a branch into it…") + 1:]


def test_the_merge_action_runs_the_workflow_with_both_branches(mod):
    from titan_cli.core.mods import ModBus

    runs = []
    bus = ModBus()
    bus.host = SimpleNamespace(repaint=lambda mod: None,
                               run_workflow=lambda mod, name, params: runs.append((name, dict(params))))
    m = bus.api("git")

    mod.sections.branches.branches.merge_into(m, "feature/login", "main", OPTIONS)

    assert runs == [("merge-branch", {"target_branch": "feature/login", "source_branch": "main"})]


def test_the_branch_you_are_on_sits_above_the_switcher_with_merges_only(mod, flatten):
    """You cannot switch to where you already are, but it is the usual merge target."""
    from titan_cli.core.mods import ModBus

    m = ModBus().api("git")
    m.state.set("repo", mod.models.Repo(branch="feat/x"))
    m.state.set("branches", branches_state(mod, current="feat/x"))

    lines = flatten(mod.draw.draw(m, 44, OPTIONS))

    assert lines.index("▸ feat/x · 2 d · here") < lines.index("▸ Switch branch (2)")

    m.state.set("open_branch", "feat/x")
    opened = flatten(mod.draw.draw(m, 44, OPTIONS))

    assert "▸ Merge a branch into it…" in opened
    assert "⇩ Pull origin/feat/x" in opened and "⇧ Push origin/feat/x" in opened
    assert "⎇ Switch to it" not in opened


def test_only_the_branch_you_are_on_offers_the_pull_and_push(mod, flatten):
    """Both act on the checked-out tree, so no other row may offer them."""
    from titan_cli.core.mods import ModBus

    m = ModBus().api("git")
    m.state.set("repo", mod.models.Repo(branch="feat/x"))
    m.state.set("branches", branches_state(mod, current="feat/x"))
    m.state.set("branches_open", True)
    m.state.set("open_branch", "feature/login")

    lines = flatten(mod.draw.draw(m, 44, OPTIONS))

    assert "⎇ Switch to it" in lines
    assert not any(line.startswith(("⇩ Pull", "⇧ Push")) for line in lines)


def test_uncommitted_work_still_lets_you_pull_and_push_the_branch_you_are_on(mod, flatten):
    """A switch is refused, but a push only sends commits and git judges the pull itself."""
    from titan_cli.core.mods import ModBus

    m = ModBus().api("git")
    m.state.set("repo", mod.models.Repo(branch="feat/x"))
    m.state.set("branches", branches_state(mod, blocked="2 uncommitted files - commit or stash before switching",
                                           current="feat/x"))
    m.state.set("open_branch", "feat/x")

    lines = flatten(mod.draw.draw(m, 44, OPTIONS))

    assert "commit or stash to use this branch" in lines
    assert "⇩ Pull origin/feat/x" in lines and "⇧ Push origin/feat/x" in lines


def test_each_card_can_be_turned_off_on_its_own(mod, flatten):
    """The pane is two cards, so the Mods screen can hide either one."""
    from titan_cli.core.mods import ModBus

    m = ModBus().api("git")
    m.state.set("repo", mod.models.Repo(branch="feat/x"))
    m.state.set("branches", branches_state(mod))

    without_branches = flatten(mod.draw.draw(m, 44, dict(OPTIONS, sections={"repo": True, "branches": False})))
    assert "⎇ feat/x no upstream" in without_branches
    assert not any("Switch branch" in line for line in without_branches)

    without_repo = flatten(mod.draw.draw(m, 44, dict(OPTIONS, sections={"repo": False, "branches": True})))
    assert "▸ Switch branch (2)" in without_repo
    assert not any("⎇ feat/x" in line for line in without_repo)


def worktrees_state(mod, paths=("/repo", "/repo-review"), current=None):
    return mod.models.Worktrees(
        items=[SimpleNamespace(path=p, path_short=p.rsplit("/", 1)[-1], branch_display="main",
                               commit_short="abc1234", is_bare=False, is_detached=False, status_icon="📂")
               for p in paths],
        main_path=paths[0],
        current_path=current or paths[0],
    )


def test_the_worktrees_card_folds_into_its_rows(mod, flatten):
    from titan_cli.core.mods import ModBus

    m = ModBus().api("git")
    m.state.set("repo", mod.models.Repo(branch="feat/x"))
    m.state.set("worktrees", worktrees_state(mod))

    assert "▸ Worktrees (2)" in flatten(mod.draw.draw(m, 44, OPTIONS))

    m.state.set("worktrees_open", True)
    lines = flatten(mod.draw.draw(m, 44, OPTIONS))

    assert "▸ 📂 repo · main" in lines and "▸ 📂 repo-review · main" in lines
    assert "⌦ Prune stale records" in lines

    # The one Titan runs in says so, unless it is the main one (already untouchable).
    m.state.set("worktrees", worktrees_state(mod, current="/repo-review"))
    assert "▸ 📂 repo-review · main · here" in flatten(mod.draw.draw(m, 44, OPTIONS))


def test_a_worktree_asks_before_it_is_removed(mod, flatten):
    """One press arms the removal, a second one does it; the main worktree neither."""
    from titan_cli.core.mods import ModBus

    m = ModBus().api("git")
    m.state.set("repo", mod.models.Repo(branch="feat/x"))
    m.state.set("worktrees", worktrees_state(mod))
    m.state.set("worktrees_open", True)
    m.state.set("open_worktree", "/repo-review")

    lines = flatten(mod.draw.draw(m, 44, OPTIONS))
    assert "/repo-review" in lines and "✗ Remove worktree" in lines
    assert "✓ Confirm removal" not in lines

    m.state.set("worktree_confirm", "/repo-review")
    armed = flatten(mod.draw.draw(m, 44, OPTIONS))

    assert "✓ Confirm removal" in armed
    assert "The directory is deleted. This cannot be undone." in armed
    assert "⚠ Force removal (discards its changes)" not in armed  # only after git refuses

    m.state.set("worktree_force", "/repo-review")
    assert "⚠ Force removal (discards its changes)" in flatten(mod.draw.draw(m, 44, OPTIONS))


def test_the_main_worktree_offers_no_removal(mod, flatten):
    from titan_cli.core.mods import ModBus

    m = ModBus().api("git")
    m.state.set("repo", mod.models.Repo(branch="feat/x"))
    m.state.set("worktrees", worktrees_state(mod))
    m.state.set("worktrees_open", True)
    m.state.set("open_worktree", "/repo")

    lines = flatten(mod.draw.draw(m, 44, OPTIONS))

    assert "Cannot be removed: the main worktree" in lines
    assert "✗ Remove worktree" not in lines


def test_the_picker_offers_the_base_branch_first(mod, flatten):
    """The usual merge is the base branch, so it is the first press, not a second button."""
    from titan_cli.core.mods import ModBus

    m = ModBus().api("git")
    m.state.set("repo", mod.models.Repo(branch="feat/x"))
    m.state.set("branches", mod.models.Branches(
        items=[SimpleNamespace(name=n, is_current=n == "feat/x", formatted_date="2 d")
               for n in ("feat/x", "feature/login", "main")],
        current="feat/x",
        main_branch="main",
    ))
    m.state.set("open_branch", "feat/x")
    m.state.set("merge_source_for", "feat/x")

    lines = flatten(mod.draw.draw(m, 44, OPTIONS))
    offered = lines[lines.index("▾ Merge a branch into it…") + 1:]

    assert offered[:2] == ["main", "feature/login"]


def test_a_running_pull_replaces_the_buttons_with_what_it_is_doing(mod, flatten):
    """From the press to the toast the card says it is working, and there is nothing to press twice."""
    from titan_cli.core.mods import ModBus

    m = ModBus().api("git")
    m.state.set("repo", mod.models.Repo(branch="feat/x"))
    m.state.set("branches", branches_state(mod, current="feat/x"))
    m.state.set("open_branch", "feat/x")
    m.state.set("remote_action", "pull")

    lines = flatten(mod.draw.draw(m, 44, OPTIONS))

    assert "… pulling origin/feat/x" in lines
    assert not any(line.startswith(("⇩ Pull", "⇧ Push")) for line in lines)

    m.state.set("remote_action", "push")
    assert "… pushing origin/feat/x" in flatten(mod.draw.draw(m, 44, OPTIONS))

    m.state.set("remote_action", None)
    assert "⇩ Pull origin/feat/x" in flatten(mod.draw.draw(m, 44, OPTIONS))
