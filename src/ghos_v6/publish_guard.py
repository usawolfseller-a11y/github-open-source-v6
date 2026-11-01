"""Production-copy guard.

Test scaffolding once leaked into the live channel ("TYPE TEST · NEON
TERMINAL CARD", "the same data in another room"): those lines were typed
by hand while probing, so no formatter could have caught them. This guard
is the enforcement point — if a post, a caption or a card headline carries
scaffolding wording, the publish call fails loudly instead of shipping it.
"""
from __future__ import annotations

import re

# Markers that only ever belong to internal testing or to the operator's notes.
_SCAFFOLD_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bTYPE\s*TEST\b", re.I),
    re.compile(r"\bTEST\s+CARD\b", re.I),
    re.compile(r"\bthis\s+is\s+a\s+test\b", re.I),
    re.compile(r"\bplease\s+ignore\b", re.I),
    re.compile(r"\bprobe\b", re.I),
    re.compile(r"\bthe\s+same\s+data\b", re.I),
    re.compile(r"\bcard\s+type\b", re.I),
    re.compile(r"\bв\s+тесте\b", re.I),
)


class ScaffoldingError(ValueError):
    """Raised when test scaffolding would reach a public surface."""


def find_scaffolding(text: str) -> str:
    """Return the first scaffolding fragment found in ``text`` ('' if clean)."""
    value = str(text or "")
    for pattern in _SCAFFOLD_PATTERNS:
        match = pattern.search(value)
        if match:
            return match.group(0)
    return ""


def assert_production_copy(text: str, *, surface: str = "post") -> str:
    """Fail loudly if ``text`` contains operator-only wording."""
    found = find_scaffolding(text)
    if found:
        raise ScaffoldingError(
            f"{surface} contains test scaffolding ({found!r}); "
            "drafts must read like a production post"
        )
    return text
