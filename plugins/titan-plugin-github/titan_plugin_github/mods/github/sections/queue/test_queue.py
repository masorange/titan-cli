"""Reading the merge queue."""
from titan_plugin_github.models.view import UIMergeQueueEntry


def test_left_queue_only_reports_my_prs_after_a_good_poll(mod):
    def entry(number, mine):
        return UIMergeQueueEntry(1, number, "t", "a", "QUEUED", "queued", None, "", mine)

    before = mod.models.Queue(configured=True, entries=[entry(7, True), entry(8, False)])
    after = mod.models.Queue(configured=True, entries=[])
    assert mod.sections.queue.queue.left_queue(before, after) == [7]
    assert mod.sections.queue.queue.left_queue(before, mod.models.Queue(error="down")) == []
