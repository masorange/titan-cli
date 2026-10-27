"""
What an error says, as the person reading it and the one pasting it elsewhere need it.

One place decides how an error of any shape (a message, an engine `Error`, a client's
`ClientError`, an exception) becomes a title, a message and the details around it,
so the panel that shows it and the text its copy button puts on the clipboard are
the same words.
"""
import traceback
from dataclasses import dataclass, field
from typing import Any, List, Optional

from titan_cli.core.result import ClientError
from titan_cli.engine.results import Error


@dataclass(frozen=True)
class ErrorReport:
    message: str
    title: str = ""
    details: List[str] = field(default_factory=list)  # "key: value" lines, shown dim
    traceback: str = ""  # only the copy carries it: too long for the panel

    def as_text(self) -> str:
        """What the copy button puts on the clipboard."""
        lines = [self.title] if self.title else []
        lines.append(self.message)
        lines.extend(self.details)
        text = "\n".join(lines)
        return f"{text}\n\n{self.traceback}" if self.traceback else text


def _traceback_of(exception: Optional[BaseException]) -> str:
    if exception is None or exception.__traceback__ is None:
        return ""
    return "".join(traceback.format_exception(type(exception), exception, exception.__traceback__)).strip()


def describe_error(error: Any, title: str = "") -> ErrorReport:
    """Report for a message, an engine `Error`, a `ClientError` or an exception."""
    if isinstance(error, ClientError):
        details = [f"code: {error.error_code}"] if error.error_code else []
        details += [f"{key}: {value}" for key, value in (error.details or {}).items()]
        return ErrorReport(error.error_message, title, details)
    if isinstance(error, Error):
        details = [f"code: {error.code}"] if error.code != 1 else []
        if error.exception is not None:
            details.append(f"exception: {type(error.exception).__name__}")
        return ErrorReport(error.message, title, details, _traceback_of(error.exception))
    if isinstance(error, BaseException):
        return ErrorReport(str(error) or type(error).__name__, title,
                           [f"exception: {type(error).__name__}"], _traceback_of(error))
    return ErrorReport(str(error), title)
