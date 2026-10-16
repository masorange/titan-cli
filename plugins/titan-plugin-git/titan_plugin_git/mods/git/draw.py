"""The pane's element tree, drawn from `m.state` only: it never waits on the network."""
from typing import Optional

from titan_cli.core.mods import Box, Button, Text
from titan_plugin_git.models.formatting import split_squash_pr_suffix

from .models import Repo


def section(title, color: str, *body):
    return Box(title if isinstance(title, Text) else Text(title, bold=True, color=color), *body, border=color)


def commit_line(c) -> Text:
    """A commit by the PR it landed (squash merges) or its hash, its subject without the "(#N)" and its age."""
    subject = split_squash_pr_suffix(c.message_subject)[0]
    return Text("  ", Text(f"#{c.pr_number}", bold=True, color="info") if c.pr_number else Text(c.short_hash, dim=True),
                f" {subject}", Text(f" · {c.formatted_date}", dim=True))


def draw(m, width: int, options=None):
    repo: Optional[Repo] = m.state.get("repo")
    if repo is None:
        return Text("Loading…", dim=True)

    commits_open = m.state.get("commits_open", False)
    head = Text(
        Text(f"⎇ {repo.branch}", bold=True, color="info"),
        repo.has_upstream and Text(f" ↑{repo.ahead}", color="success" if repo.ahead else "subtle"),
        repo.has_upstream and Text(f" ↓{repo.behind}", color="warning" if repo.behind else "subtle"),
        not repo.has_upstream and Text(" no upstream", dim=True),
        repo.added and Text(f" +{repo.added}", color="success"),
        repo.removed and Text(f" −{repo.removed}", color="error"),
    )
    first = repo.commits[0] if repo.commits else None
    label = f"▾ Last {len(repo.commits)} commits" if commits_open else (
        first and f"▸ {f'#{first.pr_number}' if first.pr_number else first.short_hash} {split_squash_pr_suffix(first.message_subject)[0]}"
    )
    return section(
        head,
        "info",
        repo.error and Text(repo.error, color="error"),
        not repo.commits and Text("No commits", dim=True),
        first and Button(label, lambda: m.state.set("commits_open", not commits_open), dim=True),
        commits_open and Box(*[commit_line(c) for c in repo.commits]),
    )
