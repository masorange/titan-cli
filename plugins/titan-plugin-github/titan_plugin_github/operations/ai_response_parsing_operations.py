"""Operations for parsing structured JSON responses from AI CLI adapters.

Centralizes the response-cleanup and JSON-extraction logic shared by every step that asks a
headless CLI for a JSON array or object (ai_review_plan, ai_review_findings,
ai_thread_resolution), so there is exactly one implementation to fix or extend.
"""

import json
from typing import Literal, Union

from titan_cli.core.result import ClientError, ClientResult, ClientSuccess


def extract_json_payload(text: str, kind: Literal["array", "object"]) -> ClientResult[Union[list, dict]]:
    """Strip markdown fences and parse the outermost JSON array/object out of CLI output."""
    opening, closing = ("[", "]") if kind == "array" else ("{", "}")
    cleaned = _strip_markdown_fences(text)
    start = cleaned.find(opening)
    end = cleaned.rfind(closing) + 1
    if start == -1 or end == 0:
        return ClientError(
            error_message=f"No JSON {kind} found in response", error_code="NO_JSON_PAYLOAD", log_level="warning"
        )
    try:
        payload = json.loads(cleaned[start:end])
    except json.JSONDecodeError as e:
        return ClientError(error_message=str(e), error_code="JSON_PARSE_ERROR", log_level="warning")
    return ClientSuccess(data=payload)


def _strip_markdown_fences(text: str) -> str:
    """Remove outer markdown code fences from a CLI response."""
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.split("\n")
    return "\n".join(lines[1:-1]) if len(lines) > 2 else stripped
