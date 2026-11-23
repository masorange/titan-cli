"""The git mod: its reading and drawing are plain functions over a fake client."""
from types import SimpleNamespace

import pytest

from titan_cli.core.mods import ModBus
from titan_plugin_git.readers import Branches, Repo, Worktrees
from titan_plugin_git.sections.branches import branches as branch_actions
from titan_plugin_git.sections.branches import new_branch
from titan_plugin_git.sections.worktrees.draw import worktrees_section

# What the loader hands `register`: every option in mod.toml, at its default.
OPTIONS = {
    "repo_refresh_seconds": 30,
    "refresh_key": "f5",
    "branches_refresh_seconds": 60,
    "recent_branches": 8,
    "commit_workflow": "commit-ai",
    "create_pr_workflow": "create-pr-ai",
    "suggestion_diff_chars": 4000,
    "merge_workflow": "merge-branch",
}

DIRTY = "2 uncommitted files - commit or stash before switching"


def branches_state(mod=None, blocked=None, names=("main", "feature/login"), current="feat/x", stashes=()):
    return Branches(
        items=[SimpleNamespace(name=n, is_current=n == current, formatted_date="2 d")
               for n in ((current,) + names if current else names)],
        current="feat/x",
        blocked=blocked,
        main_branch="main",
        stashes=list(stashes),
    )


def pane_for(host=None, **branches):
    """The mod's `m` with the branch you are on read, and its branches."""
    bus = ModBus()
    if host is not None:
        bus.host = host
    m = bus.api("git")
    m.state.set("repo", Repo(branch="feat/x", has_upstream=True, ahead=1))
    m.state.set("branches", branches_state(**branches))
    return m


def shown(mod, m, flatten, width=44, options=None):
    return [line.strip() for line in flatten(mod.draw.draw(m, width, OPTIONS if options is None else options))]


def walk(element):
    yield element
    for child in getattr(element, "children", ()) or ():
        if child:
            yield from walk(child)


def buttons_of(element):
    from titan_cli.ui.elements import Button

    return [e for e in walk(element) if isinstance(e, Button)]


def press(mod, m, flatten, label, width=44, options=None):
    """Press the button whose text starts with `label` in the pane as it is drawn now."""
    tree = mod.draw.draw(m, width, OPTIONS if options is None else options)
    for button in buttons_of(tree):
        if "".join(flatten(button)).strip().startswith(label):
            return button.on_press()
    raise AssertionError(f"no button labelled {label!r}")


def test_the_pane_is_the_branch_line_the_workspace_toolbar_and_a_way_into_the_workspace(mod, flatten):
    opened = []
    m = pane_for(SimpleNamespace(repaint=lambda mod_: None, resolve_workflow=lambda mod_, name: None,
                                 open_workspace=lambda mod_, name, focus=None: opened.append(name)))
    m.state.set("repo", Repo(branch="feat/x", has_upstream=True, ahead=1, added=4))

    lines = shown(mod, m, flatten)

    assert lines[0] == "⎇ feat/x ↑1 ↓0 +4"
    assert "⎇ feat/x ▾" in lines  # the toolbar's selector, as in the workspace
    for action in ("⇩ Pull", "⇧ Push ↑1", "＋ Branch", "⇄ Merge"):
        assert action in lines
    assert not any("Worktrees" in line or "History" in line for line in lines)
    press(mod, m, flatten, "⎇ Open Git workspace")
    assert opened == ["git"]


def test_a_failed_repo_read_is_an_error_card_apart_from_the_branch_line(mod, flatten):
    copied = []
    bus = ModBus()
    bus.host = SimpleNamespace(repaint=lambda mod_: None, copy=lambda mod_, text, what: copied.append((text, what)))
    m = bus.api("git")
    m.state.set("repo", Repo(branch="(no git)", error="git plugin not available"))

    lines = shown(mod, m, flatten)

    assert lines[0] == "⎇ (no git) no upstream"
    assert "git plugin not available" in lines
    press(mod, m, flatten, "⧉ Copy error")
    assert copied[0][1] == "error" and "git plugin not available" in copied[0][0]


def test_a_branch_without_upstream_says_so(mod, flatten):
    m = ModBus().api("git")
    m.state.set("repo", Repo(branch="feat/x"))
    assert shown(mod, m, flatten)[0] == "⎇ feat/x no upstream"


def test_refresh_key_is_bound_at_start_and_refreshes_the_repo(mod, tmp_path):
    from titan_cli.core.mods import AppStart

    keys, runs = {}, []
    host = SimpleNamespace(
        open_pane=lambda *a: None, every=lambda *a: None, repaint=lambda mod: None,
        run=lambda mod, fn: runs.append(fn), client=lambda name: None,
        bind_key=lambda mod, key, description, fn: keys.setdefault(key, (description, fn)) and None,
    )
    bus = ModBus()
    bus.host = host
    mod.register(bus.on_for("git"), dict(OPTIONS, refresh_key="f5"))

    bus.dispatch("app.start", AppStart(project_root=str(tmp_path)), lambda e: None)
    assert list(keys) == ["f5"] and keys["f5"][0] == "Refresh status"

    runs.clear()
    keys["f5"][1]()
    assert len(runs) == 1  # the refresh goes off the UI thread
    runs[0]()
    assert bus.api("git").state.get("repo").error == "git plugin not available"


def test_a_finished_or_aborted_workflow_refreshes_off_its_thread(mod, tmp_path):
    from titan_cli.core.mods import AppStart, WorkflowRun

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


# -- the branch toolbar, as the pane draws it ----------------------------------


def test_the_selector_opens_the_switcher_with_its_search(mod, flatten):
    from titan_cli.ui.elements import Input

    m = pane_for()
    assert "main" not in shown(mod, m, flatten)

    press(mod, m, flatten, "⎇ feat/x")
    lines = shown(mod, m, flatten)

    assert "⎇ feat/x ▴" in lines
    assert "main" in lines and "feature/login" in lines
    assert any(isinstance(e, Input) for e in walk(mod.draw.draw(m, 44, OPTIONS)))


def test_pressing_a_branch_in_the_switcher_checks_it_out(mod, flatten):
    from titan_cli.core.result import ClientSuccess

    asked = []
    git = SimpleNamespace(checkout=lambda name: asked.append(name) or ClientSuccess(data=None))
    m = pane_for(NewBranchHost(git))
    m.state.set("branch_panel", "switch")

    press(mod, m, flatten, "main")

    assert asked == ["main"]
    assert m.state.get("branch_panel") is None


def test_uncommitted_work_offers_commit_and_stash_and_refuses_the_switch(mod, flatten):
    m = pane_for(blocked=DIRTY)
    lines = shown(mod, m, flatten, width=80)

    assert f"⚠ {DIRTY}" in lines
    assert "✦ Commit" in lines and "⤓ Stash" in lines
    assert "⇄ Merge" not in lines  # a merge needs a clean tree

    m.state.set("branch_panel", "switch")
    lines = shown(mod, m, flatten, width=80)
    assert any("Commit or stash to switch branch" in line for line in lines)
    assert "main" not in lines


def test_what_does_not_fit_the_pane_goes_behind_the_dots(mod, flatten):
    m = pane_for(blocked=DIRTY)
    lines = shown(mod, m, flatten, width=44)

    assert "⋯ ▾" in lines

    press(mod, m, flatten, "⋯")
    assert any("New branch from here" in line for line in shown(mod, m, flatten, width=44))


def test_the_merge_panel_offers_the_base_branch_first_and_runs_the_workflow(mod, flatten):
    runs = []
    m = pane_for(SimpleNamespace(repaint=lambda mod_: None, resolve_workflow=lambda mod_, name: None,
                                 run_workflow=lambda mod_, name, params: runs.append((name, dict(params)))),
                 names=("feature/login", "main"))
    m.state.set("branch_panel", "merge")

    lines = shown(mod, m, flatten)
    offered = lines[lines.index("Merge into feat/x") + 1:]
    assert offered[:2] == ["main", "feature/login"]

    branch_actions.merge_into(m, "feat/x", "main", OPTIONS)
    assert runs == [("merge-branch", {"target_branch": "feat/x", "source_branch": "main"})]


def test_the_pr_button_runs_the_workflow_titan_would_pick_and_hides_without_one(mod, flatten):
    """The repo may extend the plugin's workflow: the button runs what the menu entry runs."""
    runs = []
    m = pane_for(SimpleNamespace(
        repaint=lambda mod_: None,
        resolve_workflow=lambda mod_, name: "create-pr" if name == "create-pr-ai" else None,
        run_workflow=lambda mod_, name, params: runs.append((name, dict(params))),
    ))

    assert "⬈ PR" in shown(mod, m, flatten)
    press(mod, m, flatten, "⬈ PR")
    assert runs == [("create-pr-ai", {})]

    assert "⬈ PR" not in shown(mod, m, flatten, options=dict(OPTIONS, create_pr_workflow=""))
    assert "⬈ PR" not in shown(mod, pane_for(), flatten)  # the host resolves it to nothing


def test_a_running_pull_replaces_the_buttons_with_what_it_is_doing(mod, flatten):
    """From the press to the toast the toolbar says it is working, and there is nothing to press twice."""
    m = pane_for()
    m.state.set("remote_action", "pull")

    lines = shown(mod, m, flatten)
    assert "… pulling origin/feat/x" in lines
    assert not any(line.startswith(("⇩ Pull", "⇧ Push")) for line in lines)

    m.state.set("remote_action", "push")
    assert "… pushing origin/feat/x" in shown(mod, m, flatten)

    m.state.set("remote_action", None)
    assert "⇩ Pull" in shown(mod, m, flatten)


def test_a_failed_branches_read_can_be_copied_whole(mod, flatten):
    copied = []
    bus = ModBus()
    bus.host = SimpleNamespace(repaint=lambda mod_: None, copy=lambda mod_, text, what: copied.append((text, what)))
    m = bus.api("git")
    m.state.set("repo", Repo(branch="feat/x"))
    m.state.set("branches", Branches(error="fatal: ambiguous argument 'HEAD'"))

    assert "fatal: ambiguous argument 'HEAD'" in shown(mod, m, flatten)
    press(mod, m, flatten, "⧉ Copy error")
    assert copied[0][1] == "error" and "fatal: ambiguous argument 'HEAD'" in copied[0][0]


def test_the_stashes_open_the_workspace_on_the_newest(mod, flatten):
    opened = []
    stashes = [SimpleNamespace(ref=f"stash@{{{i}}}", branch="feat/x", message=f"s{i}", formatted_date="1 h", hash=f"h{i}")
               for i in range(2)]
    m = pane_for(SimpleNamespace(repaint=lambda mod_: None, resolve_workflow=lambda mod_, name: None,
                                 open_workspace=lambda mod_, name, focus=None: opened.append((name, focus))),
                 stashes=stashes)

    press(mod, m, flatten, "⤒ Stashes (2)")

    assert opened == [("git", {"stash": "h0"})]
    assert not any(line.startswith("⤒ Stashes") for line in shown(mod, pane_for(), flatten))


# -- the new branch, from the toolbar's ＋ Branch panel -------------------------


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
    """The git client as the new-branch panel uses it."""

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


def open_new_branch_panel(host, **branches):
    """A pane with the toolbar's new-branch panel open."""
    m = pane_for(host, **branches)
    m.state.set("branch_panel", "new")
    return m


def test_the_new_branch_panel_offers_the_ai_and_only_creates_once_there_is_a_name(mod, flatten):
    m = pane_for(NewBranchHost(FakeGit()))
    press(mod, m, flatten, "＋ Branch")

    lines = shown(mod, m, flatten)
    assert "✦ Suggest with AI" in lines
    assert not any("Create" in line and "switch" in line for line in lines)

    m.state.set(new_branch.NAME, "feat/z")
    assert "✓ Create feat/z and switch" in shown(mod, m, flatten)


def test_uncommitted_work_still_offers_the_new_branch(mod, flatten):
    """Working on the wrong branch is exactly when it is needed, and git carries the changes over."""
    m = open_new_branch_panel(NewBranchHost(FakeGit()), blocked=DIRTY)

    assert "＋ Branch" in shown(mod, m, flatten, width=80)
    assert "✦ Suggest with AI" in shown(mod, m, flatten, width=80)


def test_the_suggestion_reads_the_diff_under_the_repo_s_prefixes_and_labels(mod, flatten):
    from titan_cli.core.mods import AIAnswer
    from titan_cli.core.result import ClientSuccess

    github = SimpleNamespace(list_labels=lambda: ClientSuccess(data=["bug", "enhancement"]))
    host = NewBranchHost(FakeGit(), github=github, answer=AIAnswer(text="`feat/Switch Branch`"))
    m = open_new_branch_panel(host)

    new_branch.suggest(m, OPTIONS)

    prompt, system = host.prompts[0]
    assert "feat, fix" in prompt  # read from the branches, remote ones without their remote
    assert "bug, enhancement" in prompt  # how this repo labels its PRs
    assert "api.py | 2 +-" in prompt and "notes.md (new file)" in prompt and "+new" in prompt
    assert "branch name only" in system

    # The answer only fills the field: nothing exists until the user presses for it.
    assert m.state.get(new_branch.NAME) == "feat/switch-branch"
    assert m.state.get(new_branch.STATUS) is None
    assert host.git.created == []
    assert "✓ Create feat/switch-branch and switch" in shown(mod, m, flatten)


def test_the_suggestion_says_why_it_has_no_name_without_touching_the_repo(mod):
    from titan_cli.core.mods import AIAnswer

    host = NewBranchHost(FakeGit(), answer=AIAnswer(error="no connection"))
    m = open_new_branch_panel(host)

    new_branch.suggest(m, OPTIONS)

    assert m.state.get(new_branch.ERROR) == "AI: no connection"
    assert host.git.created == []


def test_a_name_that_cannot_be_a_branch_is_refused_before_git_is_asked(mod, flatten):
    host = NewBranchHost(FakeGit())
    m = open_new_branch_panel(host)
    m.state.set(new_branch.NAME, "main")  # the switcher already lists it

    new_branch.create(m, "feat/x", OPTIONS)

    assert host.git.created == []
    assert "that branch already exists" in shown(mod, m, flatten)


def test_creating_branches_off_the_branch_you_are_on(mod):
    refreshed = []
    host = NewBranchHost(FakeGit())
    m = open_new_branch_panel(host)
    m.state.set("refresh", lambda: refreshed.append(True))
    new_branch.set_name(m, "Feat/New Thing")

    new_branch.create(m, "feat/x", OPTIONS)

    # The name is put in the shape git accepts before it is used, field included.
    assert host.git.created == [("feat/new-thing", "feat/x")]
    assert m.state.get(new_branch.NAME) == ""
    assert host.toasts == [("Created feat/new-thing from feat/x", "information")]
    assert refreshed == [True]


def test_a_refused_checkout_is_reported_under_the_field(mod, flatten):
    host = NewBranchHost(FakeGit(error="fatal: a branch named 'feat/z' already exists"))
    m = open_new_branch_panel(host)
    m.state.set(new_branch.NAME, "feat/z")

    new_branch.create(m, "feat/x", OPTIONS)

    assert any("already exists" in line for line in shown(mod, m, flatten))
    assert m.state.get(new_branch.STATUS) is None  # never stuck on the progress line


def test_a_failed_branch_name_is_an_error_card_and_only_the_models_failure_offers_fix_with_ai(mod, flatten):
    from titan_cli.core.mods import AssistResult

    opened = []
    host = NewBranchHost(FakeGit())
    host.ai_assist = lambda mod_, prompt, cwd: opened.append(prompt) or AssistResult(True)
    m = open_new_branch_panel(host)

    m.state.set(new_branch.ERROR, "AI: litellm.UnsupportedParamsError: tool_choice")
    lines = shown(mod, m, flatten)
    assert "⧉ Copy error" in lines and "✦ Fix with AI" in lines
    press(mod, m, flatten, "✦ Fix with AI")
    assert opened and opened[0].startswith("Help me fix this error.") and "tool_choice" in opened[0]

    m.state.set(new_branch.ERROR, "feat/x already exists")
    lines = shown(mod, m, flatten)
    assert "⧉ Copy error" in lines and "✦ Fix with AI" not in lines


# -- the worktrees card --------------------------------------------------------


def worktrees_state(paths=("/repo", "/repo-review"), current=None):
    return Worktrees(
        items=[SimpleNamespace(path=p, path_short=p.rsplit("/", 1)[-1], branch_display="main",
                               commit_short="abc1234", is_bare=False, is_detached=False, status_icon="📂")
               for p in paths],
        main_path=paths[0],
        current_path=current or paths[0],
    )


def worktrees(m, flatten):
    return flatten(worktrees_section(m, OPTIONS, 44))


def test_the_worktrees_card_folds_into_its_rows(flatten):
    m = ModBus().api("git")
    m.state.set("worktrees", worktrees_state())

    assert "▸ Worktrees (2)" in worktrees(m, flatten)

    m.state.set("worktrees_open", True)
    lines = worktrees(m, flatten)

    assert "▸ 📂 repo · main" in lines and "▸ 📂 repo-review · main" in lines
    assert "⌦ Prune stale records" in lines

    # The one Titan runs in says so, unless it is the main one (already untouchable).
    m.state.set("worktrees", worktrees_state(current="/repo-review"))
    assert "▸ 📂 repo-review · main · here" in worktrees(m, flatten)


def test_a_worktree_asks_before_it_is_removed(flatten):
    """One press arms the removal, a second one does it; the main worktree neither."""
    m = ModBus().api("git")
    m.state.set("worktrees", worktrees_state())
    m.state.set("worktrees_open", True)
    m.state.set("open_worktree", "/repo-review")

    lines = worktrees(m, flatten)
    assert "/repo-review" in lines and "✗ Remove worktree" in lines
    assert "✓ Confirm removal" not in lines

    m.state.set("worktree_confirm", "/repo-review")
    armed = worktrees(m, flatten)

    assert "✓ Confirm removal" in armed
    assert "The directory is deleted. This cannot be undone." in armed
    assert "⚠ Force removal (discards its changes)" not in armed  # only after git refuses

    m.state.set("worktree_force", "/repo-review")
    assert "⚠ Force removal (discards its changes)" in worktrees(m, flatten)


def test_the_main_worktree_offers_no_removal(flatten):
    m = ModBus().api("git")
    m.state.set("worktrees", worktrees_state())
    m.state.set("worktrees_open", True)
    m.state.set("open_worktree", "/repo")

    lines = worktrees(m, flatten)

    assert "Cannot be removed: the main worktree" in lines
    assert "✗ Remove worktree" not in lines


def test_a_failed_worktrees_read_can_be_copied_whole(flatten):
    copied = []
    bus = ModBus()
    bus.host = SimpleNamespace(repaint=lambda mod_: None, copy=lambda mod_, text, what: copied.append((text, what)))
    m = bus.api("git")
    m.state.set("worktrees", Worktrees(error="fatal: ambiguous argument 'HEAD'"))

    tree = worktrees_section(m, {}, 44)
    next(b for b in buttons_of(tree) if b.label == "⧉ Copy error").on_press()

    assert "fatal: ambiguous argument 'HEAD'" in flatten(tree)
    assert copied[0][1] == "error" and "fatal: ambiguous argument 'HEAD'" in copied[0][0]
