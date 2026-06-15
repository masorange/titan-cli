"""Pure operations for formatting Slack messages for AI summaries."""

from __future__ import annotations

from datetime import datetime, timezone

from ..models import UISlackMessage


def format_messages_as_transcript(
    messages: list[UISlackMessage],
    *,
    target_name: str | None = None,
) -> str:
    """Format Slack messages as a compact transcript for downstream AI steps."""
    lines: list[str] = []
    if target_name:
        lines.append(f"Target: {target_name}")
        lines.append("")

    for message in messages:
        lines.append(
            f"[{_format_slack_timestamp(message.ts)}] {message.user or 'Unknown'}: {message.text.strip()}"
        )
    return "\n".join(lines).strip()


def truncate_transcript_for_summary(transcript: str, max_chars: int = 12000) -> str:
    """Truncate a transcript conservatively before sending it to AI."""
    if len(transcript) <= max_chars:
        return transcript
    marker = "[Transcript truncated]"
    if max_chars <= len(marker):
        return marker[:max_chars]
    prefix = transcript[: max_chars - len(marker) - 2].rstrip()
    return f"{prefix}\n\n{marker}"


def build_summary_prompt(target_name: str | None, transcript: str) -> str:
    """Build a reusable Slack summary prompt from transcript content."""
    target_label = target_name or "the selected Slack conversation"
    return (
        f"Summarize the latest activity in {target_label}.\n\n"
        "Focus on:\n"
        "1. Main topics or decisions\n"
        "2. Action items and owners when visible\n"
        "3. Open questions or blockers\n"
        "4. Any notable links, incidents, or follow-up context\n\n"
        "Keep the summary concise but useful for someone who did not read the thread.\n\n"
        "Transcript:\n"
        f"{transcript}"
    )


def _format_slack_timestamp(ts: str) -> str:
    """Render a Slack timestamp into a stable UTC label for transcript output."""
    try:
        timestamp = float(ts)
    except (TypeError, ValueError):
        return ts or "unknown-ts"
    dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
