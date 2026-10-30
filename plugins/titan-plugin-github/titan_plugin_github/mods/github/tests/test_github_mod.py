"""The github mod: the summary in the pane, its badge and its way into the workspace."""
from types import SimpleNamespace

from titan_cli.core.mods import AppStart, ModBus
from titan_cli.core.result import ClientSuccess
from titan_cli.ui.elements import Box, Button, Text
from titan_plugin_github.readers import models

OPTIONS = {"prs_refresh_seconds": 120, "queue_refresh_seconds": 60, "runs_refresh_seconds": 30, "refresh_key": "", "queue_shown": 8}


def texts(element):
    if isinstance(element, Text):
        return ["".join(p if isinstance(p, str) else "".join(texts(p)) for p in element.parts)]
    if isinstance(element, Button):
        return [element.label]
    if isinstance(element, Box):
        return [line for child in element.children for line in texts(child)]
    return []


def test_the_pane_counts_what_waits_and_opens_the_workspace(mod, pr):
    opened = []
    bus = ModBus()
    bus.host = SimpleNamespace(repaint=lambda mod: None, open_workspace=lambda mod, name: opened.append(name))
    m = bus.api("github")
    m.state.set("prs", models.Prs(repo="o/r", to_review=[pr(5), pr(6)], mine=[pr(2)], open_count=9))

    tree = mod.draw.draw(m)

    assert "To review 2" in texts(tree) and "Your PRs 1" in texts(tree)
    button = next(c for c in tree.children if isinstance(c, Button))
    button.on_press()
    assert opened == ["github"]


def test_the_pane_says_why_it_has_nothing(mod):
    m = ModBus().api("github")
    assert texts(mod.draw.draw(m))[0] == "Loading…"

    m.state.set("prs", models.Prs(error="gh: not logged in"))
    assert texts(mod.draw.draw(m))[0] == "Could not read PRs: gh: not logged in"


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
