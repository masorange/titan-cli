# plugins/titan-plugin-github/titan_plugin_github/models/network/graphql/pull_request.py
"""
GraphQL Pull Request Models

Faithful representations of GitHub PullRequest fields that are only available
through the GraphQL API (the gh CLI's `pr view --json` does not expose them).
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class GraphQLPullRequestMergeQueueState:
    """
    Merge queue state of a pull request from the GraphQL API.

    See: https://docs.github.com/en/graphql/reference/objects#pullrequest

    Field names match the GraphQL schema exactly (camelCase preserved).

    Attributes:
        number: Pull request number
        state: Pull request state ("OPEN", "CLOSED", "MERGED")
        isMergeQueueEnabled: Whether the base branch requires a merge queue
        isInMergeQueue: Whether this pull request is currently in the merge queue
        mergeQueueEntryPosition: Position in the queue, when queued
        mergeQueueEntryState: Queue entry state (e.g. "QUEUED", "AWAITING_CHECKS",
            "MERGEABLE", "UNMERGEABLE"), when queued
    """
    number: int
    state: str
    isMergeQueueEnabled: bool
    isInMergeQueue: bool
    mergeQueueEntryPosition: Optional[int] = None
    mergeQueueEntryState: Optional[str] = None

    @classmethod
    def from_graphql(cls, data: Dict[str, Any]) -> 'GraphQLPullRequestMergeQueueState':
        """
        Create GraphQLPullRequestMergeQueueState from a GraphQL pullRequest node.

        Args:
            data: pullRequest node from the GraphQL response

        Returns:
            GraphQLPullRequestMergeQueueState instance

        Raises:
            ValueError: If the node is missing the required "number" field
        """
        if data.get("number") is None:
            raise ValueError('missing "number" in GraphQL pullRequest node')

        entry = data.get("mergeQueueEntry") or {}

        return cls(
            number=int(data["number"]),
            state=data.get("state", ""),
            isMergeQueueEnabled=bool(data.get("isMergeQueueEnabled", False)),
            isInMergeQueue=bool(data.get("isInMergeQueue", False)),
            mergeQueueEntryPosition=entry.get("position"),
            mergeQueueEntryState=entry.get("state"),
        )


@dataclass
class GraphQLMergeQueueEntry:
    """
    One entry of a repository's merge queue from the GraphQL API.

    See: https://docs.github.com/en/graphql/reference/objects#mergequeueentry

    Attributes:
        position: 1-based position in the queue
        state: Entry state ("QUEUED", "AWAITING_CHECKS", "MERGEABLE",
            "UNMERGEABLE", "LOCKED")
        estimatedTimeToMerge: Seconds GitHub estimates until it merges, if known
        pullRequestNumber: Number of the queued pull request
        pullRequestTitle: Title of the queued pull request
        authorLogin: Login of the pull request's author, if visible
        pullRequestUrl: The queued pull request's web page
    """
    position: int
    state: str
    pullRequestNumber: int
    pullRequestTitle: str
    estimatedTimeToMerge: Optional[int] = None
    authorLogin: Optional[str] = None
    pullRequestUrl: str = ""

    @classmethod
    def from_graphql(cls, data: Dict[str, Any]) -> 'GraphQLMergeQueueEntry':
        """
        Create GraphQLMergeQueueEntry from a GraphQL MergeQueueEntry node.

        Raises:
            ValueError: If the node has no position or no pull request number
        """
        pr = data.get("pullRequest") or {}
        if data.get("position") is None or pr.get("number") is None:
            raise ValueError('missing "position" or "pullRequest.number" in MergeQueueEntry node')
        return cls(
            position=int(data["position"]),
            state=data.get("state") or "",
            pullRequestNumber=int(pr["number"]),
            pullRequestTitle=pr.get("title") or "",
            estimatedTimeToMerge=data.get("estimatedTimeToMerge"),
            authorLogin=(pr.get("author") or {}).get("login"),
            pullRequestUrl=pr.get("url") or "",
        )


@dataclass
class GraphQLMergeQueue:
    """
    A repository's merge queue for its default branch, from the GraphQL API.

    See: https://docs.github.com/en/graphql/reference/objects#mergequeue

    Attributes:
        viewerLogin: Login of the authenticated user
        defaultBranch: Name of the repository's default branch
        isConfigured: Whether the default branch has a merge queue at all
        mergeMethod: Configured merge method ("MERGE", "SQUASH", "REBASE"), if any
        totalCount: Entries in the queue, including those not fetched
        entries: The first entries of the queue, in order
    """
    viewerLogin: Optional[str]
    defaultBranch: str
    isConfigured: bool
    mergeMethod: Optional[str]
    totalCount: int
    entries: List[GraphQLMergeQueueEntry]

    @classmethod
    def from_graphql(cls, data: Dict[str, Any]) -> 'GraphQLMergeQueue':
        """
        Create GraphQLMergeQueue from the GET_MERGE_QUEUE response's "data" object.

        Raises:
            ValueError: If the response has no repository
        """
        repository = data.get("repository")
        if repository is None:
            raise ValueError('missing "repository" in GraphQL merge queue response')
        queue = repository.get("mergeQueue")
        entries = (queue or {}).get("entries") or {}
        return cls(
            viewerLogin=(data.get("viewer") or {}).get("login"),
            defaultBranch=(repository.get("defaultBranchRef") or {}).get("name") or "",
            isConfigured=queue is not None,
            mergeMethod=((queue or {}).get("configuration") or {}).get("mergeMethod"),
            totalCount=int(entries.get("totalCount") or 0),
            entries=[GraphQLMergeQueueEntry.from_graphql(n) for n in entries.get("nodes") or []],
        )
