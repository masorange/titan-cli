"""Merging a project's review configuration onto Titan's, without surprises.

Before this existed, a project's `profile.yaml` **replaced** Titan's profile outright:
the manager validated the YAML on its own and every field defaults to empty, so a file
that defined a single rule silently left the review with no `file_roles` and no
`review_axes` — every file classified as "other" and the axes
falling back to their two emergency values. A team tuning its review got a degraded one
and nothing said so.

The rule that fixes it without introducing a different kind of confusion:

**The unit of merge is the named entry, never the pattern list.**

The team's `file_roles.tests` replaces Titan's `file_roles.tests` entirely; a key the
team does not mention keeps Titan's value; removing one is explicit. So the state
"Titan's 20 test globs plus the team's 3 equals 23 globs nobody wrote" is not reachable
— you either own a key completely or you leave it alone. One mental model, no
half-states.

Everything here is pure: dicts in, dicts and a report out. The managers do the I/O and
the validation.
"""

from dataclasses import dataclass, field
from typing import Any

# Fields merged key-by-key. Each holds a mapping whose values are owned whole.
# `attention` is one of them: a project that sends one role to deep must not lose the
# tier of every role it did not mention.
_KEYED_MAPPING_FIELDS = ("file_roles", "attention", "review_axes")

# The block that names what to drop from Titan's defaults. Not a profile field.
REMOVE_KEY = "remove"


@dataclass(frozen=True)
class ReviewConfigMergeReport:
    """What the merge actually did, so the result can be shown rather than trusted.

    No merge scheme is trustworthy if you cannot see what is in force, which is why
    this is returned rather than logged in passing.
    """

    replaced: list[str] = field(default_factory=list)
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    unknown_removals: list[str] = field(default_factory=list)
    ignored_keys: list[str] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not (self.replaced or self.added or self.removed)

    @property
    def has_warnings(self) -> bool:
        """Whether the project file asked for something that did not exist.

        Worth surfacing: a typo in a `remove:` target or a field name is silent
        otherwise, and the user would believe a change took effect that did not.
        """
        return bool(self.unknown_removals or self.ignored_keys)

    def as_log_fields(self) -> dict[str, Any]:
        return {
            "replaced": self.replaced,
            "added": self.added,
            "removed": self.removed,
            "unknown_removals": self.unknown_removals,
            "ignored_keys": self.ignored_keys,
        }


def merge_review_profile_data(
    base: dict, project: dict
) -> tuple[dict, ReviewConfigMergeReport]:
    """Merge a project profile dict onto Titan's, per key, and report every change.

    `base` is Titan's default profile dumped to plain JSON types; `project` is the
    parsed YAML. Neither is mutated. The result still has to be validated by the
    caller — this decides *what* the effective configuration is, not whether it is
    well-formed.
    """
    merged = _deep_copy_mapping(base)
    replaced: list[str] = []
    added: list[str] = []
    removed: list[str] = []
    unknown_removals: list[str] = []
    ignored_keys: list[str] = []

    project = dict(project or {})
    removals = project.pop(REMOVE_KEY, None) or {}

    for field_name, value in project.items():
        if field_name not in base:
            # Pydantic would ignore an unknown field in silence, which turns a typo
            # into a change that appears to have been applied.
            ignored_keys.append(field_name)
            continue

        if field_name in _KEYED_MAPPING_FIELDS and isinstance(value, dict):
            for key, entry in value.items():
                target = f"{field_name}.{key}"
                (replaced if key in merged.get(field_name, {}) else added).append(target)
                merged.setdefault(field_name, {})[key] = entry
            continue

        # A scalar, or a shape that does not match the field's own: replace outright
        # and let validation reject it if it is wrong. Reporting it as replaced is
        # accurate either way.
        replaced.append(field_name)
        merged[field_name] = value

    merged, removed, unknown_removals = _apply_removals(merged, removals)

    return merged, ReviewConfigMergeReport(
        replaced=sorted(set(replaced)),
        added=sorted(set(added)),
        removed=sorted(set(removed)),
        unknown_removals=sorted(set(unknown_removals)),
        ignored_keys=sorted(set(ignored_keys)),
    )


def _apply_removals(merged: dict, removals: Any) -> tuple[dict, list[str], list[str]]:
    """Drop the entries a `remove:` block names, reporting any that were not there.

    A removal that matches nothing is NOT an error: the profile still works, and
    failing the whole review over a stale line in a config file would be a poor trade.
    It is reported instead, because the user believes it did something.
    """
    removed: list[str] = []
    unknown: list[str] = []

    if not isinstance(removals, dict):
        if removals:
            unknown.append(f"{REMOVE_KEY} (expected a mapping of field to names)")
        return merged, removed, unknown

    for field_name, keys in removals.items():
        if isinstance(keys, str):
            keys = [keys]
        if not isinstance(keys, list):
            unknown.append(f"{REMOVE_KEY}.{field_name} (expected a list)")
            continue

        # De-duplicated: a name repeated in the file would be removed on the first
        # pass and then reported as "matched nothing" on the second, which is a warning
        # about the tool's own behaviour rather than about the user's config.
        for key in _unique(keys):
            target = f"{field_name}.{key}"
            if field_name in _KEYED_MAPPING_FIELDS:
                if isinstance(merged.get(field_name), dict) and key in merged[field_name]:
                    del merged[field_name][key]
                    removed.append(target)
                else:
                    unknown.append(target)
            else:
                unknown.append(target)

    return merged, removed, unknown


def merge_review_checklist_items(
    base_items: list[dict], project_items: list[dict], removals: Any = None
) -> tuple[list[dict], ReviewConfigMergeReport]:
    """Merge project checklist items onto Titan's twelve, keyed by `id`.

    Same rule as the profile: an item with a known id replaces it in place (so the
    default order, which puts functional correctness before style, survives), a new id
    appends, and `remove:` takes an id out. Before this, a project checklist REPLACED
    all twelve defaults, so adding one project-specific item cost the other eleven.
    """
    merged = [dict(item) for item in base_items]
    index = {item.get("id"): position for position, item in enumerate(merged)}
    known_keys = {key for item in base_items for key in item} or {"id", "name", "description"}
    replaced: list[str] = []
    added: list[str] = []
    ignored: list[str] = []

    for item in project_items or []:
        if not isinstance(item, dict):
            merged.append(item)
            continue
        item_id = item.get("id")
        # A key the item model does not have would be dropped by validation in silence.
        # The one that matters is `relevant_file_patterns`: WHEN an axis applies moved to
        # the profile's `review_axes`, and a checklist still carrying patterns must say
        # they no longer do anything instead of looking applied.
        unknown_keys = sorted(key for key in item if key not in known_keys)
        if unknown_keys:
            ignored.extend(f"items.{item_id}.{key}" for key in unknown_keys)
            item = {key: value for key, value in item.items() if key in known_keys}
        if item_id in index:
            merged[index[item_id]] = item
            replaced.append(str(item_id))
        else:
            index[item_id] = len(merged)
            merged.append(item)
            added.append(str(item_id))

    removed: list[str] = []
    unknown: list[str] = []
    if isinstance(removals, str):
        removals = [removals]
    if isinstance(removals, list):
        for item_id in _unique(removals):
            kept = [item for item in merged if not (isinstance(item, dict) and item.get("id") == item_id)]
            if len(kept) != len(merged):
                merged = kept
                removed.append(str(item_id))
            else:
                unknown.append(str(item_id))
    elif removals:
        unknown.append(f"{REMOVE_KEY} (expected a list of checklist ids)")

    return merged, ReviewConfigMergeReport(
        replaced=sorted(set(replaced)),
        added=sorted(set(added)),
        removed=sorted(set(removed)),
        unknown_removals=sorted(set(unknown)),
        ignored_keys=sorted(set(ignored)),
    )


def _unique(values: list) -> list:
    """Order-preserving de-duplication for a list read out of a config file."""
    seen: list = []
    for value in values:
        if value not in seen:
            seen.append(value)
    return seen


def _deep_copy_mapping(data: dict) -> dict:
    """Copy one level deeper than `dict(...)`, so merging never writes into the base.

    The base is Titan's default profile: mutating it would leak one project's
    configuration into the next resolution in the same process.
    """
    copied: dict = {}
    for key, value in (data or {}).items():
        if isinstance(value, dict):
            copied[key] = _deep_copy_mapping(value)
        elif isinstance(value, list):
            copied[key] = [
                _deep_copy_mapping(entry) if isinstance(entry, dict) else entry for entry in value
            ]
        else:
            copied[key] = value
    return copied
