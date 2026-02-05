#!/usr/bin/env python3
"""
Generate release notes from conventional commits.

Usage:
    python scripts/generate_release_notes.py [--version VERSION] [--from-tag TAG]
"""

import argparse
import re
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Commit:
    """Represents a parsed commit."""
    hash: str
    type: str
    scope: Optional[str]
    breaking: bool
    message: str
    body: str
    full_message: str


def get_version() -> str:
    """Get current version from pyproject.toml."""
    result = subprocess.run(
        ["poetry", "version", "-s"],
        capture_output=True,
        text=True,
        check=True
    )
    return result.stdout.strip()


def get_last_tag() -> Optional[str]:
    """Get the last git tag."""
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0", "HEAD^"],
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def get_commits_since(since_tag: Optional[str] = None) -> List[str]:
    """Get commits since a specific tag or all commits."""
    if since_tag:
        range_spec = f"{since_tag}..HEAD"
    else:
        range_spec = "HEAD"

    result = subprocess.run(
        ["git", "log", "--pretty=format:%H|||%s|||%b", range_spec],
        capture_output=True,
        text=True,
        check=True
    )

    return [c for c in result.stdout.split("\n") if c.strip()]


def parse_commit(commit_line: str) -> Optional[Commit]:
    """
    Parse a conventional commit message.

    Format: type(scope): message
    Examples:
        feat(ui): add new button
        fix: resolve crash on startup
        feat!: breaking change
        refactor(core)!: major refactor
    """
    parts = commit_line.split("|||")
    if len(parts) < 2:
        return None

    commit_hash = parts[0]
    subject = parts[1]
    body = parts[2] if len(parts) > 2 else ""

    # Conventional commit pattern
    pattern = r'^(\w+)(\(([^)]+)\))?(!)?:\s*(.+)$'
    match = re.match(pattern, subject)

    if not match:
        # Not a conventional commit, categorize as "other"
        return Commit(
            hash=commit_hash[:7],
            type="other",
            scope=None,
            breaking=False,
            message=subject,
            body=body,
            full_message=subject
        )

    commit_type = match.group(1)
    scope = match.group(3)
    breaking = match.group(4) == "!" or "BREAKING CHANGE" in body
    message = match.group(5)

    return Commit(
        hash=commit_hash[:7],
        type=commit_type,
        scope=scope,
        breaking=breaking,
        message=message,
        body=body,
        full_message=subject
    )


def group_commits(commits: List[Commit]) -> dict:
    """Group commits by type."""
    groups = defaultdict(list)

    for commit in commits:
        if commit.breaking:
            groups["breaking"].append(commit)
        else:
            groups[commit.type].append(commit)

    return dict(groups)


def format_commit(commit: Commit) -> str:
    """Format a commit for release notes."""
    scope_str = f"**{commit.scope}**: " if commit.scope else ""
    return f"- {scope_str}{commit.message} ([`{commit.hash}`](https://github.com/masmovil/titan-cli/commit/{commit.hash}))"


def generate_release_notes(version: str, from_tag: Optional[str] = None) -> str:
    """Generate release notes for a version."""

    # Get commits
    commit_lines = get_commits_since(from_tag)
    commits = [parse_commit(c) for c in commit_lines]
    commits = [c for c in commits if c is not None]

    # Group commits
    grouped = group_commits(commits)

    # Build release notes
    lines = [
        f"# Titan CLI v{version}",
        "",
    ]

    # Breaking changes first (if any)
    if "breaking" in grouped:
        lines.extend([
            "## ⚠️ Breaking Changes",
            "",
        ])
        for commit in grouped["breaking"]:
            lines.append(format_commit(commit))
        lines.append("")

    # Features
    if "feat" in grouped:
        lines.extend([
            "## ✨ Features",
            "",
        ])
        for commit in grouped["feat"]:
            lines.append(format_commit(commit))
        lines.append("")

    # Bug fixes
    if "fix" in grouped:
        lines.extend([
            "## 🐛 Bug Fixes",
            "",
        ])
        for commit in grouped["fix"]:
            lines.append(format_commit(commit))
        lines.append("")

    # Refactoring
    if "refactor" in grouped:
        lines.extend([
            "## 🔧 Refactoring",
            "",
        ])
        for commit in grouped["refactor"]:
            lines.append(format_commit(commit))
        lines.append("")

    # Documentation
    if "docs" in grouped:
        lines.extend([
            "## 📚 Documentation",
            "",
        ])
        for commit in grouped["docs"]:
            lines.append(format_commit(commit))
        lines.append("")

    # Performance
    if "perf" in grouped:
        lines.extend([
            "## ⚡ Performance",
            "",
        ])
        for commit in grouped["perf"]:
            lines.append(format_commit(commit))
        lines.append("")

    # Chores
    if "chore" in grouped:
        lines.extend([
            "## 🏗️ Chores",
            "",
        ])
        for commit in grouped["chore"]:
            lines.append(format_commit(commit))
        lines.append("")

    # Installation section
    lines.extend([
        "## 📦 Installation",
        "",
        "```bash",
        "# Recommended: Install with pipx",
        f"pipx install titan-cli=={version}",
        "",
        "# Verify installation",
        "titan --version",
        "```",
        "",
    ])

    # Built-in plugins
    lines.extend([
        "## 🔌 Built-in Plugins",
        "",
        "This release includes three core plugins:",
        "- **Git Plugin** - Smart commits, branch management, AI-powered messages",
        "- **GitHub Plugin** - Create PRs with AI descriptions, manage issues",
        "- **JIRA Plugin** - Search issues, AI-powered analysis",
        "",
    ])

    # Full changelog link
    if from_tag:
        lines.extend([
            "## 📝 Full Changelog",
            "",
            f"**Compare**: [{from_tag}...{version}](https://github.com/masmovil/titan-cli/compare/{from_tag}...{version})",
            "",
        ])

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Generate release notes from conventional commits")
    parser.add_argument("--version", help="Version to release (default: from pyproject.toml)")
    parser.add_argument("--from-tag", help="Generate notes from this tag (default: last tag)")
    parser.add_argument("--output", help="Output file (default: stdout)")

    args = parser.parse_args()

    # Get version
    version = args.version or get_version()

    # Get starting tag
    from_tag = args.from_tag or get_last_tag()

    if from_tag:
        print(f"Generating release notes v{version} (changes since {from_tag})...", flush=True)
    else:
        print(f"Generating release notes v{version} (all commits)...", flush=True)

    # Generate release notes
    notes = generate_release_notes(version, from_tag)

    # Output
    if args.output:
        with open(args.output, "w") as f:
            f.write(notes)
        print(f"Release notes written to {args.output}")
    else:
        print("\n" + "="*80 + "\n")
        print(notes)


if __name__ == "__main__":
    main()
