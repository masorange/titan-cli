"""
Scope Operations

Pure logic for the scope a PR title carries (`type(scope): Description`), taken from
the rules the repository's own labeler already applies to the files of the PR.

A repository that lints its titles against its labels (every label the labeler puts
on the PR must appear in the title scope) has one right answer for the scope: run the
labeler's rules over the PR's files. These functions do that without touching the
network, git or the filesystem; callers hand them the labeler text and the file list.
"""

import re
from dataclasses import dataclass
from typing import Optional

import yaml

# What a title's first line looks like: `type: Desc`, `type(a,b)!: Desc`.
_TITLE = re.compile(r"^(?P<type>[A-Za-z]+)(?:\([^)]*\))?(?P<breaking>!)?:\s*(?P<desc>\S.*)$")

# A PR title is asked to stay within this many characters, scope not included.
TITLE_BASE_LIMIT = 72

# Top-level options of the labeler config; they sit beside the labels but are not labels.
_LABELER_OPTIONS = ("changed-files-labels-limit", "max-files-changed")


class UnsupportedGlob(ValueError):
    """The glob uses minimatch syntax that `glob_to_regex` does not translate."""


@dataclass(frozen=True)
class TitleScopes:
    """
    What the title scope policy came to for one PR.

    `enabled` is False when the policy could not be applied (labeler missing, files
    unreadable): the title is then left exactly as the model wrote it. When enabled
    with no `scopes`, no label matched and the title carries no scope.
    """

    enabled: bool = False
    scopes: tuple = ()
    separator: str = ","
    warnings: tuple = ()


def glob_to_regex(glob: str) -> re.Pattern:
    """
    Translate a minimatch glob the way `actions/labeler` runs it (`dot: true`).

    `*` and `?` stay inside a path segment, `**` crosses folders and `**/` matches zero
    or more of them. Dotfiles match. Classes, braces, extglobs, escapes and negation are
    not translated and raise `UnsupportedGlob`, because guessing them would put a wrong
    scope in a title.

    Args:
        glob: One glob from the labeler config

    Returns:
        A pattern to use with `fullmatch` against a repo-relative path
    """
    if glob.startswith(("!", "#")) or any(c in glob for c in "[]{}()\\"):
        raise UnsupportedGlob(glob)

    segments = glob.split("/")
    regex = []
    for i, segment in enumerate(segments):
        is_last = i == len(segments) - 1
        if segment == "**":
            regex.append(".*" if is_last else "(?:.*/)?")
        else:
            regex.append(_segment_to_regex(segment) + ("" if is_last else "/"))
    return re.compile("".join(regex), re.DOTALL)


def _segment_to_regex(segment: str) -> str:
    out = []
    for char in segment:
        if char == "*":
            if not out or out[-1] != "[^/]*":
                out.append("[^/]*")
        elif char == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(char))
    return "".join(out)


def parse_labeler_rules(text: str) -> tuple:
    """
    Read a labeler config into `{label: [patterns]}` (file order) plus warnings.

    Only `changed-files` with a single `any-glob-to-any-file` is understood. Any other
    matcher is skipped with a warning; its label stays in the result, possibly with no
    patterns, so the caller still knows the labeler manages it.

    Args:
        text: Contents of the labeler config (`.github/labeler.yml`)

    Returns:
        (rules, warnings)
    """
    try:
        data = yaml.safe_load(text) or {}
    except yaml.YAMLError as e:
        return {}, [f"The labeler config is not valid YAML ({e})."]
    if not isinstance(data, dict):
        return {}, ["The labeler config is not a mapping of label to matchers."]

    rules: dict = {}
    warnings: list = []
    for key, entries in data.items():
        # YAML reads `2.0:` or `1:` as numbers; the labeler sees every key as a name
        label = str(key)
        if label in _LABELER_OPTIONS:
            warnings.append(
                f"The labeler sets '{label}', which Titan does not apply, "
                "so CI may apply fewer labels than the title scope shows."
            )
            continue
        rules[label] = []
        if not isinstance(entries, list):
            warnings.append(f"Labeler rule '{label}' is not a list of matchers, skipped.")
            continue
        for entry in entries:
            for glob in _supported_globs(label, entry, warnings):
                try:
                    rules[label].append(glob_to_regex(glob))
                except UnsupportedGlob:
                    warnings.append(f"Labeler rule '{label}' uses the unsupported glob '{glob}', skipped.")
    return rules, warnings


def _supported_globs(label: str, entry, warnings: list) -> list:
    changed_files = entry.get("changed-files") if isinstance(entry, dict) and len(entry) == 1 else None
    if not isinstance(changed_files, list):
        warnings.append(f"Labeler rule '{label}' has a matcher other than changed-files, skipped.")
        return []

    # Several match objects in one `changed-files` are ANDed by the labeler; refuse
    # rather than approximate.
    if (
        len(changed_files) != 1
        or not isinstance(changed_files[0], dict)
        or set(changed_files[0]) != {"any-glob-to-any-file"}
    ):
        warnings.append(f"Labeler rule '{label}' uses a match type other than a single any-glob-to-any-file, skipped.")
        return []

    globs = changed_files[0]["any-glob-to-any-file"]
    if isinstance(globs, str):
        return [globs]
    if isinstance(globs, list) and all(isinstance(glob, str) for glob in globs):
        return globs

    # `any-glob-to-any-file:` with no value, a number or a nested list parse as YAML but are no glob
    warnings.append(f"Labeler rule '{label}' has an any-glob-to-any-file that is not a glob or a list of globs, skipped.")
    return []


def match_labels(rules: dict, files: list) -> list:
    """
    The labels the labeler would apply to `files`.

    Args:
        rules: Output of `parse_labeler_rules`
        files: Repo-relative paths changed by the PR

    Returns:
        Matching labels in labeler config order
    """
    return [
        label
        for label, patterns in rules.items()
        if any(pattern.fullmatch(path) for pattern in patterns for path in files)
    ]


def compute_title_scopes(labeler_text: str, files: list) -> tuple:
    """
    The title scopes for a PR: the labels its files earn under the labeler config.

    Args:
        labeler_text: Contents of the labeler config
        files: Repo-relative paths changed by the PR

    Returns:
        (scopes, warnings), scopes in labeler config order
    """
    rules, warnings = parse_labeler_rules(labeler_text)
    return match_labels(rules, files), warnings


def scope_text(scopes, separator: str = ",") -> str:
    """`(a,b)` for the scopes, or "" when there are none."""
    return f"({separator.join(scopes)})" if scopes else ""


def title_length_limit(scopes, separator: str = ",", base: int = TITLE_BASE_LIMIT) -> int:
    """
    How long a title may be once it carries `scopes`.

    The scope is not part of what the title says, so it does not eat into the room the
    description has: the limit grows by the length of `(scope)`.
    """
    return base + len(scope_text(scopes, separator))


def apply_title_scopes(title: str, scopes, separator: str = ",") -> Optional[str]:
    """
    Rewrite a title so its scope is exactly `scopes`.

    Whatever scope the title already had is replaced (none when `scopes` is empty), and
    the breaking-change marker and the description are kept.

    Args:
        title: A title such as `feat: Add x` or `feat(api)!: Add x`
        scopes: The scopes it must carry
        separator: What joins several scopes

    Returns:
        The rewritten title, or None when the title has no `type:` prefix to attach a
        scope to
    """
    match = _TITLE.match(title.strip())
    if not match:
        return None
    return f"{match['type']}{scope_text(scopes, separator)}{match['breaking'] or ''}: {match['desc']}"


_DIFF_HEADER = re.compile(r'(?m)^diff --git "?a/.+?"? "?b/(?P<path>.+?)"?$')


def changed_paths_from_diff(diff: str) -> list:
    """
    The paths a unified diff changes, one per file, in diff order.

    A renamed file counts under its new name, which is the one the labeler sees on the
    PR. Taken from the diff the prompt is built from, so the scope and what the model
    reads describe the same change, with no cap on how many files there are.

    Args:
        diff: A unified diff with `diff --git` headers

    Returns:
        Repo-relative paths; empty when the diff has no headers
    """
    return list(dict.fromkeys(m["path"] for m in _DIFF_HEADER.finditer(diff or "")))


def build_title_scopes(
    labeler_text: Optional[str],
    diff: str,
    separator: str = ",",
    labeler_path: str = ".github/labeler.yml",
) -> TitleScopes:
    """
    The scope policy for one PR under the `labeler` source.

    Args:
        labeler_text: Contents of the labeler config, or None when the file is not there
        diff: The branch diff of the PR
        separator: What joins several scopes
        labeler_path: Where the config was looked for, to name it in a warning

    Returns:
        A policy; not enabled (title left as written) when there is no labeler config
    """
    if labeler_text is None:
        return TitleScopes(
            separator=separator,
            warnings=(f"Labeler config '{labeler_path}' was not found, so the title has no scope.",),
        )
    scopes, warnings = compute_title_scopes(labeler_text, changed_paths_from_diff(diff))
    return TitleScopes(enabled=True, scopes=tuple(scopes), separator=separator, warnings=tuple(warnings))


def enforce_title_scopes(title: str, policy: TitleScopes) -> tuple:
    """
    Make a generated title carry exactly the scope the policy came to.

    The model is told which scope to write, but the title is only right when the code
    says so: whatever scope it wrote is replaced, so one it invented never reaches a
    linter that only knows the repository's own.

    Args:
        title: The title as the model wrote it
        policy: The scope policy computed for this PR

    Returns:
        (title, warnings): the title to show, and what the reader should know about it
    """
    warnings = list(policy.warnings)
    if not policy.enabled:
        return title, warnings

    if not policy.scopes:
        warnings.append("No labeler rule matches the files of this PR, so the title has no scope.")

    rewritten = apply_title_scopes(title, policy.scopes, policy.separator)
    if rewritten is None:
        warnings.append("The title has no 'type:' prefix, so its scope could not be set.")
    else:
        title = rewritten
    return title, warnings


def build_title_instruction(scopes=(), separator: str = ",") -> str:
    """
    The title rule of the PR prompt: with the scope the PR earned, or without any.

    Without scopes it is the rule a PR prompt has always carried, so a repository that
    does not use scopes is prompted exactly as before.

    Args:
        scopes: The scopes the title must carry; empty for none
        separator: What joins several scopes

    Returns:
        The numbered instruction, starting at `1. **Title**:`
    """
    if not scopes:
        return (
            "1. **Title**: Follow conventional commits format WITHOUT scope (type: Description), be clear and descriptive\n"
            "   - Format: `type: Description` (NO scope, NO parentheses)\n"
            f"   - **HARD LIMIT: title MUST be ≤{TITLE_BASE_LIMIT} characters total** (count carefully before writing)\n"
            "   - Start description with CAPITAL letter (imperative mood)\n"
            "   - **If <project_context> contains issue IDs** (e.g., jira_issues, issue_ids, tickets), include them in the title BEFORE the description:\n"
            "     * Format: `type: ISSUE-1, ISSUE-2 Description`\n"
            "     * Example: `feat: PROJ-1234, PROJ-5678 Add OAuth2 integration`\n"
            '   - Examples without issues: "feat: Add user auth flow", "fix: Resolve cache race condition"\n'
            '   - NEVER use format like "feat(scope): Description" - always use "feat: Description"'
        )

    scope = separator.join(scopes)
    limit = title_length_limit(scopes, separator)
    return (
        "1. **Title**: Follow conventional commits format WITH the scope given below "
        "(type(scope): Description), be clear and descriptive\n"
        f"   - Format: `type({scope}): Description` - use exactly this scope, character for character; "
        "do not add, drop, reorder or rename any part of it\n"
        f"   - **HARD LIMIT: title MUST be ≤{limit} characters total, scope included** (count carefully before writing)\n"
        "   - Start description with CAPITAL letter (imperative mood)\n"
        "   - **If <project_context> contains issue IDs** (e.g., jira_issues, issue_ids, tickets), include them in the title BEFORE the description:\n"
        f"     * Format: `type({scope}): ISSUE-1, ISSUE-2 Description`\n"
        f"     * Example: `feat({scope}): PROJ-1234, PROJ-5678 Add OAuth2 integration`\n"
        f'   - Examples without issues: "feat({scope}): Add user auth flow", "fix({scope}): Resolve cache race condition"'
    )
