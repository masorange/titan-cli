"""Searching the repo's PRs with GitHub's syntax: on Enter, never per keystroke."""
from titan_plugin_github.readers import models
from types import SimpleNamespace

from titan_cli.core.mods import ModBus
from titan_cli.core.result import ClientError, ClientSuccess


def pane(github=None):
    bus = ModBus()
    bus.host = SimpleNamespace(repaint=lambda mod: None, run=lambda mod, fn: fn(), client=lambda name: github)
    return bus.api("github")


def test_typing_only_keeps_the_text_and_enter_searches(mod):
    asked = []
    m = pane(SimpleNamespace(search_prs=lambda q: asked.append(q) or ClientSuccess(data=[])))
    search = mod.sections.prs.search

    search.write(m, "author:ana")
    assert asked == [] and search.current(m) is None

    search.start(m, "author:ana")
    assert asked == ["author:ana"] and search.current(m).status == "done"


def test_a_search_keeps_what_github_found(mod, pr):
    found = [pr(7), pr(8)]
    m = pane(SimpleNamespace(search_prs=lambda q: ClientSuccess(data=found)))

    mod.sections.prs.search.start(m, "  label:bug ")

    result = mod.sections.prs.search.current(m)
    assert result.query == "label:bug" and result.prs == found


def test_an_empty_search_clears_it_and_asks_nothing(mod):
    asked = []
    m = pane(SimpleNamespace(search_prs=lambda q: asked.append(q) or ClientSuccess(data=[])))
    mod.sections.prs.search.start(m, "label:bug")

    mod.sections.prs.search.start(m, "   ")

    assert mod.sections.prs.search.current(m) is None and asked == ["label:bug"]


def test_a_failed_search_says_why_and_never_stays_running(mod):
    m = pane(SimpleNamespace(search_prs=lambda q: ClientError(error_message="HTTP 403: rate limit")))
    mod.sections.prs.search.start(m, "x")
    assert mod.sections.prs.search.current(m).error == "HTTP 403: rate limit"

    m = pane(SimpleNamespace(search_prs=lambda q: 1 / 0))
    mod.sections.prs.search.start(m, "x")
    assert mod.sections.prs.search.current(m).status == "error"


def test_the_answer_of_a_search_that_was_replaced_is_dropped(mod):
    m = pane()
    search = mod.sections.prs.search
    m.state.set("search", models.Search("new"))

    m.client = lambda name: SimpleNamespace(search_prs=lambda q: ClientSuccess(data=[1]))
    search.read(m, "old")

    assert search.current(m).query == "new" and search.current(m).status == "running"


def test_while_searching_the_section_shows_the_results_instead_of_the_groups(mod, flatten, pr):
    m = pane()
    m.state.set("prs", models.Prs(repo="o/r", to_review=[pr(5)], mine=[pr(2)], open_count=2))
    m.state.set("search", models.Search("label:bug", "done", prs=[pr(9)]))

    lines = flatten(mod.draw.draw(m, 44, {}, {"prs": True, "queue": False, "runs": False}))

    assert "1 result for “label:bug”" in lines and "✕ Clear search" in lines
    assert any("#9 PR 9" in line for line in lines)
    assert not any(line.startswith(("▸ Needs your review", "▾ Needs your review", "▸ Your PRs", "▾ Your PRs")) for line in lines)


def test_no_match_says_which_filters_exist(mod, flatten, pr):
    m = pane()
    m.state.set("prs", models.Prs(repo="o/r", open_count=0))
    m.state.set("search", models.Search("zzz", "done", prs=[]))

    text = " ".join(flatten(mod.draw.draw(m, 60, {}, {"prs": True, "queue": False, "runs": False})))

    assert "No PR matches" in text and "review:approved" in text


def test_a_failed_search_offers_retry_that_asks_again(mod, flatten):
    asked = []
    m = pane(SimpleNamespace(search_prs=lambda q: asked.append(q) or ClientError(error_message="HTTP 403")))
    mod.sections.prs.search.start(m, "label:bug")
    m.state.set("prs", models.Prs(repo="o/r"))

    card = mod.draw.search_results(m, mod.sections.prs.search.current(m), {}, {}, None)
    retry = next(e for e in card.children[-1].children if getattr(e, "label", "") == "⟳ Retry")
    retry.on_press()

    assert asked == ["label:bug", "label:bug"]
