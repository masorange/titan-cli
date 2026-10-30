"""Reading the merge queue."""
from titan_plugin_github.readers import models
from titan_plugin_github.readers import queue as queue_reader
from titan_plugin_github.models.view import UIMergeQueueEntry


def test_left_queue_only_reports_my_prs_after_a_good_poll(mod):
    def entry(number, mine):
        return UIMergeQueueEntry(1, number, "t", "a", "QUEUED", "queued", None, "", mine)

    before = models.Queue(configured=True, entries=[entry(7, True), entry(8, False)])
    after = models.Queue(configured=True, entries=[])
    assert queue_reader.left_queue(before, after) == [7]
    assert queue_reader.left_queue(before, models.Queue(error="down")) == []
