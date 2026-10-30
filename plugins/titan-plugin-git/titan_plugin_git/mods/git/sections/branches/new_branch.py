"""
Starting a branch from the one you are on: the name, where the AI's suggestion
comes from, and the checkout itself.

Reading the repository's conventions, writing the prompt and judging a name are
the git plugin's (`branch_operations`); this file runs them with the mod's AI
routing, the git client and - when the repo has the github plugin - its pull
request labels, and keeps what the card draws in `m.state`.
"""
from typing import List, Optional

from titan_cli.core.result import ClientError, ClientSuccess
from titan_plugin_git.operations import (
    branch_name_prefixes,
    build_branch_name_prompt,
    normalize_branch_name,
    parse_suggested_branch_name,
    validate_branch_name,
)

# What the fold keeps in state, all under the branch it was opened from.
PREFIXES = 6   # how many of the repository's branch prefixes the model is shown
LABELS = 20    # how many pull request labels go with them

NAME = "new_branch_name"
STATUS = "new_branch_status"  # "suggesting", "creating" or None
ERROR = "new_branch_error"
AI_ERROR_PREFIX = "AI: "  # an error that starts with it came from the model, not from git or the name


def menu_key(branch: str) -> str:
    """Where the branch's choice card keeps which of its dropdowns is open."""
    return f"branch_menu:{branch}"


def reset(m) -> None:
    """The fold was opened: a new name starts from nothing."""
    m.state.set(NAME, "")
    m.state.set(ERROR, None)
    m.state.set(STATUS, None)


def set_name(m, value: str) -> None:
    """What the field holds. Typing clears the last complaint: it was about the old name."""
    m.state.set(NAME, value)
    m.state.set(ERROR, None)


def repo_branches(git) -> List[str]:
    """
    Every branch name git knows, local and remote, without its remote:
    "origin/feat/login" counts as "feat/login", so the prefix read from it is
    the branch's own and not the remote's.
    """
    names: List[str] = []
    for remote in (False, True):
        match git.get_branches(remote=remote):
            case ClientSuccess(data=branches):
                names.extend(
                    b.name.split("/", 1)[1] if b.is_remote and "/" in b.name else b.name
                    for b in branches
                )
    return names


def pr_labels(m, limit: int) -> List[str]:
    """
    The repository's pull request labels, as a second hint at how this team
    classifies work. Empty when the github plugin is not here or says no: the
    suggestion is worth having without them.
    """
    if limit <= 0:
        return []
    github = m.client("github")
    if github is None:
        return []
    match github.list_labels():
        case ClientSuccess(data=labels):
            return list(labels)[:limit]
    return []


def start(m, kind: str, fn) -> None:
    """
    Claim the fold for `kind` and run `fn` on a background thread.

    The button's state is from the last repaint, so two quick presses both saw
    the fold idle: claiming in state here closes that window, and the claim is
    what the card draws its progress line from.
    """
    claimed = []

    def claim(current):
        if current:
            return current
        claimed.append(True)
        return kind

    m.state.update(STATUS, claim)
    if claimed:
        m.run(fn)


def suggest(m, options) -> None:
    """Ask for a name from the press; the reading and the model call go off the UI thread."""
    start(m, "suggesting", lambda: run_suggest(m, options))


def run_suggest(m, options) -> None:
    """
    Name the uncommitted work: its diff, under this repository's branch prefixes
    and pull request labels, read by the AI the user routed this mod to.

    The answer only fills the field - nothing is created until the user presses
    for it, so a bad suggestion costs an edit, never a branch.
    """
    git = m.client("git")
    try:
        if git is None:
            m.state.set(ERROR, "git plugin not available")
            return

        summary, excerpt = uncommitted_work(git, options["suggestion_diff_chars"])
        if not summary and not excerpt:
            m.state.set(ERROR, "nothing uncommitted to name a branch after")
            return

        prefixes = branch_name_prefixes(repo_branches(git), limit=PREFIXES)
        prompt, system = build_branch_name_prompt(summary, excerpt, prefixes, pr_labels(m, LABELS))
        answer = m.ai.complete(prompt, system=system, max_tokens=60)
        if not answer.ok:
            m.state.set(ERROR, f"{AI_ERROR_PREFIX}{answer.error}")
            return

        name = parse_suggested_branch_name(answer.text)
        if not name:
            m.state.set(ERROR, "the model answered with no name")
            return
        m.state.set(NAME, name)
    finally:
        m.state.set(STATUS, None)


def uncommitted_work(git, diff_chars: int):
    """What is not committed yet: the files, and as much of the diff as is worth sending."""
    summary = ""
    match git.get_uncommitted_diff_stat():
        case ClientSuccess(data=stat):
            summary = stat or ""
    match git.get_untracked_files():
        case ClientSuccess(data=files) if files:
            summary = "\n".join([summary.strip(), *(f"{path} (new file)" for path in files)]).strip()

    excerpt = ""
    match git.get_uncommitted_diff():
        case ClientSuccess(data=diff):
            excerpt = (diff or "")[:diff_chars]
    return summary, excerpt


def create(m, source: str, options) -> None:
    """
    Branch off `source` once the name holds up, carrying the uncommitted work over.

    The name is judged here, before git is asked, so the reason appears under
    the field instead of as a toast about a command the user never typed.
    """
    git = m.client("git")
    name = normalize_branch_name(m.state.get(NAME) or "")
    if name != (m.state.get(NAME) or ""):
        m.state.set(NAME, name)  # what will be created is what the field shows

    known = [b.name for b in (m.state.get("branches").items if m.state.get("branches") else [])]
    reason = validate_branch_name(name, known)
    if reason:
        m.state.set(ERROR, reason)
        return
    if git is None:
        m.state.set(ERROR, "git plugin not available")
        return

    start(m, "creating", lambda: run_create(m, name, source))


def run_create(m, name: str, source: str) -> None:
    """Create `name` at `source` and switch to it; the card is redrawn from what git says next."""
    git = m.client("git")
    try:
        match git.create_and_switch_branch(name, source):
            case ClientSuccess():
                m.state.set(menu_key(source), None)
                m.state.set(NAME, "")
                m.ui.toast(f"Created {name} from {source}", "information")
            case ClientError(error_message=err):
                m.state.set(ERROR, err)
    finally:
        m.state.set(STATUS, None)
        refresh = m.state.get("refresh")
        if refresh:
            refresh()


def status(m) -> Optional[str]:
    """What the fold is doing, `"suggesting"`, `"creating"` or None."""
    return m.state.get(STATUS)
