"""`ask_ai` and the pieces that draw it: one claim per key, the state it ends in, the button, the box and the chip."""
import threading

from titan_cli.core.mods import (
    AIAnswer,
    AIResult,
    Box,
    ModBus,
    Text,
    ai_answer_box,
    ai_ask_button,
    ai_chip,
    ai_result,
    ask_ai,
    refresh_ai_chip,
)
from titan_cli.core.mods.elements import plain


class Host:
    """Runs `m.run` jobs by hand, so a test decides when the background work happens."""

    def __init__(self, who="Local · qwen"):
        self.jobs, self.copied, self.configured, self.who = [], [], [], who

    def run(self, mod, fn):
        self.jobs.append(fn)

    def repaint(self, mod):
        pass

    def copy(self, mod, text, what):
        self.copied.append((text, what))

    def ai_describe(self, mod):
        return self.who

    def ai_configure(self, mod, title, on_done):
        self.configured.append((title, on_done))

    def finish(self):
        while self.jobs:
            self.jobs.pop(0)()


def api():
    bus = ModBus()
    bus.host = Host()
    return bus.api("jira"), bus.host


def labels(node):
    out = []
    for child in getattr(node, "children", ()):
        out += labels(child)
    if hasattr(node, "label"):
        out.append(plain(node.label))
    if isinstance(node, Text):
        out.append(plain(node))
    return out


def test_asking_runs_the_work_off_the_ui_thread_and_keeps_the_answer_under_the_key():
    m, host = api()

    assert ask_ai(m, "summary:A-1", lambda m: AIAnswer(text="It asks for X", model="qwen")) is True
    assert ai_result(m, "summary:A-1").status == "running" and len(host.jobs) == 1

    host.finish()

    assert ai_result(m, "summary:A-1") == AIResult("done", "It asks for X", "qwen")


def test_a_failed_answer_returned_by_work_is_logged_like_a_raised_one(monkeypatch):
    m, host = api()
    logged = []
    monkeypatch.setattr(m.log, "warning", lambda event, **kw: logged.append((event, kw)), raising=False)

    ask_ai(m, "k", lambda m: AIAnswer(error="model not found"))
    host.finish()

    assert ai_result(m, "k") == AIResult("error", error="model not found")
    assert logged == [("mod_ask_ai_failed", {"key": "k", "error": "model not found"})]


def test_a_second_ask_under_the_same_key_while_running_starts_nothing():
    m, host = api()
    calls = []

    first = ask_ai(m, "k", lambda m: calls.append(1) or AIAnswer(text="a"))
    second = ask_ai(m, "k", lambda m: calls.append(2) or AIAnswer(text="b"))
    host.finish()

    assert (first, second) == (True, False) and calls == [1]


def test_two_threads_pressing_at_once_claim_the_key_only_once():
    m, host = api()
    started, barrier = [], threading.Barrier(8)

    def press():
        barrier.wait()
        started.append(ask_ai(m, "k", lambda m: AIAnswer(text="a")))

    threads = [threading.Thread(target=press) for _ in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]

    assert started.count(True) == 1 and len(host.jobs) == 1


def test_different_keys_run_independently_and_a_finished_key_can_be_asked_again():
    m, host = api()

    ask_ai(m, "a", lambda m: AIAnswer(text="one"))
    ask_ai(m, "b", lambda m: AIAnswer(text="two"))
    host.finish()
    assert ask_ai(m, "a", lambda m: AIAnswer(text="three")) is True
    host.finish()

    assert (ai_result(m, "a").text, ai_result(m, "b").text) == ("three", "two")


def test_a_failed_answer_and_a_raising_work_both_end_as_an_error():
    m, host = api()

    ask_ai(m, "failed", lambda m: AIAnswer(error="no connection"))
    ask_ai(m, "raised", lambda m: 1 / 0)
    host.finish()

    assert ai_result(m, "failed") == AIResult("error", error="no connection")
    assert ai_result(m, "raised").status == "error" and "division" in ai_result(m, "raised").error


def test_work_can_hand_back_more_than_text_through_value():
    m, host = api()

    ask_ai(m, "run:1", lambda m: AIResult("done", "2 jobs", "m1", value=["job-a", "job-b"]))
    host.finish()

    assert ai_result(m, "run:1").value == ["job-a", "job-b"]


def test_the_running_state_carries_who_is_answering():
    m, host = api()
    m.state.set("ai:who", "Local · qwen")

    ask_ai(m, "k", lambda m: AIAnswer(text="a"))

    assert ai_result(m, "k").model == "Local · qwen"


def test_the_button_follows_the_state_and_presses_nothing_while_running():
    m, host = api()

    def work(m):
        return AIAnswer(text="a", model="qwen")

    button = ai_ask_button(m, "k", work, label="✦ Summarize", again_label="✦ Summarize again", running_label="… summarizing with")
    assert button.label == "✦ Summarize"

    button.on_press()
    running = ai_ask_button(m, "k", work, running_label="… summarizing with")
    assert running.label.startswith("… summarizing with") and running.dim
    running.on_press()
    assert len(host.jobs) == 1

    host.finish()
    assert ai_ask_button(m, "k", work, again_label="✦ Summarize again").label == "✦ Summarize again"


def test_the_box_is_empty_while_nothing_is_asked_or_running():
    m, host = api()
    assert ai_answer_box(m, "k") is None

    ask_ai(m, "k", lambda m: AIAnswer(text="a"))
    assert ai_answer_box(m, "k") is None


def test_the_box_shows_the_answer_with_its_model_and_copies_it():
    m, host = api()
    ask_ai(m, "k", lambda m: AIAnswer(text="# Why\n**It** broke\n\n- fix it", model="qwen"))
    host.finish()

    box = ai_answer_box(m, "k", title="✦ Summary")
    shown = labels(box)

    assert "✦ Summary · qwen" in shown and "Why" in shown and "It broke" in shown
    [copy] = [c for c in box.children if hasattr(c, "on_press")]
    copy.on_press()
    assert host.copied == [("# Why\n**It** broke\n\n- fix it", "answer")]


def test_the_box_draws_the_mods_own_value_when_given_a_renderer():
    m, host = api()
    ask_ai(m, "k", lambda m: AIResult("done", "2 jobs", "m1", value=["job-a", "job-b"]))
    host.finish()

    box = ai_answer_box(m, "k", render=lambda value: Box(*[Text(v) for v in value]))
    shown = labels(box)

    assert "job-a" in shown and "job-b" in shown and "2 jobs" not in shown


def test_a_failed_ask_shows_an_error_card_with_a_copy_button():
    m, host = api()
    ask_ai(m, "k", lambda m: AIAnswer(error="no connection"))
    host.finish()

    shown = labels(ai_answer_box(m, "k"))

    assert "Could not ask AI" in shown and "no connection" in shown and "⧉ Copy error" in shown


def test_the_chip_says_who_answers_and_follows_what_the_user_picks():
    m, host = api()
    assert ai_chip(m, "Jira issue summary").label == "⟳ AI routing"

    m.run(lambda: refresh_ai_chip(m))
    host.finish()
    chip = ai_chip(m, "Jira issue summary")
    assert chip.label == "⟳ Local · qwen"

    host.who = "MasOrange LLM · opus"
    chip.on_press()
    [(title, on_done)] = host.configured
    on_done()
    host.finish()

    assert title == "Jira issue summary" and ai_chip(m, "x").label == "⟳ MasOrange LLM · opus"
