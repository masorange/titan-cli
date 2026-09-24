"""Pydantic models for project-specific review profile configuration."""

from pydantic import BaseModel, Field

from .review_enums import AttentionTier, ChecklistCategory


class ReviewAxisRule(BaseModel):
    """Rule that determines when a review axis should apply."""

    always_include: bool = Field(default=False)
    patterns: list[str] = Field(default_factory=list)


class ReviewProfile(BaseModel):
    """What a project tunes about its reviews: which files get which attention, which
    review axes apply when, and which of its documents the review is held to."""

    version: int = Field(default=1)
    file_roles: dict[str, list[str]] = Field(default_factory=dict)
    attention: dict[str, AttentionTier] = Field(
        default_factory=dict,
        description="How much attention each file role is worth: deep (the model opens "
        "the file and explores), glance (the model sees only the diff, packed with "
        "others and cheap) or skip (not reviewed, but said so on screen). Keyed by the "
        "role names `file_roles` defines, plus the three the manifest derives - "
        "`docs_or_generated`, `tests`, `config_or_contracts` - and `other` for a file "
        "no role claims. A role absent from this map falls back to glance: covering a "
        "file cheaply is the safe default, skipping it silently is not.",
    )
    always_deep: list[str] = Field(
        default_factory=list,
        description="Globs that enter the deep tier whatever their role says and "
        "however little changed. This is the one path-based escape hatch, and it exists "
        "because a two-line change in a security boundary deserves a full read while "
        "its role-level default may not. It outranks every other rule, including the "
        "lockfile and rename-only skips: second-guessing an explicit instruction would "
        "make the hatch useless.",
    )
    context_docs: list[str] = Field(
        default_factory=list,
        description="Paths or globs of project documents the review session should read "
        "BEFORE judging the code: architecture notes, conventions, an agent harness, "
        "whatever states the rules this repo is held to. Only the paths travel in the "
        "prompt -- the session opens them from the working tree itself -- and only paths "
        "that actually exist there are offered, so a stale entry costs nothing. Keep the "
        "list short and load-bearing: this is the reading a new reviewer would do first, "
        "not the whole repository. A review with no project context judges the diff "
        "against general good practice and reports things the project decided on purpose.",
    )
    max_context_docs: int = Field(
        default=8,
        ge=0,
        le=25,
        description="Ceiling on how many context documents are offered to the session. A "
        "bound, not a target: every document is reading time inside the one deep call, "
        "and an unbounded list turns 'read the docs' into 'read the repo'.",
    )
    review_axes: dict[ChecklistCategory, ReviewAxisRule] = Field(default_factory=dict)



class ReviewChecklistFile(BaseModel):
    """Project-specific checklist file format."""

    version: int = Field(default=1)
    items: list["ReviewChecklistItemFile"] = Field(default_factory=list)


class ReviewChecklistItemFile(BaseModel):
    """Single project-specific review checklist item."""

    id: ChecklistCategory
    name: str
    description: str
