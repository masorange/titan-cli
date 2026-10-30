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
    "commit_workflow": "commit-ai",
    "create_pr_workflow": "create-pr-ai",
    "suggestion_diff_chars": 4000,
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


def test_the_search_is_always_there_and_reaches_beyond_the_recent_branches(mod, flatten):
    from titan_cli.core.mods import ModBus, Input

    m = ModBus().api("git")
    m.state.set("repo", mod.models.Repo(branch="feat/x"))
    state = branches_state(mod)
    every = [*state.items, SimpleNamespace(name="feat/old-one", is_current=False, is_remote=True, formatted_date="")]
    m.state.set("branches", mod.models.Branches(items=state.items, all=every, current="feat/x", main_branch="main"))
    m.state.set("branches_open", True)

    tree = mod.draw.draw(m, 44, OPTIONS)
    assert any(isinstance(e, Input) for e in walk(tree))  # two branches only, and the field is there

    assert "✕" not in flatten(tree)  # nothing typed, nothing to clear

    m.state.set("branch_filter", "old")
    m.state.set("branch_search_error", "No branch named old")
    tree = mod.draw.draw(m, 44, OPTIONS)
    assert "▸ feat/old-one · remote" in flatten(tree)

    clear = next(e for e in walk(tree) if getattr(e, "label", None) == "✕")
    clear.on_press()
    assert (m.state.get("branch_filter"), m.state.get("branch_search_error")) == ("", None)


def walk(element):
    yield element
    for child in getattr(element, "children", ()):
        yield from walk(child)


def test_uncommitted_work_leaves_a_branch_with_no_actions(mod, flatten):
    """The reason is shown, a row opens but offers nothing, and the current branch opens with a commit offered."""
    from titan_cli.core.mods import ModBus

    m = ModBus().api("git")
    m.state.set("repo", mod.models.Repo(branch="feat/x"))
    m.state.set("branches", branches_state(mod, blocked="2 uncommitted files - commit or stash before switching"))
    m.state.set("branches_open", True)
    m.state.set("open_branch", "main")

    lines = [line.strip() for line in flatten(mod.draw.draw(m, 44, OPTIONS))]

    # With no row for the branch you are on, the commit stands alone above the rows.
    assert "⚠ 2 uncommitted files - commit or stash before switching" in lines
    assert "✦ Commit with AI" in lines
    assert "commit or stash to use this branch" in lines
    assert "⎇ Switch to it" not in lines and not any("Merge" in line for line in lines)

    # With the current branch listed it starts open, holds the commit, and closing it sticks.
    m.state.set("open_branch", None)
    m.state.set("branches", branches_state(mod, current="feat/x", blocked="2 uncommitted files - commit or stash before switching"))
    assert "✦ Commit with AI" in [line.strip() for line in flatten(mod.draw.draw(m, 44, OPTIONS))]
    m.state.set("open_branch", "")
    assert "✦ Commit with AI" not in [line.strip() for line in flatten(mod.draw.draw(m, 44, OPTIONS))]



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

    m.state.set("branch_menu:feature/login", "Merge a branch into it…")
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


class NewBranchHost:
    """Runs m.run inline, answers m.ai from a script and hands out the fake clients."""

    def __init__(self, git, github=None, answer=None):
        self.git, self.github, self.answer = git, github, answer
        self.prompts, self.toasts = [], []

    def toast(self, mod, text, severity): self.toasts.append((text, severity))
    def repaint(self, mod): pass
    def resolve_workflow(self, mod, name): return None
    def client(self, name): return {"git": self.git, "github": self.github}.get(name)
    def run(self, mod, fn): fn()

    def ai(self, mod, prompt, system, max_tokens, model, timeout):
        self.prompts.append((prompt, system))
        return self.answer


class FakeGit:
    """The git client as the new-branch fold uses it."""

    def __init__(self, created=None, error=None):
        self.created, self.error = created if created is not None else [], error

    def get_branches(self, remote=False):
        from titan_cli.core.result import ClientSuccess
        names = ["origin/feat/remote-one"] if remote else ["feat/x", "feat/y", "fix/crash", "main"]
        return ClientSuccess(data=[SimpleNamespace(name=n, is_remote=remote) for n in names])

    def get_uncommitted_diff_stat(self):
        from titan_cli.core.result import ClientSuccess
        return ClientSuccess(data=" api.py | 2 +-")

    def get_untracked_files(self):
        from titan_cli.core.result import ClientSuccess
        return ClientSuccess(data=["notes.md"])

    def get_uncommitted_diff(self):
        from titan_cli.core.result import ClientSuccess
        return ClientSuccess(data="@@ -1 +1 @@\n-old\n+new")

    def create_and_switch_branch(self, name, start_point):
        from titan_cli.core.result import ClientError, ClientSuccess
        if self.error:
            return ClientError(error_message=self.error)
        self.created.append((name, start_point))
        return ClientSuccess(data=None)


def open_new_branch_fold(mod, host):
    """A pane with the fold open under the branch you are on."""
    from titan_cli.core.mods import ModBus

    bus = ModBus()
    bus.host = host
    m = bus.api("git")
    m.state.set("repo", mod.models.Repo(branch="feat/x"))
    m.state.set("branches", branches_state(mod, current="feat/x"))
    m.state.set("open_branch", "feat/x")
    m.state.set("branch_menu:feat/x", "New branch from it…")
    return m


def test_the_new_branch_fold_is_offered_on_the_branch_you_are_on(mod, flatten):
    """It starts at HEAD and carries the uncommitted work, so no other row may offer it."""
    from titan_cli.core.mods import ModBus

    bus = ModBus()
    bus.host = SimpleNamespace(repaint=lambda mod: None, resolve_workflow=lambda mod, name: None)
    m = bus.api("git")
    m.state.set("repo", mod.models.Repo(branch="feat/x"))
    m.state.set("branches", branches_state(mod, current="feat/x"))
    m.state.set("branches_open", True)

    m.state.set("open_branch", "feat/x")
    assert "▸ New branch from it…" in flatten(mod.draw.draw(m, 44, OPTIONS))

    m.state.set("open_branch", "feature/login")
    assert not any("New branch" in line for line in flatten(mod.draw.draw(m, 44, OPTIONS)))


def test_the_fold_offers_the_ai_and_only_creates_once_there_is_a_name(mod, flatten):
    host = NewBranchHost(FakeGit())
    m = open_new_branch_fold(mod, host)

    lines = flatten(mod.draw.draw(m, 44, OPTIONS))
    assert "▾ New branch from it…" in lines and "✦ Suggest with AI" in lines
    assert not any("Create" in line and "switch" in line for line in lines)

    m.state.set(mod.sections.branches.new_branch.NAME, "feat/z")
    assert "✓ Create feat/z and switch" in flatten(mod.draw.draw(m, 44, OPTIONS))


def test_uncommitted_work_still_offers_the_new_branch_fold(mod, flatten):
    """Working on the wrong branch is exactly when it is needed, and git carries the changes over."""
    from titan_cli.core.mods import ModBus

    bus = ModBus()
    bus.host = SimpleNamespace(repaint=lambda mod: None, resolve_workflow=lambda mod, name: None)
    m = bus.api("git")
    m.state.set("repo", mod.models.Repo(branch="feat/x"))
    m.state.set("branches", branches_state(mod, blocked="2 uncommitted files - commit or stash before switching",
                                           current="feat/x"))
    m.state.set("open_branch", "feat/x")

    assert "▸ New branch from it…" in flatten(mod.draw.draw(m, 44, OPTIONS))


def test_the_suggestion_reads_the_diff_under_the_repo_s_prefixes_and_labels(mod, flatten):
    from titan_cli.core.mods import AIAnswer
    from titan_cli.core.result import ClientSuccess

    github = SimpleNamespace(list_labels=lambda: ClientSuccess(data=["bug", "enhancement"]))
    host = NewBranchHost(FakeGit(), github=github, answer=AIAnswer(text="`feat/Switch Branch`"))
    m = open_new_branch_fold(mod, host)

    mod.sections.branches.new_branch.suggest(m, OPTIONS)

    prompt, system = host.prompts[0]
    assert "feat, fix" in prompt  # read from the branches, remote ones without their remote
    assert "bug, enhancement" in prompt  # how this repo labels its PRs
    assert "api.py | 2 +-" in prompt and "notes.md (new file)" in prompt and "+new" in prompt
    assert "branch name only" in system

    # The answer only fills the field: nothing exists until the user presses for it.
    assert m.state.get(mod.sections.branches.new_branch.NAME) == "feat/switch-branch"
    assert m.state.get(mod.sections.branches.new_branch.STATUS) is None
    assert host.git.created == []
    assert "✓ Create feat/switch-branch and switch" in flatten(mod.draw.draw(m, 44, OPTIONS))


def test_the_suggestion_says_why_it_has_no_name_without_touching_the_repo(mod):
    from titan_cli.core.mods import AIAnswer

    host = NewBranchHost(FakeGit(), answer=AIAnswer(error="no connection"))
    m = open_new_branch_fold(mod, host)

    mod.sections.branches.new_branch.suggest(m, OPTIONS)

    assert m.state.get(mod.sections.branches.new_branch.ERROR) == "AI: no connection"
    assert host.git.created == []


def test_a_name_that_cannot_be_a_branch_is_refused_before_git_is_asked(mod, flatten):
    host = NewBranchHost(FakeGit())
    m = open_new_branch_fold(mod, host)
    m.state.set(mod.sections.branches.new_branch.NAME, "main")  # the switcher already lists it

    mod.sections.branches.new_branch.create(m, "feat/x", OPTIONS)

    assert host.git.created == []
    assert "that branch already exists" in flatten(mod.draw.draw(m, 44, OPTIONS))


def test_creating_branches_off_the_branch_you_are_on_and_closes_the_fold(mod):
    refreshed = []
    host = NewBranchHost(FakeGit())
    m = open_new_branch_fold(mod, host)
    m.state.set("refresh", lambda: refreshed.append(True))
    mod.sections.branches.new_branch.set_name(m, "Feat/New Thing")

    mod.sections.branches.new_branch.create(m, "feat/x", OPTIONS)

    # The name is put in the shape git accepts before it is used, field included.
    assert host.git.created == [("feat/new-thing", "feat/x")]
    assert m.state.get(mod.sections.branches.new_branch.NAME) == ""
    assert m.state.get("branch_menu:feat/x") is None
    assert host.toasts == [("Created feat/new-thing from feat/x", "information")]
    assert refreshed == [True]


def test_a_refused_checkout_is_reported_under_the_field(mod, flatten):
    host = NewBranchHost(FakeGit(error="fatal: a branch named 'feat/z' already exists"))
    m = open_new_branch_fold(mod, host)
    m.state.set(mod.sections.branches.new_branch.NAME, "feat/z")

    mod.sections.branches.new_branch.create(m, "feat/x", OPTIONS)

    lines = flatten(mod.draw.draw(m, 44, OPTIONS))
    assert any("already exists" in line for line in lines)
    assert m.state.get(mod.sections.branches.new_branch.STATUS) is None  # never stuck on the progress line


def test_the_create_pr_button_runs_the_workflow_titan_would_pick(mod, flatten):
    """The repo may extend the plugin's workflow: the button runs what the menu entry runs."""
    from titan_cli.core.mods import ModBus

    runs = []
    bus = ModBus()
    bus.host = SimpleNamespace(
        repaint=lambda mod: None,
        resolve_workflow=lambda mod, name: "create-pr" if name == "create-pr-ai" else None,
        run_workflow=lambda mod, name, params: runs.append((name, dict(params))),
    )
    m = bus.api("git")
    m.state.set("repo", mod.models.Repo(branch="feat/x"))
    m.state.set("branches", branches_state(mod, current="feat/x"))
    m.state.set("open_branch", "feat/x")

    lines = flatten(mod.draw.draw(m, 44, OPTIONS))
    assert "⬈ Create PR" in [line.strip() for line in lines]  # padded to its grid cell

    # The mod asks by the name it knows; resolving to the repo's own is Titan's job.
    mod.sections.branches.branches.create_pr(m, OPTIONS)
    assert runs == [("create-pr-ai", {})]


def test_without_a_pr_workflow_there_is_no_create_pr_button(mod, flatten):
    """Nothing to run (no github plugin, or the option cleared) means nothing to press."""
    from titan_cli.core.mods import ModBus

    def pane(options):
        bus = ModBus()
        bus.host = SimpleNamespace(repaint=lambda mod: None, resolve_workflow=lambda mod, name: None)
        m = bus.api("git")
        m.state.set("repo", mod.models.Repo(branch="feat/x"))
        m.state.set("branches", branches_state(mod, current="feat/x"))
        m.state.set("open_branch", "feat/x")
        return flatten(mod.draw.draw(m, 44, options))

    assert "⬈ Create PR" not in pane(OPTIONS)  # the host resolves it to nothing
    assert "⬈ Create PR" not in pane(dict(OPTIONS, create_pr_workflow=""))


def test_only_the_branch_you_are_on_offers_the_create_pr(mod, flatten):
    """It acts on the checked-out tree, as the pull and the push do."""
    from titan_cli.core.mods import ModBus

    bus = ModBus()
    bus.host = SimpleNamespace(repaint=lambda mod: None, resolve_workflow=lambda mod, name: name)
    m = bus.api("git")
    m.state.set("repo", mod.models.Repo(branch="feat/x"))
    m.state.set("branches", branches_state(mod, current="feat/x"))
    m.state.set("branches_open", True)
    m.state.set("open_branch", "feature/login")

    assert "⬈ Create PR" not in flatten(mod.draw.draw(m, 44, OPTIONS))


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
    m.state.set("branch_menu:feat/x", "Merge a branch into it…")

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


def _commits(n):
    return [SimpleNamespace(short_hash=f"h{i}", message_subject=f"c{i}", pr_number=None, formatted_date="today",
                            refs=[], hash=f"h{i}", message=f"c{i}") for i in range(n)]


def _press(tree, label):
    from titan_cli.core.mods import Box, Button
    stack = [tree]
    while stack:
        element = stack.pop()
        if isinstance(element, Button) and element.label == label:
            return element.on_press()
        if isinstance(element, Box):
            stack.extend(element.children)
    raise AssertionError(f"no button labelled {label!r}")


def test_show_more_raises_the_page_and_reads_the_repo_again(mod):
    from titan_cli.core.mods import ModBus

    runs, read = [], []
    bus = ModBus()
    bus.host = SimpleNamespace(repaint=lambda mod_: None, run=lambda mod_, fn: runs.append(fn))
    m = bus.api("git")
    m.state.set("refresh_repo", lambda: read.append(m.state.get("commit_limit")))
    m.state.set("commits_open", True)
    m.state.set("repo", mod.models.Repo(branch="x", commits=_commits(10)))   # a full page: more may remain

    _press(mod.draw.draw(m, 44, OPTIONS), "＋ Show more")
    runs[0]()

    assert read == [20]


def test_no_show_more_when_the_history_ran_out(mod, flatten):
    from titan_cli.core.mods import ModBus

    m = ModBus().api("git")
    m.state.set("commits_open", True)
    m.state.set("repo", mod.models.Repo(branch="x", commits=_commits(4)))    # a short page: that is all of it

    assert "＋ Show more" not in flatten(mod.draw.draw(m, 44, OPTIONS))


@pytest.mark.parametrize("key, model", [("repo", "Repo"), ("branches", "Branches"), ("worktrees", "Worktrees")])
def test_a_failed_read_can_be_copied_whole(mod, flatten, key, model):
    from titan_cli.core.mods import ModBus

    copied = []
    bus = ModBus()
    bus.host = SimpleNamespace(repaint=lambda mod: None, copy=lambda mod, text, what: copied.append((text, what)))
    m = bus.api("git")
    fields = {"branch": "feat/x"} if model == "Repo" else {}
    m.state.set(key, getattr(mod.models, model)(error="fatal: ambiguous argument 'HEAD'", **fields))

    tree = mod.draw.draw(m, 44, {}) if key == "repo" else getattr(mod.draw, f"{key}_section")(m, {}, 44)
    _press(tree, "⧉ Copy error")

    assert "fatal: ambiguous argument 'HEAD'" in flatten(tree)
    assert copied[0][1] == "error" and "fatal: ambiguous argument 'HEAD'" in copied[0][0]


def test_a_failed_branch_name_is_an_error_card_and_only_the_models_failure_offers_fix_with_ai(mod, flatten):
    from titan_cli.core.mods import AssistResult

    opened = []
    host = NewBranchHost(FakeGit())
    host.ai_assist = lambda mod_, prompt, cwd: opened.append(prompt) or AssistResult(True)
    m = open_new_branch_fold(mod, host)
    error = mod.sections.branches.new_branch.ERROR

    m.state.set(error, "AI: litellm.UnsupportedParamsError: tool_choice")
    lines = flatten(mod.draw.draw(m, 44, OPTIONS))
    assert "⧉ Copy error" in lines and "✦ Fix with AI" in lines
    next(b for b in buttons_of(mod.draw.draw(m, 44, OPTIONS)) if b.label == "✦ Fix with AI").on_press()
    assert opened and opened[0].startswith("Help me fix this error.") and "tool_choice" in opened[0]

    m.state.set(error, "feat/x already exists")
    lines = flatten(mod.draw.draw(m, 44, OPTIONS))
    assert "⧉ Copy error" in lines and "✦ Fix with AI" not in lines


def buttons_of(element):
    from titan_cli.core.mods import Button

    if isinstance(element, Button):
        yield element
    for child in getattr(element, "children", ()) or ():
        if child:
            yield from buttons_of(child)
