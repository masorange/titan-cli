"""
Comment Operations

Pure business logic for PR comment and review operations.
No UI dependencies - all functions can be unit tested.
"""

import os
import glob
from typing import Optional, Set, Tuple, Dict
from ..models.network.graphql import GraphQLPullRequestReviewThread
from ..widgets.comment_utils import extract_diff_context


def build_ai_review_context(
    pr_thread: GraphQLPullRequestReviewThread,
    pr_title: str
) -> dict:
    """
    Build structured JSON context for AI review.

    Extracts only relevant diff lines (7 before + target + 3 after) to minimize tokens.

    Args:
        pr_thread: The PR review thread to process
        pr_title: The PR title

    Returns:
        Dictionary with structured context for AI:
        {
            "pr": str,
            "file": str,
            "line": int,
            "diff_hunk": str (acotado),
            "thread": [{"author": str, "date": str, "body": str}, ...]
        }

    Example:
        >>> context = build_ai_review_context(pr_thread, "feat: Add feature")
        >>> context['pr']
        'feat: Add feature'
        >>> len(context['diff_hunk'].split('\\n'))
        11  # ~11 lines instead of 200+
    """
    main_comment = pr_thread.main_comment

    # Extract only relevant lines from diff_hunk (7 before + target + 3 after)
    # This reduces token usage significantly (e.g., 200 lines → ~11 lines)
    diff_context = extract_diff_context(
        diff_hunk=main_comment.diff_hunk,
        target_line=main_comment.line,
        is_outdated=False
    ) if main_comment.diff_hunk else None

    # Build thread conversation
    thread_conversation = [
        {
            "author": main_comment.author.login,
            "date": main_comment.created_at[:10],
            "body": main_comment.body
        }
    ]

    # Add all replies to show full conversation
    if pr_thread.replies:
        for reply in pr_thread.replies:
            thread_conversation.append({
                "author": reply.author.login,
                "date": reply.created_at[:10],
                "body": reply.body
            })

    return {
        "pr": pr_title,
        "file": main_comment.path or "N/A",
        "line": main_comment.line,
        "diff_hunk": diff_context,
        "thread": thread_conversation
    }


def detect_worktree_changes(
    git_status_before: str,
    git_status_after: str
) -> Tuple[bool, Set[str]]:
    """
    Compare git status before/after to detect new changes.

    This is used to determine if AI made code changes vs just writing a text response.

    Args:
        git_status_before: Output of `git status --short` before operation
        git_status_after: Output of `git status --short` after operation

    Returns:
        Tuple of (has_new_changes: bool, new_changed_files: Set[str])

    Example:
        >>> before = "M file1.txt"
        >>> after = "M file1.txt\\nM file2.txt"
        >>> has_changes, files = detect_worktree_changes(before, after)
        >>> has_changes
        True
        >>> files
        {'M file2.txt'}
    """
    files_before = set(line.strip() for line in git_status_before.splitlines() if line.strip())
    files_after = set(line.strip() for line in git_status_after.splitlines() if line.strip())

    new_changes = files_after - files_before
    has_new_changes = bool(new_changes)

    return has_new_changes, new_changes


def find_ai_response_file(comment_id: int, expected_path: str) -> Optional[str]:
    """
    Search for AI response file in expected and fallback locations.

    Different AI CLIs (Gemini, Claude) write to different temp directories.
    This function searches common locations to find the response file.

    Args:
        comment_id: The comment ID (used in filename)
        expected_path: The expected file path (e.g., /tmp/titan-ai-response-comment-{id}.txt)

    Returns:
        Path to the found file, or None if not found

    Example:
        >>> path = find_ai_response_file(123, "/tmp/titan-ai-response-comment-123.txt")
        >>> path
        '/home/user/.gemini/tmp/.../titan-ai-response-comment-123.txt'
    """
    # Try expected location first
    if os.path.exists(expected_path):
        return expected_path

    # Search in common AI CLI temp directories
    filename = os.path.basename(expected_path)
    search_patterns = [
        f"/tmp/**/{filename}",
        os.path.expanduser(f"~/.gemini/tmp/**/{filename}"),
        os.path.expanduser(f"~/.claude/tmp/**/{filename}"),
    ]

    for pattern in search_patterns:
        matches = glob.glob(pattern, recursive=True)
        if matches:
            return matches[0]

    return None


def create_commit_message(comment_body: str, comment_author: str, comment_path: Optional[str]) -> str:
    """
    Generate a descriptive commit message from a PR comment.

    Args:
        comment_body: The comment body text
        comment_author: The comment author username
        comment_path: The file path the comment is on (optional)

    Returns:
        Formatted commit message

    Example:
        >>> msg = create_commit_message("Fix the bug", "reviewer", "src/main.py")
        >>> msg
        'Fix PR comment: Fix the bug\\n\\nComment by reviewer on src/main.py'
    """
    # Truncate comment to 80 chars and remove newlines
    comment_summary = comment_body[:80].replace('\n', ' ')

    # Build commit message
    message = f"Fix PR comment: {comment_summary}\n\n"
    message += f"Comment by {comment_author}"

    if comment_path:
        message += f" on {comment_path}"

    return message


def reply_to_comment_batch(
    github_client,
    pr_number: int,
    replies: Dict[int, str]
) -> Dict[int, bool]:
    """
    Reply to multiple PR comments in batch.

    Args:
        github_client: GitHub client instance
        pr_number: PR number
        replies: Dictionary mapping comment_id -> response_text

    Returns:
        Dictionary mapping comment_id -> success (bool)

    Example:
        >>> replies = {123: "Fixed", 456: "Done"}
        >>> results = reply_to_comment_batch(github, 789, replies)
        >>> results
        {123: True, 456: True}
    """
    results = {}

    for comment_id, response_text in replies.items():
        try:
            github_client.reply_to_comment(pr_number, comment_id, response_text)
            results[comment_id] = True
        except Exception:
            results[comment_id] = False

    return results


def auto_review_comment(
    github_client,
    git_client,
    pr_thread: GraphQLPullRequestReviewThread,
    worktree_path: str,
    pr_title: str,
    response_file_path: str,
    ai_executor_func
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Automatically review a PR comment using AI.

    The AI can either:
    1. Make code changes (returns commit hash)
    2. Write a text response (returns response text)

    Args:
        github_client: GitHub client
        git_client: Git client
        pr_thread: PR review thread to process
        worktree_path: Path to worktree
        pr_title: PR title
        response_file_path: Path where AI should write text responses
        ai_executor_func: Function that executes AI (receives context dict)

    Returns:
        Tuple of (has_code_changes, commit_hash_or_none, response_text_or_none)

    Example:
        >>> has_changes, commit_hash, response = auto_review_comment(
        ...     github, git, thread, "/tmp/worktree", "feat: Add X",
        ...     "/tmp/response.txt", lambda ctx: ai.execute(ctx)
        ... )
        >>> if has_changes:
        ...     print(f"Committed: {commit_hash}")
        >>> else:
        ...     print(f"Response: {response}")
    """
    main_comment = pr_thread.main_comment

    # Build AI context
    review_context = build_ai_review_context(pr_thread, pr_title)

    # Take snapshot before AI executes
    status_before = git_client.run_in_worktree(worktree_path, ["git", "status", "--short"])

    # Execute AI (caller provides the executor function)
    ai_executor_func(review_context, response_file_path)

    # Take snapshot after
    status_after = git_client.run_in_worktree(worktree_path, ["git", "status", "--short"])

    # Detect changes
    has_new_changes, changed_files = detect_worktree_changes(status_before, status_after)

    if has_new_changes:
        # AI made code changes - commit them
        commit_msg = create_commit_message(
            main_comment.body,
            main_comment.author.login,
            main_comment.path
        )

        # Import here to avoid circular dependency
        from .worktree_operations import commit_in_worktree

        commit_hash = commit_in_worktree(
            git_client,
            worktree_path,
            commit_msg,
            add_all=True,
            no_verify=True
        )

        return (True, commit_hash, None)
    else:
        # No code changes - check for text response
        response_path = find_ai_response_file(main_comment.id, response_file_path)

        if response_path:
            try:
                with open(response_path, 'r') as f:
                    ai_response = f.read().strip()
                return (False, None, ai_response)
            except Exception:
                return (False, None, None)
        else:
            return (False, None, None)
