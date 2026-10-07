"""
Which keys a mod may bind.

A mod's key is an app-wide shortcut, so it must never shadow one of Titan's
own (any screen's, any widget's, the app's) nor another mod's: the first to
ask keeps it. The TUI collects the keys Titan binds; this module only decides.
"""

from typing import Collection, Mapping, Optional


def normalize_key(key: str) -> str:
    """Textual's spelling of a key: `"F5"` -> `"f5"`, `"Ctrl+K"` -> `"ctrl+k"`; a single character is kept as typed (`"A"` is shift+a)."""
    key = key.strip()
    return key if len(key) == 1 else key.lower()


def key_refusal(key: str, titan_keys: Collection[str], mod_keys: Mapping[str, str], mod: str) -> Optional[str]:
    """Why `mod` may not bind `key`, or None when it may. `mod_keys` maps each key a mod holds to that mod."""
    if not key or "," in key:
        return f"'{key}' is not one key"
    if key in titan_keys:
        return f"'{key}' is already a Titan shortcut"
    holder = mod_keys.get(key)
    if holder is not None and holder != mod:
        return f"'{key}' is already bound by mod '{holder}'"
    return None
