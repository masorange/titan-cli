from titan_plugin_slack.block_formatting import SlackBlockFormatter


class TestBuilders:
    def test_section(self) -> None:
        assert SlackBlockFormatter.section("Hello *world*") == {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "Hello *world*"},
        }

    def test_header(self) -> None:
        assert SlackBlockFormatter.header("Release 0.7.0") == {
            "type": "header",
            "text": {"type": "plain_text", "text": "Release 0.7.0"},
        }

    def test_divider(self) -> None:
        assert SlackBlockFormatter.divider() == {"type": "divider"}

    def test_context(self) -> None:
        assert SlackBlockFormatter.context("Posted by titan-cli") == {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": "Posted by titan-cli"}],
        }

    def test_fields_caps_at_ten(self) -> None:
        block = SlackBlockFormatter.fields([f"Field {i}" for i in range(12)])
        assert block["type"] == "section"
        assert len(block["fields"]) == 10
        assert block["fields"][0] == {"type": "mrkdwn", "text": "Field 0"}


class TestToBlocks:
    def test_paragraph_becomes_section(self) -> None:
        blocks = SlackBlockFormatter.to_blocks("Just a plain paragraph.")
        assert blocks == [SlackBlockFormatter.section("Just a plain paragraph.")]

    def test_multiline_paragraph_stays_one_section(self) -> None:
        blocks = SlackBlockFormatter.to_blocks("Line one\nLine two")
        assert blocks == [SlackBlockFormatter.section("Line one\nLine two")]

    def test_h1_becomes_header_block(self) -> None:
        blocks = SlackBlockFormatter.to_blocks("# Release 0.7.0")
        assert blocks == [SlackBlockFormatter.header("Release 0.7.0")]

    def test_h2_becomes_header_block(self) -> None:
        blocks = SlackBlockFormatter.to_blocks("## Highlights")
        assert blocks == [SlackBlockFormatter.header("Highlights")]

    def test_deep_heading_falls_back_to_bold_section(self) -> None:
        blocks = SlackBlockFormatter.to_blocks("#### Details")
        assert blocks == [SlackBlockFormatter.section("*Details*")]

    def test_heading_with_emphasis_strips_markup_for_header_block(self) -> None:
        blocks = SlackBlockFormatter.to_blocks("# Release **0.7.0**")
        assert blocks == [SlackBlockFormatter.header("Release 0.7.0")]

    def test_bullet_list_becomes_one_section(self) -> None:
        blocks = SlackBlockFormatter.to_blocks("- First item\n- Second item")
        assert blocks == [SlackBlockFormatter.section("• First item\n• Second item")]

    def test_horizontal_rule_becomes_divider(self) -> None:
        blocks = SlackBlockFormatter.to_blocks("Before\n\n---\n\nAfter")
        assert blocks == [
            SlackBlockFormatter.section("Before"),
            SlackBlockFormatter.divider(),
            SlackBlockFormatter.section("After"),
        ]

    def test_fenced_code_block_becomes_its_own_section_untouched(self) -> None:
        blocks = SlackBlockFormatter.to_blocks('Before\n```python\n**not bold**\n```\nAfter')
        assert blocks == [
            SlackBlockFormatter.section("Before"),
            SlackBlockFormatter.section("```python\n**not bold**\n```"),
            SlackBlockFormatter.section("After"),
        ]

    def test_table_becomes_its_own_section_as_fenced_grid(self) -> None:
        markdown = "| Name | Version |\n| --- | --- |\n| titan-cli | 0.7.0 |"
        blocks = SlackBlockFormatter.to_blocks(markdown)
        assert len(blocks) == 1
        text = blocks[0]["text"]["text"]
        assert text.startswith("```\n") and text.endswith("\n```")
        assert "Name" in text and "titan-cli" in text

    def test_paragraph_before_and_after_table_are_separate_sections(self) -> None:
        markdown = (
            "Intro paragraph.\n\n"
            "| Name | Version |\n| --- | --- |\n| titan-cli | 0.7.0 |\n\n"
            "Outro paragraph."
        )
        blocks = SlackBlockFormatter.to_blocks(markdown)
        assert len(blocks) == 3
        assert blocks[0] == SlackBlockFormatter.section("Intro paragraph.")
        assert blocks[2] == SlackBlockFormatter.section("Outro paragraph.")

    def test_full_document_produces_expected_block_sequence(self) -> None:
        markdown = "# Release 0.7.0\n\nBody text.\n\n- Item one\n- Item two\n\n---\n\nDone."
        blocks = SlackBlockFormatter.to_blocks(markdown)
        assert [block["type"] for block in blocks] == [
            "header",
            "section",
            "section",
            "divider",
            "section",
        ]

    def test_oversized_paragraph_is_split_into_multiple_sections(self) -> None:
        long_line = "x" * 4000
        blocks = SlackBlockFormatter.to_blocks(long_line)
        assert len(blocks) == 2
        assert all(len(block["text"]["text"]) <= 3000 for block in blocks)
        assert "".join(block["text"]["text"] for block in blocks) == long_line
