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
    "graph_max_lanes": 8, "context_lines": 3, "diff_lines": 200, "recent_branches": 8,
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
    next(e for e in walk(bus.render_view("git", width)) if isinstance(e, Button) and plain(e.label).startswith(starting)).on_press()


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


def test_the_branch_card_the_switcher_and_the_worktrees_sit_above_the_history():
    bus, w, _ = start(FakeGit(staged=STAGED))
    shown = labels(bus)
    history = next(i for i, label in enumerate(shown) if label.startswith("▶ ● Uncommitted changes"))

    for label in ("▸ feat/x · today · here", "▸ Switch branch (1)", "▸ Worktrees (1)"):
        assert label in shown
        assert shown.index(label) < history


def test_uncommitted_work_opens_the_branch_card_on_the_way_out_of_the_block():
    git = FakeGit(staged=STAGED)
    git.dirty = ["a.py"]
    bus, w, _ = start(git)

    assert any("17" not in t and "uncommitted" in t for t in texts(bus))
    assert any("Commit with AI" in label for label in labels(bus))


def test_a_dirty_tree_offers_to_stash_and_a_stash_offers_to_pop():
    git = FakeGit(staged=STAGED)
    git.dirty = ["a.py"]
    git.stashes = [SimpleNamespace(ref="stash@{0}", branch="feat/x", message="m", formatted_date="1 h")]
    bus, w, _ = start(git)
    shown = [label.strip() for label in labels(bus)]
    assert "⤓ Stash changes" in shown and "▸ ⤒ Pop stash (1)…" in shown

    clean, cw, _ = start(FakeGit(staged=STAGED))
    cw.state.set("open_branch", "feat/x")
    assert not any("Stash" in label or "Pop stash" in label for label in labels(clean))


def test_the_current_branch_groups_its_actions_in_three_cards():
    git = FakeGit(staged=STAGED)
    git.dirty = ["a.py"]
    bus, w, _ = start(git)
    shown = [t.strip() for t in texts(bus)]

    assert [t for t in shown if t in ("Working tree", "Remote", "Branch")] == ["Working tree", "Remote", "Branch"]


def stash_picker(git):
    git.stashes = [
        SimpleNamespace(ref="stash@{0}", branch="feat/x", message="newest", formatted_date="1 h ago"),
        SimpleNamespace(ref="stash@{1}", branch="main", message="older", formatted_date="3 d ago"),
    ]
    bus, w, _ = start(git)
    w.state.set("open_branch", "feat/x")
    w.state.set("branch_menu:feat/x:tree", "⤒ Pop stash (2)…")
    return bus, w


def test_the_stashes_are_a_picker_and_choosing_one_pops_that_one():
    git = FakeGit(staged=STAGED)
    popped = []
    git.stash_pop = lambda ref=None: (popped.append(ref), ClientSuccess(data=True))[1]
    bus, w = stash_picker(git)
    assert "▾ ⤒ Pop stash (2)…" in [label.strip() for label in labels(bus)]

    shown = [label.strip() for label in labels(bus)]
    assert "newest · feat/x · 1 h ago" in shown and "older · main · 3 d ago" in shown
    press(bus, "older · main")
    assert popped == ["stash@{1}"]


def test_the_last_line_of_the_picker_clears_the_list_but_only_after_a_second_press():
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


def test_the_history_is_a_card_that_folds():
    bus, w, _ = start(FakeGit(staged=STAGED, commits=[commit("a" * 40)]))

    assert "▾ History" in labels(bus) and any("Uncommitted changes" in label for label in labels(bus))
    press(bus, "▾ History")
    assert "▸ History" in labels(bus) and not any("Uncommitted changes" in label for label in labels(bus))


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
