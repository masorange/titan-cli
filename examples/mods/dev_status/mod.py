"""
dev_status: a side pane with the git branch, the harness focus, review
requests, your PRs and the merge queue.

A port of a Claude Code mod of the same name. Data comes from the git and
github plugin clients on background timers; drawing reads only `m.state`, so
it never waits on the network.
"""
import json
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

from titan_cli.core.mods import Box, Button, Text
from titan_cli.core.result import ClientError, ClientSuccess

PANE = "dev-status"
TITLE = "Dev status"
UNTRACKED_READ_LIMIT = 100
GROUP_SHOWN = 12
UP_NEXT = ("planned", "pending", "not-started")
NOT_COUNTED = ("superseded", "deferred", "discarded")


# -- what the pane shows ---------------------------------------------------


@dataclass(frozen=True)
class Commit:
    hash: str
    subject: str
    pr: Optional[int]
    age: str


@dataclass(frozen=True)
class Feature:
    id: str
    name: str
    status: str


@dataclass(frozen=True)
class Harness:
    name: str
    status: str
    done: int
    total: int
    in_progress: List[Feature]
    up_next: List[Feature]
    other_active: List[str]


@dataclass(frozen=True)
class Repo:
    branch: str
    has_upstream: bool = False
    ahead: int = 0
    behind: int = 0
    added: int = 0
    removed: int = 0
    commits: List[Commit] = field(default_factory=list)
    harness: Optional[Harness] = None
    error: Optional[str] = None


@dataclass(frozen=True)
class Pr:
    number: int
    title: str
    author: str
    is_draft: bool
    review: str  # "approved", "changes requested", "review required", "ready for review"
    checks: str  # "failing", "running", "passing" or "none"
    failing: int
    has_conflicts: bool
    failed_checks: Tuple[Tuple[str, str], ...] = ()  # (name, url) of each failed check


@dataclass(frozen=True)
class Prs:
    repo: str = ""
    to_review: List[Pr] = field(default_factory=list)
    mine: List[Pr] = field(default_factory=list)
    open_count: int = 0
    error: Optional[str] = None


@dataclass(frozen=True)
class QueueEntry:
    position: int
    number: int
    title: str
    author: str
    state_label: str
    state: str
    eta: str
    mine: bool


@dataclass(frozen=True)
class Queue:
    configured: bool = False
    branch: str = ""
    merge_method: str = ""
    total: int = 0
    entries: List[QueueEntry] = field(default_factory=list)
    error: Optional[str] = None


# -- reading -----------------------------------------------------------------


def split_pr(subject: str):
    """Squash merges end their subject with "(#1234)": that is the PR the commit landed."""
    match = re.search(r"\s*\(#(\d+)\)$", subject)
    if not match:
        return subject, None
    return subject[: match.start()], int(match.group(1))


def count_lines(text: str) -> int:
    if text == "":
        return 0
    return text.count("\n") + (0 if text.endswith("\n") else 1)


def untracked_lines(root: Path, files: List[str]) -> int:
    """Lines new files add: they are outside `git diff`, so they are counted by reading them."""
    total = 0
    for name in files[:UNTRACKED_READ_LIMIT]:
        try:
            total += count_lines((root / name).read_text(errors="ignore"))
        except OSError:
            pass
    return total


def read_harness(root: Path, harness_dir: str) -> Optional[Harness]:
    """The focused domain of a root harness (`feature-list.json` with `currentFocus`)."""
    base = root / harness_dir
    try:
        index = json.loads((base / "feature-list.json").read_text())
    except (OSError, ValueError):
        return None
    focus = index.get("currentFocus") or ""
    tasks = index.get("tasks") or []

    def is_focus(task) -> bool:
        path = task.get("path") or ""
        return focus in (task.get("id"), path, path.split("/")[-1])

    task = next((t for t in tasks if is_focus(t)), None)
    if task is None:
        return None
    try:
        domain = json.loads((base / (task.get("path") or focus) / "feature-list.json").read_text())
        features = [
            Feature(f.get("id", "?"), f.get("name", ""), f.get("status", ""))
            for f in domain.get("features") or []
        ]
    except (OSError, ValueError):
        features = []
    return Harness(
        name=task.get("name") or focus,
        status=task.get("status") or "?",
        done=sum(f.status == "done" for f in features),
        total=sum(f.status not in NOT_COUNTED for f in features),
        in_progress=[f for f in features if f.status == "in-progress"],
        up_next=[f for f in features if f.status in UP_NEXT],
        other_active=[t.get("name") or t.get("path") or "?" for t in tasks if t.get("status") == "active" and not is_focus(t)],
    )


def read_repo(git, root: Path, options) -> Repo:
    if git is None:
        return Repo(branch="(no git)", error="git plugin not available")
    match git.get_status():
        case ClientSuccess(data=status):
            pass
        case ClientError(error_message=err):
            return Repo(branch="(no git)", error=err, harness=read_harness(root, options["harness_dir"]))

    added = removed = 0
    match git.get_uncommitted_numstat():
        case ClientSuccess(data=churns):
            added = sum(c.additions for c in churns)
            removed = sum(c.deletions for c in churns)
        case ClientError():
            pass
    # Not status.untracked_files: `git status` collapses a new directory into
    # one entry, and walking it by hand counts what .gitignore excludes.
    match git.get_untracked_files():
        case ClientSuccess(data=untracked):
            added += untracked_lines(root, untracked)
        case ClientError():
            pass

    commits: List[Commit] = []
    match git.get_commits(str(root), limit=options["recent_commits"]):
        case ClientSuccess(data=log):
            for c in log:
                subject, pr = split_pr(c.message_subject)
                commits.append(Commit(c.short_hash, subject, pr, c.formatted_date))
        case ClientError():
            pass

    return Repo(
        branch=status.branch,
        has_upstream=status.has_upstream,
        ahead=status.ahead,
        behind=status.behind,
        added=added,
        removed=removed,
        commits=commits,
        harness=read_harness(root, options["harness_dir"]),
    )


def _pr(ui) -> Pr:
    return Pr(
        number=ui.number,
        title=ui.title,
        author=ui.author_name,
        is_draft=ui.is_draft,
        review=ui.review_status_summary or "",
        checks=ui.checks_state,
        failing=len(ui.failed_checks),
        has_conflicts=ui.has_conflicts,
        failed_checks=tuple((c.name, c.url) for c in ui.failed_checks),
    )


def repo_name(git) -> str:
    if git is None:
        return ""
    match git.get_github_repo_info():
        case ClientSuccess(data=(owner, name)) if owner and name:
            return f"{owner}/{name}"
        case _:
            return ""


def read_prs(github, repo: str = "") -> Prs:
    if github is None:
        return Prs(repo=repo, error="github plugin not available")
    lists = []
    for result in (github.list_pending_review_prs(), github.list_my_prs(), github.list_all_prs(max_results=500)):
        match result:
            case ClientSuccess(data=prs):
                lists.append(prs)
            case ClientError(error_message=err):
                return Prs(repo=repo, error=err)
    to_review, mine, everything = lists
    return Prs(repo=repo, to_review=[_pr(p) for p in to_review], mine=[_pr(p) for p in mine], open_count=len(everything))


def read_queue(github, shown: int) -> Queue:
    if github is None:
        return Queue(error="github plugin not available")
    match github.get_merge_queue(max_entries=shown):
        case ClientSuccess(data=q):
            return Queue(
                configured=q.is_configured,
                branch=q.branch,
                merge_method=q.merge_method,
                total=q.total,
                entries=[
                    QueueEntry(e.position, e.pr_number, e.title, e.author, e.state_label, e.state, e.eta_label, e.is_mine)
                    for e in q.entries
                ],
            )
        case ClientError(error_message=err):
            return Queue(error=err)


def new_review_requests(before: Optional[Prs], after: Prs) -> List[int]:
    """Review requests that arrived since the last good poll, not the ones there at start."""
    if before is None or before.error is not None or after.error is not None:
        return []
    known = {p.number for p in before.to_review}
    return [p.number for p in after.to_review if p.number not in known]


def left_queue(before: Optional[Queue], after: Queue) -> List[int]:
    """My PRs that were queued and no longer are: merged or kicked out, either way news."""
    if before is None or before.error is not None or after.error is not None:
        return []
    still = {e.number for e in after.entries}
    return [e.number for e in before.entries if e.mine and e.number not in still]


# -- failed check diagnosis --------------------------------------------------

LOG_CHARS = 40_000
LOG_TAIL_LINES = 120
FAILURE_LINE = re.compile(
    r"##\[error\]|\bFAILED\b|BUILD FAILED|What went wrong|^e: |\berror:|Exception|AssertionError|> Task .* FAILED|Traceback"
)
TIMESTAMP = re.compile(r"^\d{4}-\d\d-\d\dT[\d:.]+Z ")
JOB_URL = re.compile(r"/actions/runs/\d+/job/(\d+)")

DIAG_SYSTEM = """You read the log of one failed CI job and say why it failed.
Answer with one JSON object and nothing else: {"cause": string, "where": string, "quote": string}.
- cause: one sentence, the most likely reason the job failed, naming the task, test or rule.
- where: "path/File.ext:line" when the log names one, else "".
- quote: ONE line copied character for character from the log that shows the failure, without its timestamp.
Never infer a cause the log does not show. If the log does not make it clear, say so in cause."""


@dataclass(frozen=True)
class JobDiagnosis:
    name: str
    cause: str
    where: str = ""
    quote: str = ""
    is_quote_in_log: bool = False  # a quote that is not in the log was made up


@dataclass(frozen=True)
class Diagnosis:
    status: str  # "running", "done" or "error"
    model: Optional[str] = None
    jobs: Tuple[JobDiagnosis, ...] = ()
    error: Optional[str] = None


def excerpt_of(log: str) -> str:
    """Actions logs run to megabytes: keep the lines that report a failure, with context, and the tail."""
    lines = [TIMESTAMP.sub("", line) for line in log.split("\n")]
    keep = set(range(max(0, len(lines) - LOG_TAIL_LINES), len(lines)))
    for i, line in enumerate(lines):
        if FAILURE_LINE.search(line):
            keep.update(range(max(0, i - 3), min(len(lines), i + 7)))
    text = "\n".join(lines[i] for i in sorted(keep))
    return text[-LOG_CHARS:]


def squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def parse_diagnosis(name: str, answer: str, excerpt: str) -> JobDiagnosis:
    match = re.search(r"\{[\s\S]*\}", answer)
    try:
        parsed = json.loads(match.group(0)) if match else {}
    except ValueError:
        parsed = {}
    quote = str(parsed.get("quote") or "").strip()
    first_line = answer.strip().split("\n")[0] if answer.strip() else ""
    return JobDiagnosis(
        name=name,
        cause=str(parsed.get("cause") or "").strip() or first_line or "No answer",
        where=str(parsed.get("where") or "").strip(),
        quote=quote,
        is_quote_in_log=bool(quote) and squash(quote) in squash(excerpt),
    )


def diagnose_job(m, github, name: str, url: str) -> Tuple[JobDiagnosis, Optional[str]]:
    """The diagnosis of one failed job, and the model that answered."""
    job = JOB_URL.search(url or "")
    if job is None:
        return JobDiagnosis(name, "Not a GitHub Actions job: its log is outside GitHub."), None
    match github.get_actions_job_log(int(job.group(1))):
        case ClientSuccess(data=log):
            pass
        case ClientError(error_message=err):
            raise RuntimeError(err)
    excerpt = excerpt_of(log)
    answer = m.ai.complete(f"Job: {name}\n\nLog excerpt:\n{excerpt}", system=DIAG_SYSTEM, max_tokens=600)
    if not answer.ok:
        raise RuntimeError(f"AI: {answer.error}")
    return parse_diagnosis(name, answer.text, excerpt), answer.model


def diagnose(m, number: int, options) -> None:
    """Explain the failed checks of one of my PRs; runs on a background thread."""
    prs: Optional[Prs] = m.state.get("prs")
    pr = next((p for p in (prs.mine if prs else []) if p.number == number), None)
    if pr is None:
        return
    key = str(number)

    def put(d: Diagnosis) -> None:
        m.state.update("diagnoses", lambda all_: {**(all_ or {}), key: d}, default={})

    put(Diagnosis("running", model=m.state.get("ai_label")))
    github = m.client("github")
    checks = pr.failed_checks[: options["diagnosis_jobs"]]
    try:
        if github is None:
            raise RuntimeError("github plugin not available")
        with ThreadPoolExecutor(max_workers=len(checks) or 1) as pool:
            results = list(pool.map(lambda c: diagnose_job(m, github, c[0], c[1]), checks))
        answered = next((model for _, model in results if model), None)
        put(Diagnosis("done", model=answered, jobs=tuple(job for job, _ in results)))
    except Exception as e:
        put(Diagnosis("error", error=str(e)))


# -- drawing -----------------------------------------------------------------


QUEUE_TONE = {"QUEUED": "subtle", "AWAITING_CHECKS": "warning", "MERGEABLE": "success", "UNMERGEABLE": "error", "LOCKED": "error"}
# A PR with no review decision yet is waiting for one, as GitHub's own lists put it.
REVIEW_LABEL = {"approved": "approved", "changes requested": "changes requested"}
REVIEW_TONE = {"approved": "success", "changes requested": "error"}
CHECKS_LABEL = {"passing": "✓ checks", "failing": "✗ checks", "running": "… checks"}
CHECKS_TONE = {"passing": "success", "failing": "error", "running": "warning"}
FEATURE_MARK = {"in-progress": ("◐", "warning"), "planned": ("○", "subtle"), "pending": ("○", "subtle"), "not-started": ("◇", "info")}


def section(title, color: str, *body):
    return Box(title if isinstance(title, Text) else Text(title, bold=True, color=color), *body, border=color)


def bar(done: int, total: int, width: int) -> Text:
    cells = max(6, min(24, width - 10))
    filled = 0 if total == 0 else round(done / total * cells)
    return Text(Text("█" * filled, color="success"), Text("░" * (cells - filled), color="subtle"), Text(f" {done}/{total}", dim=True))


def diagnosis_of(m, pr: Pr, options) -> Box:
    d: Optional[Diagnosis] = (m.state.get("diagnoses") or {}).get(str(pr.number))
    running = d is not None and d.status == "running"
    if running:
        label = f"… diagnosing with {d.model or 'AI routing'}"
    elif d is not None and d.status == "done":
        label = f"✦ Diagnose again (last: {d.model or 'AI routing'})"
    else:
        label = "✦ Diagnose failure"

    def press():
        if not running:
            m.run(lambda: diagnose(m, pr.number, options))

    done = d is not None and d.status == "done"
    return Box(
        Button(label, press, dim=not running),
        d is not None and d.status == "error" and Text(f"Could not diagnose: {d.error}", color="error"),
        done and [
            Box(
                Text(" "),
                Text(f"✗ {j.name}", color="error"),
                Text(j.cause, wrap=True),
                j.where and Text(f"  at {j.where}", color="info"),
                j.quote and Text(f"“{j.quote}”", dim=True, wrap=True),
                j.quote and not j.is_quote_in_log and Text("  ⚠ this line is not in the log: do not trust the cause", color="warning"),
            )
            for j in d.jobs
        ],
        done and len(pr.failed_checks) > len(d.jobs) and Text(f"…and {len(pr.failed_checks) - len(d.jobs)} more failed checks", dim=True),
        indent=3,
    )


def pr_row(pr: Pr, is_mine: bool, queued: dict, m=None, options=None) -> Box:
    entry = queued.get(pr.number)
    review = (
        Text("○ draft", dim=True)
        if pr.is_draft
        else Text(f"● {REVIEW_LABEL.get(pr.review, 'awaiting review')}", color=REVIEW_TONE.get(pr.review, "warning"))
    )
    return Box(
        Text(" "),
        Text(Text(f"#{pr.number}", bold=True, color="info"), " ", pr.title),
        Text(
            not is_mine and Text(f"@{pr.author} · ", dim=True),
            review,
            pr.checks in CHECKS_LABEL and Text(
                f"  {CHECKS_LABEL[pr.checks]}" + (f" ({pr.failing})" if pr.failing else ""), color=CHECKS_TONE[pr.checks]
            ),
            pr.has_conflicts and Text("  ⚠ conflicts", color="error"),
        ),
        entry and Text(f"   ⇢ in merge queue #{entry.position}" + (f" · {entry.eta}" if entry.eta else ""), color="info"),
        # Fixing a red check is the author's job, so only my own PRs get a diagnosis.
        is_mine and pr.checks == "failing" and m is not None and diagnosis_of(m, pr, options),
    )


def refresh_ai_label(m) -> None:
    """Who answers a diagnosis now; resolving may probe, so it runs off the UI thread."""
    m.state.set("ai_choices", m.ai.choices())
    m.state.set("ai_pinned", m.ai.pinned())
    m.state.set("ai_label", m.ai.describe())


def model_picker(m, options):
    """
    Cycles the task "mods.dev_status" through: AI routing's default, then every
    connection and headless CLI this machine has. A pick is a task pin in the
    user config, the same one the AI routing screen writes.
    """
    choices = m.state.get("ai_choices") or []
    pinned = m.state.get("ai_pinned")
    label = m.state.get("ai_label") or "…"
    cycle = [None] + [c.key for c in choices]

    def press():
        nxt = cycle[(cycle.index(pinned) + 1) % len(cycle)] if pinned in cycle else (cycle[1] if len(cycle) > 1 else None)
        m.ai.pin(nxt)
        m.state.set("ai_pinned", nxt)
        m.run(lambda: refresh_ai_label(m))

    how = "pinned for this panel" if pinned else "Titan's AI default"
    return Box(
        Text("✦ Diagnosis AI", dim=True),
        Button(f"  ⟳ {label}", press),
        Text(f"    {how} · Enter/click to change", dim=True),
    )


def fold(m, key: str, label: str, default_open: bool, *body):
    """A pressable title that shows its body only while open; remembers what the person chose."""
    chosen = m.state.get(key)
    is_open = default_open if chosen is None else chosen
    return Box(
        Button(f"{'▾' if is_open else '▸'} {label}", lambda: m.state.set(key, not is_open), dim=True),
        is_open and Box(*body, indent=2),
    )


def feature_row(f: Feature) -> Text:
    glyph, tone = FEATURE_MARK.get(f.status, ("·", "subtle"))
    return Text(Text(f"{glyph} {f.id}", color=tone), " ", f.name)


def group(m, key: str, title: str, features: List[Feature], default_open: bool):
    return fold(
        m, key, f"{title} ({len(features)})", default_open,
        [feature_row(f) for f in features[:GROUP_SHOWN]],
        len(features) > GROUP_SHOWN and Text(f"…and {len(features) - GROUP_SHOWN} more", dim=True),
    )


def queue_row(e: QueueEntry) -> Box:
    return Box(
        Text(" "),
        Text(Text(f"{e.position}. ", dim=True), Text(f"#{e.number}", bold=True, color="accent" if e.mine else "info"), f" {e.title}"),
        Text("   ", Text(f"@{e.author} · ", dim=True), Text(f"● {e.state_label}", color=QUEUE_TONE.get(e.state, "subtle")),
             e.eta and Text(f" · {e.eta}", bold=True)),
    )


def draw(m, width: int, options=None):
    options = options or {"diagnosis_jobs": 3}
    repo: Optional[Repo] = m.state.get("repo")
    prs: Optional[Prs] = m.state.get("prs")
    queue: Optional[Queue] = m.state.get("queue")
    if repo is None and prs is None:
        return Text("Loading…", dim=True)

    parts = []
    if repo is not None:
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
        label = f"▾ Last {len(repo.commits)} commits" if commits_open else (first and f"▸ {f'#{first.pr}' if first.pr else first.hash} {first.subject}")
        parts.append(
            section(
                head,
                "info",
                repo.error and Text(repo.error, color="error"),
                not repo.commits and Text("No commits", dim=True),
                first and Button(label, lambda: m.state.set("commits_open", not commits_open), dim=True),
                commits_open and Box(*[
                    Text("  ", Text(f"#{c.pr}", bold=True, color="info") if c.pr else Text(c.hash, dim=True), f" {c.subject}", Text(f" · {c.age}", dim=True))
                    for c in repo.commits
                ]),
            )
        )

        hs = repo.harness
        if hs is not None:
            idle = not hs.in_progress
            parts.append(
                section(
                    Text(Text(f"◆ {hs.name}", bold=True, color="accent"), Text(f" {hs.status}", dim=True)),
                    "accent",
                    bar(hs.done, hs.total, width),
                    hs.in_progress and group(m, "in_progress_open", "In progress", hs.in_progress, False),
                    hs.up_next and group(m, "up_next_open", "Up next" if idle else "Pending", hs.up_next, idle),
                    idle and not hs.up_next and Text("✓ Nothing left to do", color="success"),
                    hs.other_active and Text(f"Also active: {', '.join(hs.other_active)}", dim=True, wrap=True),
                )
            )

    queued = {e.number: e for e in (queue.entries if queue else [])}
    if prs is None:
        parts.append(Text("Loading PRs…", dim=True))
    else:
        has_queue = queue is not None and queue.configured
        tone = "error" if prs.error else "warning" if prs.to_review else "info"
        title = Text(
            Text("⇄ Pull requests", bold=True, color=tone),
            not prs.error and Text(f" {prs.repo + ' · ' if prs.repo else ''}{prs.open_count} open", dim=True),
        )
        if prs.error:
            parts.append(section(title, tone, Text(f"Could not read PRs: {prs.error}", dim=True)))
        else:
            parts.append(section(title, tone, Box(
                # Empty groups start closed; each one keeps what the person last chose.
                fold(m, "review_open", f"Needs your review ({len(prs.to_review)})", bool(prs.to_review),
                     not prs.to_review and Text("Nothing pending", dim=True),
                     [pr_row(p, False, queued) for p in prs.to_review]),
                fold(m, "mine_open", f"Your PRs ({len(prs.mine)})", bool(prs.mine),
                     not prs.mine and Text("No open PRs", dim=True),
                     [pr_row(p, True, queued, m, options) for p in prs.mine]),
                has_queue and fold(
                    m, "queue_open",
                    f"Merge queue · {queue.branch} ({queue.total})" + (f" · {queue.merge_method}" if queue.merge_method else ""),
                    bool(queue.entries),
                    queue.error and Text(queue.error, color="error"),
                    not queue.error and queue.total == 0 and Text("Queue empty", dim=True),
                    [queue_row(e) for e in queue.entries],
                    queue.total > len(queue.entries) and Text(f"…and {queue.total - len(queue.entries)} more", dim=True),
                ),
                model_picker(m, options),
                gap=1,
            )))
    return Box(*parts)


# -- wiring ------------------------------------------------------------------


def register(on, options):
    where = {}

    def refresh_repo(m):
        m.state.set("repo", read_repo(m.client("git"), where["root"], options))

    def refresh_prs(m):
        before = m.state.get("prs")
        after = read_prs(m.client("github"), repo_name(m.client("git")))
        m.state.set("prs", after)
        arrived = new_review_requests(before, after)
        if arrived:
            m.ui.toast("Review requested: " + ", ".join(f"#{n}" for n in arrived))

    def refresh_queue(m):
        before = m.state.get("queue")
        after = read_queue(m.client("github"), options["queue_shown"])
        m.state.set("queue", after)
        left = left_queue(before, after)
        if left:
            m.ui.toast("Left the merge queue: " + ", ".join(f"#{n}" for n in left))

    @on("app.start")
    def start(m, e, next):
        where["root"] = Path(e.project_root)
        m.ui.open(PANE, TITLE)
        m.clock.every(options["repo_refresh_seconds"], lambda: refresh_repo(m))
        m.clock.every(options["prs_refresh_seconds"], lambda: refresh_prs(m))
        m.clock.every(options["queue_refresh_seconds"], lambda: refresh_queue(m))
        m.run(lambda: refresh_ai_label(m))
        return next(e)

    # Workflows are what change the tree, so refresh right after one ends.
    @on("workflow.run")
    def after_workflow(m, e, next):
        result = next(e)
        if not e.nested and "root" in where:
            try:
                refresh_repo(m)
            except Exception:
                m.log.warning("dev_status_refresh_failed", exc_info=True)
        return result

    @on("ui.render", match={"component": "Pane", "pane": PANE})
    def render(m, e, next):
        return draw(m, e.width, options)
