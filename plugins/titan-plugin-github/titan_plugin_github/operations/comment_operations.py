"""
Comment Operations

Pure business logic for PR comment and review operations.
No UI dependencies - all functions can be unit tested.
"""

import os
import glob
from typing import Optional, Dict
from titan_cli.core.result import ClientSuccess, ClientError
from ..models.view import UICommentThread
from ..widgets.comment_utils import extract_diff_context


def build_ai_review_context(
    pr_thread: UICommentThread,
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
            "author": main_comment.author_login,
            "date": main_comment.formatted_date[:10],
            "body": main_comment.body
        }
    ]

    # Add all replies to show full conversation
    if pr_thread.replies:
        for reply in pr_thread.replies:
            thread_conversation.append({
                "author": reply.author_login,
                "date": reply.formatted_date[:10],
                "body": reply.body
            })

    return {
        "pr": pr_title,
        "file": main_comment.path or "N/A",
        "line": main_comment.line,
        "diff_hunk": diff_context,
        "thread": thread_conversation
    }


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
    Generate a simple commit message from a PR comment.

    Args:
        comment_body: The comment body text
        comment_author: The comment author username
        comment_path: The file path the comment is on (optional)

    Returns:
        Formatted commit message
    """
    # Simple and direct commit message
    if comment_path:
        # Extract just the filename from the path
        filename = comment_path.split('/')[-1]
        message = f"Fix: {filename}"
    else:
        message = "PR review fix"

    # Add author attribution in body
    message += f"\n\nBy: {comment_author}"

    return message


def build_ai_review_prompt(response_file: str) -> str:
    """
    Build the prompt template for AI review of a PR comment thread.

    Args:
        response_file: Path where the AI should write text responses

    Returns:
        Prompt string with {context} placeholder for the JSON context
    """
    return f"""Review this PR comment thread:

```json
{{context}}
```

## Your Task

1. **First, evaluate if the review comment makes sense:**
   - Is the feedback valid and applicable to the current code?
   - Is the requested change appropriate?
   - Could previous attempts have already addressed this (check the thread conversation)?

2. **Then, based on your evaluation:**
   - **If the comment makes sense**: Make the necessary code changes to address it
   - **If the comment doesn't make sense or is outdated**:
     * DO NOT make code changes
     * Write your explanation/response EXACTLY to this file path: {response_file}
     * IMPORTANT: Use this exact command to write the response:
       ```bash
       cat > {response_file} << 'EOF'
       Your response text here
       EOF
       ```

## Response Style (CRITICAL)
- **Keep responses SHORT and CONCISE** (maximum 2-3 sentences)
- **Be direct and to the point** - no verbose explanations
- **Avoid multiple paragraphs** - use a single short paragraph
- **Don't over-explain** - state the key point clearly and move on
- Example GOOD: "This is intentional. The logic handles X at layer Y, ensuring Z."
- Example BAD: Long multi-paragraph explanations with bullet points and detailed justifications

Note: Review the entire conversation thread carefully - previous fix attempts may have failed or been incomplete.

## When You're Done
Once you have completed your single action (code fix OR written the response file), tell the user:
"Done. Press Ctrl+C twice to exit and return to Titan." """


def prepare_replies_for_sending(
    pending_responses: Dict[int, Dict],
    comment_commits: Dict[int, str],
    push_successful: bool
) -> Dict[int, str]:
    """
    Prepare all replies for batch sending.

    Combines text responses and commit replies based on push success.
    If push failed, commit replies are excluded.

    Args:
        pending_responses: Dict mapping comment_id -> {"text": ..., "source": ...}
        comment_commits: Dict mapping comment_id -> commit_hash
        push_successful: Whether commits were successfully pushed

    Returns:
        Dict mapping comment_id -> reply_text ready to send
    """
    replies_to_send = {}

    # Add text responses (always send these)
    for comment_id, response_data in pending_responses.items():
        if isinstance(response_data, dict):
            replies_to_send[comment_id] = response_data["text"]
        else:
            # Backward compatibility: if it's still a string
            replies_to_send[comment_id] = response_data

    # Add commit replies ONLY if push succeeded
    if push_successful and comment_commits:
        for comment_id, commit_hash in comment_commits.items():
            short_hash = commit_hash[:8]
            if comment_id in replies_to_send:
                # Has text reply too — combine: hash first, then text
                replies_to_send[comment_id] = f"{short_hash}\n\n{replies_to_send[comment_id]}"
            else:
                replies_to_send[comment_id] = short_hash

    return replies_to_send


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
        result = github_client.reply_to_comment(pr_number, comment_id, response_text)

        # Handle ClientResult
        match result:
            case ClientSuccess():
                results[comment_id] = True
            case ClientError():
                results[comment_id] = False
            case _:
                results[comment_id] = False

    return results
