# plugins/titan-plugin-github/titan_plugin_github/models.py
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

# Import PRSizeEstimation from utils


@dataclass
class User:
    """GitHub user representation"""
    login: str
    name: Optional[str] = None
    email: Optional[str] = None
    avatar_url: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> 'User':
        """
        Create User from API response (REST API)

        Args:
            data: User data from GitHub API

        Returns:
            User instance

        Examples:
            >>> data = {"login": "john", "name": "John Doe"}
            >>> user = User.from_dict(data)
        """
        if not data:
            return cls(login="unknown")

        return cls(
            login=data.get("login", "unknown"),
            name=data.get("name"),
            email=data.get("email"),
            avatar_url=data.get("avatar_url")
        )

    @classmethod
    def from_graphql(cls, data: dict) -> 'User':
        """
        Create User from GraphQL response

        Args:
            data: Actor data from GraphQL

        Returns:
            User instance
        """
        if not data:
            return cls(login="unknown")

        return cls(
            login=data.get("login", "unknown"),
            name=data.get("name"),
            email=data.get("email")
        )


@dataclass
class ReviewComment:
    """GitHub PR review comment"""
    id: int
    path: str
    line: int
    body: str
    user: User
    created_at: str
    side: str = "RIGHT"  # RIGHT or LEFT

    @classmethod
    def from_dict(cls, data: dict) -> 'ReviewComment':
        """Create ReviewComment from API response"""
        return cls(
            id=data.get("id", 0),
            path=data.get("path", ""),
            line=data.get("line", 0),
            body=data.get("body", ""),
            user=User.from_dict(data.get("user", {})),
            created_at=data.get("created_at", ""),
            side=data.get("side", "RIGHT")
        )


@dataclass
class Review:
    """GitHub PR review"""
    id: int
    user: User
    body: str
    state: str  # PENDING, APPROVED, CHANGES_REQUESTED, COMMENTED
    submitted_at: Optional[str] = None
    commit_id: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> 'Review':
        """Create Review from API response"""
        return cls(
            id=data.get("id", 0),
            user=User.from_dict(data.get("user", {})),
            body=data.get("body", ""),
            state=data.get("state", "PENDING"),
            submitted_at=data.get("submitted_at"),
            commit_id=data.get("commit_id")
        )


@dataclass
class PullRequest:
    """
    GitHub Pull Request representation

    Attributes:
        number: PR number
        title: PR title
        body: PR description
        state: open, closed, merged
        author: PR author
        base_ref: Base branch (e.g., develop)
        head_ref: Head branch (e.g., feature/xyz)
        additions: Lines added
        deletions: Lines deleted
        changed_files: Number of files changed
        mergeable: Can be merged
        draft: Is draft PR
        created_at: ISO date string
        updated_at: ISO date string
        merged_at: ISO date string (if merged)
        reviews: List of reviews
        labels: List of label names
    """
    number: int
    title: str
    body: str
    state: str
    author: User
    base_ref: str
    head_ref: str
    additions: int = 0
    deletions: int = 0
    changed_files: int = 0
    mergeable: bool = True
    draft: bool = False
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    merged_at: Optional[str] = None
    reviews: List[Review] = field(default_factory=list)
    labels: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> 'PullRequest':
        """
        Create PullRequest from GitHub API response

        Args:
            data: PR data from GitHub API (gh pr view --json format)

        Returns:
            PullRequest instance

        Examples:
            >>> data = gh_api_response
            >>> pr = PullRequest.from_dict(data)
        """
        # Parse author
        author_data = data.get("author", {})
        author = User.from_dict(author_data)

        # Parse reviews
        reviews_data = data.get("reviews", [])
        reviews = [Review.from_dict(r) for r in reviews_data]

        # Parse labels
        labels_data = data.get("labels", [])
        labels = [label.get("name", "") for label in labels_data]

        return cls(
            number=data.get("number", 0),
            title=data.get("title", ""),
            body=data.get("body", ""),
            state=data.get("state", "OPEN"),
            author=author,
            base_ref=data.get("baseRefName", ""),
            head_ref=data.get("headRefName", ""),
            additions=data.get("additions", 0),
            deletions=data.get("deletions", 0),
            changed_files=data.get("changedFiles", 0),
            mergeable=data.get("mergeable", "MERGEABLE") == "MERGEABLE",
            draft=data.get("isDraft", False),
            created_at=data.get("createdAt"),
            updated_at=data.get("updatedAt"),
            merged_at=data.get("mergedAt"),
            reviews=reviews,
            labels=labels
        )

    def get_status_emoji(self) -> str:
        """Get emoji for PR state"""
        if self.state == "MERGED":
            return "🟣"
        elif self.state == "CLOSED":
            return "🔴"
        elif self.draft:
            return "📝"
        elif self.state == "OPEN":
            return "🟢"
        return "⚪"

    def get_review_status(self) -> str:
        """Get review status summary"""
        if not self.reviews:
            return "No reviews"

        approved = sum(1 for r in self.reviews if r.state == "APPROVED")
        changes = sum(1 for r in self.reviews if r.state == "CHANGES_REQUESTED")

        if approved > 0 and changes == 0:
            return f"✅ {approved} approved"
        elif changes > 0:
            return f"❌ {changes} changes requested"
        else:
            return f"💬 {len(self.reviews)} comments"


@dataclass
class PRSearchResult:
    """Result of searching pull requests"""
    prs: List[PullRequest]
    total: int

    @classmethod
    def from_list(cls, data: List[dict]) -> 'PRSearchResult':
        """
        Create PRSearchResult from list of PR data

        Args:
            data: List of PR dictionaries from GitHub API

        Returns:
            PRSearchResult instance
        """
        prs = [PullRequest.from_dict(pr_data) for pr_data in data]
        return cls(prs=prs, total=len(prs))


@dataclass
class PRReviewComment:
    """
    Individual review comment on code (GraphQL: PullRequestReviewComment).

    Faithful representation of GitHub's GraphQL PullRequestReviewComment object.
    See: https://docs.github.com/en/graphql/reference/objects#pullrequestreviewcomment

    Attributes:
        id: Comment database ID (databaseId in GraphQL)
        body: Comment text content
        author: User who created the comment
        created_at: Creation timestamp (ISO 8601)
        updated_at: Last update timestamp (ISO 8601)
        path: File path being commented on
        position: Position in the diff (None if outdated)
        line: Line number in the new version of the file (None if outdated)
        original_line: Line number in the original version before changes
        diff_hunk: Diff context snippet showing the commented code
        reply_to: Parent comment if this is a reply (for threading)
    """
    id: int
    body: str
    author: User
    created_at: str
    updated_at: str
    path: Optional[str] = None
    position: Optional[int] = None
    line: Optional[int] = None
    original_line: Optional[int] = None
    diff_hunk: Optional[str] = None
    reply_to: Optional['PRReviewComment'] = None

    @classmethod
    def from_graphql(cls, data: Dict[str, Any]) -> 'PRReviewComment':
        """
        Create PRReviewComment from GraphQL response.

        Args:
            data: Comment node from GraphQL PullRequestReviewComment

        Returns:
            PRReviewComment instance
        """
        author_data = data.get("author", {})
        author = User.from_graphql(author_data)

        # Handle replyTo for threading
        reply_to_data = data.get("replyTo")
        reply_to = None
        if reply_to_data:
            reply_to = cls.from_graphql(reply_to_data)

        return cls(
            id=data.get("databaseId", 0),
            body=data.get("body", ""),
            author=author,
            created_at=data.get("createdAt", ""),
            updated_at=data.get("updatedAt", ""),
            path=data.get("path"),
            position=data.get("position"),
            line=data.get("line"),
            original_line=data.get("originalLine"),
            diff_hunk=data.get("diffHunk"),
            reply_to=reply_to
        )


@dataclass
class PRReviewThread:
    """
    Review thread containing a main comment and its replies (GraphQL: PullRequestReviewThread).

    Faithful representation of GitHub's GraphQL PullRequestReviewThread object.
    See: https://docs.github.com/en/graphql/reference/objects#pullrequestreviewthread

    Attributes:
        id: Thread node ID (for resolving/unresolving)
        is_resolved: Whether the thread has been marked as resolved
        is_outdated: Whether the code has changed since this comment was made
        path: File path where the thread is located
        comments: List of comments [main_comment, reply1, reply2, ...]
    """
    id: str
    is_resolved: bool
    is_outdated: bool
    path: Optional[str]
    comments: List[PRReviewComment]

    @property
    def main_comment(self) -> Optional[PRReviewComment]:
        """Get the main comment that started this thread."""
        return self.comments[0] if self.comments else None

    @property
    def replies(self) -> List[PRReviewComment]:
        """Get all reply comments in this thread."""
        return self.comments[1:] if len(self.comments) > 1 else []

    @classmethod
    def from_graphql(cls, data: Dict[str, Any]) -> 'PRReviewThread':
        """
        Create PRReviewThread from GraphQL response.

        Args:
            data: Thread node from GraphQL PullRequestReviewThread

        Returns:
            PRReviewThread instance
        """
        thread_id = data.get("id", "")
        is_resolved = data.get("isResolved", False)
        is_outdated = data.get("isOutdated", False)
        path = data.get("path")

        comment_nodes = data.get("comments", {}).get("nodes", [])
        comments = [PRReviewComment.from_graphql(node) for node in comment_nodes]

        return cls(
            id=thread_id,
            is_resolved=is_resolved,
            is_outdated=is_outdated,
            path=path,
            comments=comments
        )


@dataclass
class PRIssueComment:
    """
    General PR comment not attached to specific code (GraphQL: IssueComment).

    Faithful representation of GitHub's GraphQL IssueComment object.
    These are general comments on the PR itself, not inline code review comments.
    See: https://docs.github.com/en/graphql/reference/objects#issuecomment

    Attributes:
        id: Comment database ID (databaseId in GraphQL)
        body: Comment text content
        author: User who created the comment
        created_at: Creation timestamp (ISO 8601)
        updated_at: Last update timestamp (ISO 8601)
    """
    id: int
    body: str
    author: User
    created_at: str
    updated_at: str

    @classmethod
    def from_graphql(cls, data: Dict[str, Any]) -> 'PRIssueComment':
        """
        Create PRIssueComment from GraphQL response.

        Args:
            data: Comment node from GraphQL IssueComment

        Returns:
            PRIssueComment instance
        """
        author_data = data.get("author", {})
        author = User.from_graphql(author_data)

        return cls(
            id=data.get("databaseId", 0),
            body=data.get("body", ""),
            author=author,
            created_at=data.get("createdAt", ""),
            updated_at=data.get("updatedAt", "")
        )


@dataclass
class PRMergeResult:
    """
    Result of merging a pull request

    Attributes:
        merged: Whether the PR was successfully merged
        sha: Commit SHA of the merge (if successful)
        message: Success or error message
    """
    merged: bool
    sha: Optional[str] = None
    message: str = ""


@dataclass
class Issue:
    """
    GitHub Issue representation.
    """
    number: int
    title: str
    body: str
    state: str
    author: User
    labels: List[str] = field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> 'Issue':
        """
        Create Issue from GitHub API response.
        """
        author_data = data.get("author", {})
        author = User.from_dict(author_data)

        labels_data = data.get("labels", [])
        labels = [label.get("name", "") for label in labels_data]

        return cls(
            number=data.get("number", 0),
            title=data.get("title", ""),
            body=data.get("body", ""),
            state=data.get("state", "OPEN"),
            author=author,
            labels=labels,
            created_at=data.get("createdAt"),
            updated_at=data.get("updatedAt"),
        )
