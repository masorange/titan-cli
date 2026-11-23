"""The git workspace: what it reads, what it draws and what a press does, over a fake git client.

The log, the diffs and the graph lanes are the git plugin's, tested there.
"""
from pathlib import Path
from types import SimpleNamespace

from titan_cli.core.mods import WORKSPACES, ModBus, import_mod
from titan_cli.core.result import ClientError, ClientSuccess
from titan_cli.ui.elements import DIFF_COMPONENT, Button, Columns, Component, Text, plain
from titan_plugin_git.models.view import (
    UIDiffHunk,
    UIDiffLine,
    UIFileChange,
    UIFileDiff,
    UIGitCommit,
    UIUncommittedFiles,
)

ws = import_mod(Path(__file__).resolve().parent.parent, kind=WORKSPACES)
OPTIONS = {
    "refresh_seconds": 30, "refresh_key": "f5", "commits_shown": 40,
    "context_lines": 3, "diff_lines": 200, "recent_branches": 8,
    "commit_workflow": "commit-ai", "create_pr_workflow": "create-pr-ai", "merge_workflow": "merge-branch",
    "suggestion_diff_chars": 4000,
}


def commit(sha, *parents):
    return UIGitCommit(
        hash=sha, short_hash=sha[:7], message=f"{sha} subject", message_subject=f"{sha} subject",
        author="A <a@b.c>", author_short="A", date="2026-11-03", formatted_date="today", parents=list(parents),
    )


def diff(path, added="new"):
    return UIFileDiff(path, [UIDiffHunk("@@ -1 +1 @@", [UIDiffLine("add", added, None, 1)])])


class FakeGit:
    """A git client that answers from tables and records what it was asked."""

    repo_path = "/repo"

    def __init__(self, staged=(), unstaged=(), commits=(), commit_files=None):
        self.staged, self.unstaged = list(staged), list(unstaged)
        self.commits = list(commits)
        self.commit_files = commit_files or {}
        self.asked = []
        self.fail = None
        self.fail_index = False
        self.dirty = []
        self.stashes = []

    def get_status(self):
        return ClientSuccess(data=SimpleNamespace(
            branch="feat/x", has_upstream=True, ahead=1, behind=0,
            modified_files=self.dirty, staged_files=[], untracked_files=[],
        ))

    main_branch = "main"

    def list_recent_branches(self, limit):
        return ClientSuccess(data=[
            SimpleNamespace(name="feat/x", is_current=True, formatted_date="today", is_remote=False),
            SimpleNamespace(name="main", is_current=False, formatted_date="2 d", is_remote=False),
        ])

    def list_stashes(self):
        return ClientSuccess(data=list(self.stashes))

    def get_branches(self, remote=False):
        return ClientSuccess(data=[])

    def list_worktrees(self):
        return ClientSuccess(data=[SimpleNamespace(
            path="/repo", path_short="repo", branch="feat/x", branch_display="feat/x", status_icon="📂",
            is_bare=False, is_detached=False, commit_short="abc1234",
        )])

    def get_uncommitted_numstat(self, include_untracked):
        return ClientSuccess(data=[])

    def get_commits(self, root, limit, all_branches=False):
        self.asked.append(("log", limit))
        return ClientSuccess(data=self.commits[:limit])

    def get_uncommitted_files(self):
        self.asked.append("uncommitted")
        if self.fail:
            return ClientError(error_message=self.fail)
        return ClientSuccess(data=UIUncommittedFiles(staged=self.staged, unstaged=self.unstaged))

    def _move(self, path, source, target):
        moved = [f for f in source if f.path == path]
        source[:] = [f for f in source if f.path != path]
        target.extend(moved)

    def stage_file(self, path):
        self.asked.append(("stage", path))
        self._move(path, self.unstaged, self.staged)
        return ClientError(error_message="index.lock exists") if self.fail_index else ClientSuccess(data=None)

    def unstage_file(self, path):
        self.asked.append(("unstage", path))
        self._move(path, self.staged, self.unstaged)
        return ClientSuccess(data=None)

    def discard_file(self, path):
        self.asked.append(("discard", path))
        self.unstaged[:] = [f for f in self.unstaged if f.path != path]
        return ClientSuccess(data=None)

    def pull(self, remote, branch):
        self.asked.append(("pull", remote, branch))
        return ClientSuccess(data=None)

    def push(self, remote, branch):
        self.asked.append(("push", remote, branch))
        return ClientSuccess(data=None)

    def checkout(self, branch):
        self.asked.append(("checkout", branch))
        return ClientSuccess(data=None)

    def get_commit_files(self, sha):
        self.asked.append(("files", sha))
        return ClientSuccess(data=self.commit_files.get(sha, []))

    def get_worktree_file_diff(self, path, staged=False, context_lines=3):
        self.asked.append(("wip diff", path, staged))
        return ClientSuccess(data=diff(path, "staged" if staged else "unstaged"))

    def get_commit_file_diff(self, sha, path, context_lines=3):
        self.asked.append(("commit diff", sha, path))
        return ClientSuccess(data=diff(path))


def start(git, **options):
    """The workspace registered on a bus of its own kind and started, with every read run at once."""
    dock = []
    host = SimpleNamespace(
        run=lambda mod, fn: fn(), client=lambda name: git, every=lambda *a: None, repaint=lambda mod: None,
        copy=lambda *a: None, toast=lambda *a: None, dock=lambda mod, slot: dock.append(slot),
        bind_key=lambda *a: None, resolve_workflow=lambda mod, name: name,
    )
    bus = ModBus(prefix="workspace.", store_dir="workspaces")
    bus.host = host
    w = bus.api("git")
    ws.register(w, bus.on_for("git"), {**OPTIONS, **options})
    bus.start()
    return bus, w, dock


def walk(element):
    yield element
    for child in getattr(element, "children", ()) or ():
        if child:
            yield from walk(child)


def labels(bus, width=150):
    return [plain(e.label) for e in walk(bus.render_view("git", width)) if isinstance(e, Button)]


def texts(bus, width=150):
    return [plain(e) for e in walk(bus.render_view("git", width)) if isinstance(e, Text)]


def press(bus, starting, width=150):
    next(e for e in walk(bus.render_view("git", width)) if isinstance(e, Button) and plain(e.label).strip().startswith(starting)).on_press()


def press_exact(bus, label, width=150):
    next(e for e in walk(bus.render_view("git", width)) if isinstance(e, Button) and plain(e.label).strip() == label).on_press()


def diffs_shown(bus, width=150):
    return [e for e in walk(bus.render_view("git", width)) if isinstance(e, Component) and e.name == DIFF_COMPONENT]


STAGED = [UIFileChange("a.py", "M", 3, 1)]
UNSTAGED = [UIFileChange("b.py", "M", 2, 0), UIFileChange("new.txt", "?", 4, 0)]


def test_it_starts_on_the_uncommitted_changes_with_the_first_file_open():
    git = FakeGit(staged=STAGED, unstaged=UNSTAGED, commits=[commit("c1")])

    bus, w, dock = start(git)

    assert len(dock) == 1  # the tile
    assert any(label.startswith("▶ ● Uncommitted changes") for label in labels(bus))
    assert any(label.startswith("▾ a.py") for label in labels(bus))
    assert [d.props.diff.hunks[0].lines[0].text for d in diffs_shown(bus)] == ["staged"]
    assert ("wip diff", "a.py", True) in git.asked


def test_staged_and_unstaged_files_are_listed_apart_and_other_files_start_folded():
    bus, w, _ = start(FakeGit(staged=STAGED, unstaged=UNSTAGED))

    assert "▾ Staged (1)" in labels(bus) and "▾ Unstaged (2)" in labels(bus)
    assert [label for label in labels(bus) if label.startswith("▸") and "+" in label] == [
        "▸ b.py  modified  +2 -0", "▸ new.txt  new  +4 -0",
    ]


def test_the_toolbar_sits_above_three_tabs_and_the_history_is_the_one_open():
    git = FakeGit(staged=STAGED, commits=[commit("c1")])
    git.stashes = [SimpleNamespace(ref="stash@{0}", branch="feat/x", message="m", formatted_date="1 h", hash="h0")]
    bus, w, _ = start(git)
    shown = [label.strip("▌ ") for label in labels(bus)]

    assert shown.index("⎇ feat/x ▾") < shown.index("History")
    for tab in ("History", "Stashes (1)", "Worktrees (1)"):
        assert tab in shown
    assert any(label.startswith("⇩ Pull") for label in shown) and any(label.startswith("⇧ Push") for label in shown)
    assert any(label.startswith("▶ ● Uncommitted changes") for label in labels(bus))


def test_pressing_a_tab_swaps_what_is_under_the_toolbar_and_keeps_the_toolbar():
    bus, w, _ = start(FakeGit(staged=STAGED, commits=[commit("a" * 40)]))

    press(bus, "Worktrees")
    assert not any("Uncommitted changes" in label for label in labels(bus))
    assert any("repo" in label for label in labels(bus))
    assert any(label.startswith("⇩ Pull") for label in labels(bus))

    press(bus, "History")
    assert any("Uncommitted changes" in label for label in labels(bus))


def test_a_dirty_tree_says_so_in_the_top_bar_and_offers_commit_and_stash_in_the_toolbar():
    git = FakeGit(staged=STAGED)
    git.dirty = ["a.py"]
    bus, w, _ = start(git)

    top = bus.render_view("git", 150).children[0]
    assert any("uncommitted changes" in plain(e) for e in walk(top) if isinstance(e, Text))
    assert not any(isinstance(e, Button) for e in walk(top))
    shown = [label.strip() for label in labels(bus)]
    assert "✦ Commit" in shown and "⤓ Stash" in shown
    assert any("commit or stash" in t for t in texts(bus))

    clean, cw, _ = start(FakeGit(staged=STAGED))
    assert not any(label.strip() in ("✦ Commit", "⤓ Stash") for label in labels(clean))


def test_the_branch_selector_opens_the_recent_branches_and_pressing_one_switches_to_it():
    git = FakeGit(staged=STAGED)
    bus, w, _ = start(git)
    assert not any(label.strip() == "main" for label in labels(bus))

    press(bus, "⎇ feat/x")
    assert "▴" in labels(bus)[labels(bus).index("⎇ feat/x ▴")]
    assert any("Switch to" in t for t in texts(bus))

    press(bus, "main")
    assert ("checkout", "main") in git.asked
    assert w.state.get("branch_panel") is None


def test_a_dirty_tree_says_why_the_switch_panel_has_no_branches():
    git = FakeGit(staged=STAGED)
    git.dirty = ["a.py"]
    bus, w, _ = start(git)

    press(bus, "⎇ feat/x")

    assert any("Commit or stash to switch branch" in t for t in texts(bus))
    assert not any(label.strip() == "main" for label in labels(bus))


def test_every_action_is_on_the_row_when_it_fits_and_new_branch_and_merge_open_their_panel():
    bus, w, _ = start(FakeGit(staged=STAGED))
    shown = [label.strip() for label in labels(bus)]

    for action in ("⇩ Pull", "⇧ Push ↑1", "⬈ PR", "＋ Branch", "⇄ Merge"):
        assert action in shown
    assert not any(label.startswith("⋯") for label in shown)

    press(bus, "＋ Branch")
    assert any("Suggest with AI" in label for label in labels(bus))
    press(bus, "＋ Branch")
    assert not any("Suggest with AI" in label for label in labels(bus))

    press(bus, "⇄ Merge")
    assert "main" in [label.strip() for label in labels(bus)]


def test_what_does_not_fit_on_the_row_is_grouped_behind_the_dots():
    bus, w, _ = start(FakeGit(staged=STAGED))
    narrow = 36
    shown = [label.strip() for label in labels(bus, narrow)]

    assert "⇩ Pull" in shown and "⇧ Push ↑1" in shown
    assert "＋ Branch" not in shown and "⇄ Merge" not in shown
    assert "⋯ ▾" in shown

    press(bus, "⋯", narrow)
    opened = [label.strip() for label in labels(bus, narrow)]
    assert "▸ ＋ New branch from here…" in opened and "▸ ⇄ Merge a branch into it…" in opened
    press(bus, "▸ ＋ New branch", narrow)
    assert any("Suggest with AI" in label for label in labels(bus, narrow))


def test_fit_keeps_the_order_and_gives_up_the_last_actions_first():
    from types import SimpleNamespace as NS

    fit = ws.draw.toolbar.__globals__["fit"]
    acts = [NS(key=k, cells=c) for k, c in (("a", 10), ("b", 10), ("c", 10), ("d", 10))]

    assert [a.key for a in fit(acts, 50)[0]] == ["a", "b", "c", "d"]  # 40 cells in a 46-cell room
    shown, hidden = fit(acts, 34)  # 30 room: two fit with the dots' 4 cells
    assert [a.key for a in shown] == ["a", "b"] and [a.key for a in hidden] == ["c", "d"]


def test_pull_and_push_run_on_the_branch_you_are_on():
    git = FakeGit(staged=STAGED)
    bus, w, _ = start(git)

    press(bus, "⇩ Pull")
    press(bus, "⇧ Push")

    assert ("pull", "origin", "feat/x") in git.asked and ("push", "origin", "feat/x") in git.asked


def stash_picker(git, **kw):
    git.stashes = [
        SimpleNamespace(ref="stash@{0}", branch="feat/x", message="newest", formatted_date="1 h ago", hash="h0"),
        SimpleNamespace(ref="stash@{1}", branch="main", message="older", formatted_date="3 d ago", hash="h1"),
    ]
    bus, w, _ = start(git, **kw)
    w.state.set("tab", "stashes")
    return bus, w


def test_pressing_a_stash_of_the_list_shows_its_changes_and_a_menu_of_actions():
    git = FakeGit(staged=STAGED, commit_files={"h1": [UIFileChange("old.py", "M", 5, 2)]})
    bus, w = stash_picker(git)
    shown = [label.strip() for label in labels(bus)]
    assert "newest · feat/x · 1 h ago" in shown and "older · main · 3 d ago" in shown
    assert any(label.startswith("Stashes (2)") for label in [text.strip("▌ ") for text in labels(bus)])

    press(bus, "older · main")

    assert ("files", "h1") in git.asked
    assert "Stash stash@{1}" in texts(bus) and "older" in texts(bus)
    shown = [label.strip() for label in labels(bus)]
    assert any(label.startswith("▾ old.py") for label in shown)  # its first file opens on its own
    for action in ("⤴ Apply, keep it", "⤒ Pop: apply and remove", "✗ Drop…"):
        assert action in shown


def test_the_stash_menu_applies_pops_and_drops_the_stash_where_it_sits_in_the_list_now():
    git = FakeGit(staged=STAGED, commit_files={"h1": [UIFileChange("old.py", "M", 5, 2)]})
    calls = []
    git.stash_apply = lambda ref=None: (calls.append(("apply", ref)), ClientSuccess(data=True))[1]
    git.stash_pop = lambda ref=None: (calls.append(("pop", ref)), ClientSuccess(data=True))[1]
    git.stash_drop = lambda ref: (calls.append(("drop", ref)), ClientSuccess(data=True))[1]
    bus, w = stash_picker(git)
    press(bus, "older · main")

    press(bus, "⤴ Apply")
    press(bus, "⤒ Pop")
    assert calls == [("apply", "stash@{1}"), ("pop", "stash@{1}")]

    press(bus, "✗ Drop…")
    assert len(calls) == 2  # asks first
    press(bus, "Cancel")
    press(bus, "✗ Drop…")
    press(bus, "✓ Confirm drop")
    assert calls[-1] == ("drop", "stash@{1}")


def test_a_stash_that_is_gone_goes_back_to_the_uncommitted_changes():
    git = FakeGit(staged=STAGED, commit_files={"h1": [UIFileChange("old.py", "M", 5, 2)]})
    bus, w = stash_picker(git)
    press(bus, "older · main")
    git.stashes = [s for s in git.stashes if s.hash != "h1"]

    w.run(lambda: None)
    w.state.get("refresh")()

    assert w.state.get("selected") == "wip"


def test_a_failed_branches_read_keeps_the_stash_being_read():
    git = FakeGit(staged=STAGED, commit_files={"h1": [UIFileChange("old.py", "M", 5, 2)]})
    bus, w = stash_picker(git)
    press(bus, "older · main")
    git.get_status = lambda: ClientError(error_message="index.lock exists")

    w.run(lambda: None)
    w.state.get("refresh")()

    assert w.state.get("selected") == "h1" and w.state.get("stash_selected")


def test_the_last_line_of_the_list_clears_it_but_only_after_a_second_press():
    git = FakeGit(staged=STAGED)
    cleared = []
    git.stash_clear = lambda: (cleared.append(True), ClientSuccess(data=True))[1]
    bus, w = stash_picker(git)
    shown = [label.strip() for label in labels(bus)]
    assert shown.index("✗ Clear stash list…") > shown.index("older · main · 3 d ago")

    press(bus, "✗ Clear stash list…")
    assert cleared == [] and any("Drops all 2 stashes" in t for t in texts(bus))

    press(bus, "Cancel")
    assert cleared == [] and "✗ Clear stash list…" in [label.strip() for label in labels(bus)]

    press(bus, "✗ Clear stash list…")
    press(bus, "✓ Confirm clear")
    assert cleared == [True]


def test_pressing_a_commit_reads_its_files_and_shows_its_header():
    git = FakeGit(staged=STAGED, commits=[commit("c1"), commit("c2")], commit_files={"c2": [UIFileChange("x.py", "M", 1, 1)]})
    bus, w, _ = start(git)

    next(b for b in walk(bus.render_view("git", 150)) if isinstance(b, Button) and "c2 subject" in plain(b.label)).on_press()

    assert w.state.get("selected") == "c2"
    assert ("files", "c2") in git.asked and ("commit diff", "c2", "x.py") in git.asked
    assert "c2 subject" in texts(bus) and "Uncommitted changes" not in texts(bus)
    assert any(label.startswith("▶ ") and "c2 subject" in label for label in labels(bus))


def test_pressing_a_file_opens_its_diff_and_pressing_it_again_folds_it():
    git = FakeGit(unstaged=UNSTAGED)
    bus, w, _ = start(git)
    assert len(diffs_shown(bus)) == 1  # b.py, opened on its own

    press(bus, "▸ new.txt")
    assert len(diffs_shown(bus)) == 2
    press(bus, "▾ new.txt")

    assert len(diffs_shown(bus)) == 1


def test_staged_and_unstaged_fold_and_unfold_on_their_title():
    bus, w, _ = start(FakeGit(staged=STAGED, unstaged=UNSTAGED))

    press(bus, "▾ Unstaged")
    assert "▸ Unstaged (2)" in labels(bus) and not any(label.startswith("▸ b.py") for label in labels(bus))
    press(bus, "▸ Unstaged")
    assert any(label.startswith("▸ b.py") for label in labels(bus))


def test_an_empty_working_tree_says_so():
    bus, w, _ = start(FakeGit())

    assert "Working tree clean" in texts(bus)


def test_a_failed_read_is_an_error_card_that_rereads_on_retry():
    git = FakeGit()
    git.fail = "fatal: not a git repository"
    bus, w, _ = start(git)
    assert any("fatal: not a git repository" in t for t in texts(bus))

    git.fail = None
    git.unstaged = UNSTAGED
    press(bus, "Retry")

    assert "▾ Unstaged (2)" in labels(bus)


def test_the_screen_is_two_columns_when_wide_and_stacks_when_narrow():
    bus, w, _ = start(FakeGit(staged=STAGED))

    assert any(isinstance(e, Columns) for e in walk(bus.render_view("git", 150)))
    assert not any(isinstance(e, Columns) for e in walk(bus.render_view("git", 80)))


def test_show_more_commits_raises_the_page_and_rereads():
    git = FakeGit(commits=[commit(f"c{i}") for i in range(100)])
    bus, w, _ = start(git, commits_shown=40)
    assert ("log", 40) in git.asked

    press(bus, "＋ Show more")

    assert ("log", 80) in git.asked


def test_a_mods_row_opens_it_on_that_commit():
    git = FakeGit(commits=[commit("c1"), commit("c2")], commit_files={"c2": [UIFileChange("x.py", "M", 1, 1)]})
    bus, w, _ = start(git)

    bus.opened("git", {"sha": "c2"})

    assert w.state.get("selected") == "c2"


def test_opening_from_the_dock_tile_keeps_what_was_selected():
    bus, w, _ = start(FakeGit(commits=[commit("c1")]))
    w.state.set("selected", "c1")

    bus.opened("git", None)

    assert w.state.get("selected") == "c1"


def test_a_diff_longer_than_the_page_offers_more_lines():
    long = UIFileDiff("a.py", [UIDiffHunk("@@", [UIDiffLine("add", str(i), None, i) for i in range(50)])])
    git = FakeGit(staged=STAGED)
    git.get_worktree_file_diff = lambda path, staged=False, context_lines=3: ClientSuccess(data=long)
    bus, w, _ = start(git, diff_lines=20)
    assert diffs_shown(bus)[0].props.max_lines == 20

    press(bus, "＋ Show more lines (30 left)")

    assert diffs_shown(bus)[0].props.max_lines == 40


def test_a_failed_log_is_an_error_card_that_rereads_on_retry():
    git = FakeGit(commits=[commit("c1")])
    original = git.get_commits
    git.get_commits = lambda root, limit, all_branches=False: ClientError(error_message="fatal: bad object")
    bus, w, _ = start(git)
    assert any("fatal: bad object" in t for t in texts(bus))

    git.get_commits = original
    press(bus, "Retry")

    assert not any("fatal: bad object" in t for t in texts(bus))
    assert any("c1 subject" in label for label in labels(bus))


def test_stage_moves_a_file_to_the_staged_group_and_keeps_its_card_open():
    git = FakeGit(staged=STAGED, unstaged=UNSTAGED)
    bus, w, _ = start(git)
    press(bus, "▸ b.py")

    press_exact(bus, "+ Stage")

    assert ("stage", "b.py") in git.asked
    assert "▾ Staged (2)" in labels(bus) and "▾ Unstaged (1)" in labels(bus)
    assert "▾ b.py" in " ".join(labels(bus)) and "− Unstage" in labels(bus)


def test_unstage_moves_a_file_back_to_the_unstaged_group():
    git = FakeGit(staged=STAGED, unstaged=UNSTAGED)
    bus, w, _ = start(git)

    press_exact(bus, "− Unstage")

    assert ("unstage", "a.py") in git.asked
    assert "▾ Unstaged (3)" in labels(bus) and not any(label.startswith("▾ Staged") for label in labels(bus))


def test_stage_all_and_unstage_all_act_on_the_whole_group():
    git = FakeGit(staged=STAGED, unstaged=UNSTAGED)
    bus, w, _ = start(git)

    press(bus, "+ Stage all")

    assert [a for a in git.asked if a[0] == "stage"] == [("stage", "b.py"), ("stage", "new.txt")]
    assert "▾ Staged (3)" in labels(bus) and "+ Stage all" not in labels(bus)


def test_discard_needs_a_second_press_and_cancel_leaves_the_file_alone():
    git = FakeGit(unstaged=UNSTAGED)
    bus, w, _ = start(git)

    press_exact(bus, "✗ Discard…")
    assert not any(a[0] == "discard" for a in git.asked) and "✓ Confirm discard" in labels(bus)
    press(bus, "Cancel")
    assert not any(a[0] == "discard" for a in git.asked) and "✗ Discard…" in labels(bus)

    press_exact(bus, "✗ Discard…")
    press(bus, "✓ Confirm discard")

    assert ("discard", "b.py") in git.asked
    assert not any(label.startswith("▾ b.py") or label.startswith("▸ b.py") for label in labels(bus))


def test_a_failed_index_change_is_toasted_and_the_files_are_reread():
    git = FakeGit(unstaged=UNSTAGED)
    git.fail_index = True
    bus, w, _ = start(git)
    toasts = []
    bus.host.toast = lambda mod, text, severity: toasts.append((text, severity))

    press_exact(bus, "+ Stage")

    assert toasts == [("Could not stage b.py: index.lock exists", "error")]


def test_a_commit_has_no_stage_or_discard_buttons():
    git = FakeGit(commits=[commit("a" * 40)], commit_files={"a" * 40: [UIFileChange("c.py", "M", 1, 0)]})
    bus, w, _ = start(git)
    w.state.set("selected", "a" * 40)

    assert not any(label in ("+ Stage", "− Unstage", "✗ Discard…") for label in labels(bus))


def test_a_file_card_is_titled_by_its_name_and_shows_the_whole_path_when_open():
    deep = UIFileChange("docs/business/very/deep/01-brands.md", "M", 1, 1)
    bus, w, _ = start(FakeGit(unstaged=[deep, UIFileChange("b.py", "M", 2, 0)]))

    assert "▾ 01-brands.md  docs/business/very/deep  modified  +1 -1" in labels(bus)
    assert "docs/business/very/deep/01-brands.md" in texts(bus)


def test_a_long_folder_is_cut_from_the_start_and_a_root_file_has_none():
    short_dir = ws.detail.short_dir

    assert short_dir("a.py") == ""
    assert short_dir("src/a.py") == "src"
    cut = short_dir("one/two/three/four/five/six/seven/eight/a.py")
    assert cut.startswith("…") and cut.endswith("seven/eight") and len(cut) == 30


def test_show_less_goes_back_one_page_and_only_shows_once_more_was_pressed():
    git = FakeGit(commits=[commit(f"c{i}") for i in range(100)])
    bus, w, _ = start(git, commits_shown=40)
    assert not any("Show less" in label for label in labels(bus))

    press(bus, "＋ Show more")
    assert any("Show less" in label for label in labels(bus))

    press(bus, "－ Show less")
    assert git.asked[-1] == ("log", 40)
    assert not any("Show less" in label for label in labels(bus))
