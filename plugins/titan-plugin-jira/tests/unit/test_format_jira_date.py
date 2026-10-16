from titan_plugin_jira.models.formatting import extract_text_from_adf, format_jira_date


def test_epoch_milliseconds_are_formatted_in_utc():
    assert format_jira_date("1582152559000") == "19/02/2020 22:49:19"


def test_iso_dates_and_unknowns_are_unchanged():
    assert format_jira_date("2025-01-15T10:30:45.000+0000") == "15/01/2025 10:30:45"
    assert format_jira_date(None) == "Unknown"
    assert format_jira_date("not a date") == "Unknown"
    assert format_jira_date("9" * 30) == "Unknown"


def test_adf_date_nodes_render_their_date():
    doc = {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "date", "attrs": {"timestamp": "1582152559000"}}]}]}
    assert "19/02/2020" in extract_text_from_adf(doc)
