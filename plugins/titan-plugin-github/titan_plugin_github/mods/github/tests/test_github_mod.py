"""The github mod: the summary in the pane, its badge and its way into the workspace."""
from types import SimpleNamespace

from titan_cli.core.mods import AppStart, ModBus
from titan_cli.core.result import ClientSuccess
from titan_cli.ui.elements import Box, Button, Text, plain
from titan_plugin_github.readers import models

OPTIONS = {"prs_refresh_seconds": 120, "queue_refresh_seconds": 60, "runs_refresh_seconds": 30, "refresh_key": "", "queue_shown": 8}


def texts(element):
    if isinstance(element, Text):
        return [plain(element)]
    if isinstance(element, Button):
        return [plain(element.label)]
    if isinstance(element, Box):
        return [line for child in element.children for line in texts(child)]
    return []


def _pane(mod, **state):
    opened = []
    bus = ModBus()
    bus.host = SimpleNamespace(repaint=lambda mod: None,
                               open_workspace=lambda mod, name, focus=None: opened.append((name, focus)))
    m = bus.api("github")
    for key, value in state.items():
        m.state.set(key, value)
    return m, opened


def _buttons(element):
    if isinstance(element, Button):
        return [element]
    if isinstance(element, Box):
        return [b for child in element.children for b in _buttons(child)]
    return []


def test_the_pane_lists_what_needs_you_and_leaves_out_what_only_waits(mod, pr):
    m, _ = _pane(
        mod,
        prs=models.Prs(
            repo="o/r", open_count=19,
            to_review=[pr(5, conflicts=True), pr(6)],
            mine=[pr(2, checks="failing"), pr(3), pr(4, review="approved"), pr(8, draft=True, review="approved")],
        ),
    )

    lines = texts(mod.draw.draw(m))

    assert "19 open · 2 to review · 4 yours" in lines
    assert "Review requested (2)" in lines and "Your PRs (2)" in lines
    assert "   @ana · 2d ago · ⚠ conflicts" in lines
    assert "   ✗ checks failing" in lines and "   ✓ ready to merge" in lines
    # PR 3 only waits for a review and PR 8 is a draft: neither asks anything of you.
    assert not any("#3 " in line or "#8 " in line for line in lines)


def test_pressing_a_pr_or_a_failed_run_opens_the_workspace_on_it(mod, pr):
    from titan_plugin_github.models.view import UIWorkflowRun

    failed = UIWorkflowRun(id=77, title="build-and-tests", workflow="ci", event="push", state="failure",
                           state_label="failed", branch="develop", age="37m ago")
    m, opened = _pane(
        mod,
        prs=models.Prs(repo="o/r", to_review=[pr(5)], mine=[pr(2, checks="failing")]),
        runs=models.Runs(runs=[failed]),
    )

    for button in _buttons(mod.draw.draw(m)):
        button.on_press()

    assert opened == [("github", {"pr": 5}), ("github", {"pr": 2}), ("github", {"run": 77}), ("github", None)]


def test_each_section_shows_three_rows_and_counts_the_rest(mod, pr):
    m, _ = _pane(mod, prs=models.Prs(repo="o/r", to_review=[pr(n) for n in range(1, 8)]))

    lines = texts(mod.draw.draw(m))

    assert "Review requested (7)" in lines and "…and 4 more" in lines
    assert sum(1 for line in lines if line.startswith("#")) == 3


def test_with_nothing_pending_the_pane_says_so_and_still_shows_the_totals(mod, pr):
    m, _ = _pane(mod, prs=models.Prs(repo="o/r", open_count=4, mine=[pr(3)]))

    lines = texts(mod.draw.draw(m))

    assert "✓ All clear: nothing needs you" in lines and "4 open · 0 to review · 1 yours" in lines


def test_the_pane_says_why_it_has_nothing(mod):
    m, _ = _pane(mod)
    assert texts(mod.draw.draw(m))[0] == "Loading…"

    m.state.set("prs", models.Prs(error="gh: not logged in"))
    assert any("gh: not logged in" in line for line in texts(mod.draw.draw(m)))


def test_review_requests_badge_the_rail_icon_and_none_clears_it(mod, tmp_path, pr):
    timers, badges = [], []
    to_review = [[pr(5), pr(6)]]
    github = SimpleNamespace(
        get_repo_full_name=lambda: "o/r",
        list_pending_review_prs=lambda: ClientSuccess(data=to_review[0]),
        list_my_prs=lambda: ClientSuccess(data=[]),
        count_open_prs=lambda: ClientSuccess(data=2),
    )
    host = SimpleNamespace(
        open_pane=lambda *a: None, every=lambda mod, seconds, fn, immediately: timers.append(fn),
        badge=lambda mod, pane, text, severity: badges.append((pane, text, severity)),
        toast=lambda *a: None, repaint=lambda mod: None, run=lambda mod, fn: None,
        client=lambda name: github if name == "github" else None, bind_key=lambda *a: None,
    )
    bus = ModBus()
    bus.host = host
    mod.register(bus.on_for("github"), OPTIONS)
    bus.dispatch("app.start", AppStart(project_root=str(tmp_path)), lambda e: None)

    refresh_prs = timers[0]
    refresh_prs()
    to_review[0] = []
    refresh_prs()

    assert badges == [("github", "2", "warning"), ("github", None, "warning")]
