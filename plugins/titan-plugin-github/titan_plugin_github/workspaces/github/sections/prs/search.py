"""Searching the repo's PRs from the pane, with the syntax of GitHub's own search box.

The text typed is kept as it is until Enter: a search is a call to GitHub's search
API, which has a rate limit of its own, so it never runs per keystroke.
"""
from titan_cli.core.result import ClientError, ClientSuccess

from titan_plugin_github.readers.models import Search

# What the box suggests, as GitHub's own filters do; any other qualifier GitHub knows works too.
EXAMPLES = "author:ana label:bug review:approved status:failure draft:false base:develop"


def typed(m) -> str:
    """What is in the box now, searched or not."""
    return m.state.get("search_text") or ""


def write(m, text: str) -> None:
    m.state.set("search_text", text)


def current(m):
    """The search being shown, if one has been made."""
    return m.state.get("search")


def start(m, text: str) -> None:
    """Search for `text` on a background thread; an empty text clears the search.

    The claim is made before returning, so a second Enter while GitHub answers does nothing.
    """
    query = text.strip()
    m.state.set("search_text", text)
    if not query:
        m.state.set("search", None)
        return
    claimed = []

    def claim(found):
        if found is not None and found.status == "running" and found.query == query:
            return found
        claimed.append(True)
        return Search(query)

    m.state.update("search", claim)
    if claimed:
        m.run(lambda: read(m, query))


def clear(m) -> None:
    m.state.set("search_text", "")
    m.state.set("search", None)


def read(m, query: str) -> None:
    """Runs on a background thread: GitHub is asked, and the answer kept unless the search moved on."""
    def put(value: Search) -> None:
        # A newer search replaced this one while it was out: its answer is no longer wanted.
        m.state.update("search", lambda found: value if found is not None and found.query == query else found)

    github = m.client("github")
    try:
        if github is None:
            raise RuntimeError("github plugin not available")
        match github.search_prs(query):
            case ClientSuccess(data=prs):
                put(Search(query, "done", prs=list(prs)))
            case ClientError(error_message=err):
                put(Search(query, "error", error=err))
    except Exception as e:
        put(Search(query, "error", error=str(e)))
