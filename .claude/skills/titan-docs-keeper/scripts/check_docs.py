"""Mechanical checks for Titan's documentation layers. Read-only.

Run from anywhere: python3 -I .claude/skills/titan-docs-keeper/scripts/check_docs.py
Exit code 1 when any ERROR is found; WARN never fails.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT_BUDGET = 140
PLUGIN_BUDGET = 45
GUIDE_BUDGET = 600
SKILL_BUDGET = 130
AGENT_BUDGET = 110
KNOWN_COMMANDS = {"titan-dev"}

LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
BACKTICK_PATH = re.compile(r"`((?:\.claude|docs|plugins|titan_cli|harness)/[\w./\-<>*]+)`")
HARNESS_ID = re.compile(r"\b(?:D|F|FEAT)-\d{2,}\b")
SHARED_WORDS = 9  # consecutive words two files must share before it is worth a look

findings: list[tuple[str, str, str]] = []


def add(level: str, where: str, msg: str) -> None:
    findings.append((level, where, msg))


def repo_root() -> Path:
    out = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True
    )
    return Path(out.stdout.strip()) if out.returncode == 0 else Path.cwd()


def lines_of(p: Path) -> list[str]:
    return p.read_text(encoding="utf-8").splitlines()


def check_links(root: Path, f: Path) -> None:
    in_fence = False
    for n, line in enumerate(lines_of(f), 1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for target in LINK.findall(line):
            if re.match(r"^(https?:|mailto:|#)", target):
                continue
            path = target.split("#")[0]
            if path and not (f.parent / path).resolve().exists():
                add("ERROR", f"{f.relative_to(root)}:{n}", f"dead link {target}")
        for p in BACKTICK_PATH.findall(line):
            if any(c in p for c in "<>*"):
                continue
            if not (root / p.rstrip("/")).exists():
                add("WARN", f"{f.relative_to(root)}:{n}", f"path not found `{p}`")


def shared_passages(root: Path, files: list[Path]) -> None:
    """WARN when two files carry the same run of words: a likely second copy of a fact.

    Approximate on purpose (tables, code and links are stripped; wording that differs is not
    caught), so it only warns; the judgment is the audit checklist's.
    """
    seen: dict[tuple[str, ...], tuple[str, int]] = {}
    reported: set[tuple[str, str]] = set()
    for f in files:
        rel, in_fence = str(f.relative_to(root)), False
        for n, line in enumerate(lines_of(f), 1):
            if line.lstrip().startswith("```"):
                in_fence = not in_fence
                continue
            text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", line)
            if in_fence or line.lstrip().startswith("|") or len(text.split()) < SHARED_WORDS:
                continue
            words = re.sub(r"[`*_]", "", text).lower().split()
            for i in range(len(words) - SHARED_WORDS + 1):
                key = tuple(words[i:i + SHARED_WORDS])
                other = seen.setdefault(key, (rel, n))
                if other[0] != rel and (other[0], rel) not in reported:
                    reported.add((other[0], rel))
                    add("WARN", f"{rel}:{n}", f"same passage as {other[0]}:{other[1]} - keep it in one home, link the other")


def main() -> int:
    root = repo_root()
    agents = root / "AGENTS.md"
    guides = sorted((root / ".claude/docs").glob("*.md"))
    skills = sorted(p.parent for p in (root / ".claude/skills").glob("*/SKILL.md"))
    agent_defs = sorted((root / ".claude/agents").glob("*.md"))
    plugin_agents = sorted(root.glob("plugins/*/AGENTS.md"))

    if not agents.exists():
        print("ERROR AGENTS.md missing")
        return 1
    root_text = agents.read_text(encoding="utf-8")

    n = len(lines_of(agents))
    if n > ROOT_BUDGET:
        add("WARN", "AGENTS.md", f"{n} lines, budget {ROOT_BUDGET}: move depth to .claude/docs")

    for g in guides:
        rel = g.relative_to(root)
        if f".claude/docs/{g.name}" not in root_text:
            add("ERROR", str(rel), "not in the root AGENTS.md Guides table")
        size = len(lines_of(g))
        if size > GUIDE_BUDGET:
            add("WARN", str(rel), f"{size} lines, budget {GUIDE_BUDGET}: split by task")
    for m in re.findall(r"\(\.claude/docs/([\w\-]+\.md)\)", root_text):
        if not (root / ".claude/docs" / m).exists():
            add("ERROR", "AGENTS.md", f"Guides row points at missing {m}")

    for s in skills:
        if f"`{s.name}`" not in root_text:
            add("ERROR", f".claude/skills/{s.name}", "not in the root AGENTS.md skill routing")
        size = len(lines_of(s / "SKILL.md"))
        if size > SKILL_BUDGET:
            add("WARN", f".claude/skills/{s.name}/SKILL.md", f"{size} lines, budget {SKILL_BUDGET}")
        head = (s / "SKILL.md").read_text(encoding="utf-8")
        if not re.search(rf"^name:\s*{re.escape(s.name)}\s*$", head, re.M):
            add("ERROR", f".claude/skills/{s.name}/SKILL.md", "frontmatter name != folder name")
        if not re.search(r"^description:\s*\S", head, re.M):
            add("ERROR", f".claude/skills/{s.name}/SKILL.md", "missing description")
    for m in re.findall(r"`(titan-[\w\-]+)`", root_text):
        if m in KNOWN_COMMANDS:
            continue
        if (
            not (root / ".claude/skills" / m).exists()
            and not (root / ".claude/agents" / f"{m}.md").exists()
            and not (root / ".titan/workflows" / f"{m}.yaml").exists()
        ):
            add("WARN", "AGENTS.md", f"`{m}` is neither a skill nor an agent")

    for a in agent_defs:
        size = len(lines_of(a))
        if size > AGENT_BUDGET:
            add("WARN", str(a.relative_to(root)), f"{size} lines, budget {AGENT_BUDGET}")

    for pa in plugin_agents:
        rel = str(pa.relative_to(root))
        size = len(lines_of(pa))
        if size > PLUGIN_BUDGET:
            add("WARN", rel, f"{size} lines, budget {PLUGIN_BUDGET}: repo-wide rules belong in root")
        if "AGENTS.md" not in pa.read_text(encoding="utf-8").split("## ")[0]:
            add("WARN", rel, "does not link to the root AGENTS.md in its intro")

    scanned = [agents, *guides, *plugin_agents, *agent_defs]
    for s in skills:
        scanned += [p for p in s.rglob("*.md")]
    for f in scanned:
        check_links(root, f)
        for i, line in enumerate(lines_of(f), 1):
            if HARNESS_ID.search(line):
                add("WARN", f"{f.relative_to(root)}:{i}", "harness/feature ID cited in docs")

    # Plugin AGENTS.md files share an intro template on purpose.
    shared_passages(root, [f for f in scanned if f not in plugin_agents])

    order = {"ERROR": 0, "WARN": 1}
    for level, where, msg in sorted(findings, key=lambda x: (order[x[0]], x[1])):
        print(f"{level:5} {where} - {msg}")
    errors = sum(1 for f in findings if f[0] == "ERROR")
    print(f"\n{errors} error(s), {len(findings) - errors} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
