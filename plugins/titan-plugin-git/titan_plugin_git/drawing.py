"""Pieces of drawing shared inside the git plugin: a graph row's lanes, a commit's title line and the bordered card the sections use."""
from titan_cli.ui.elements import Box, Text
from titan_plugin_git.models.formatting import split_squash_pr_suffix

# One colour per lane, cycled: what makes a branch followable down the rows.
LANE_COLORS = ("info", "success", "warning", "error", "accent", "primary")


def lane_glyphs(row, width: int) -> Text:
    """A row's lanes, each in its own colour, padded so every subject starts at the same column."""
    cells = list(row.cells) + [" "] * (width - len(row.cells))
    return Text(*[
        Text(cell, color=LANE_COLORS[j % len(LANE_COLORS)], bold=(j == row.lane))
        for j, cell in enumerate(cells)
    ])


def commit_title(c) -> Text:
    """A commit by the PR it landed (squash merges) or its hash, its subject without the "(#N)" and its age."""
    subject = split_squash_pr_suffix(c.message_subject)[0]
    return Text(
        Text(f"#{c.pr_number}", bold=True, color="info") if c.pr_number else Text(c.short_hash, dim=True),
        [Text(f" {ref}", color="accent") for ref in c.refs[:2]],
        f" {subject}",
    )


def section(title, color: str, *body):
    return Box(title if isinstance(title, Text) else Text(title, bold=True, color=color), *body, border=color)
