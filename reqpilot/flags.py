"""Unresolved flags: what the reviewer and the Python checks still report for an item.

Used to warn when a flagged item is accepted, and to mark it "needs-review" in the export.
Python findings are always current (they are rerun after every edit). Reviewer verdicts are
for the text the reviewer saw, so after an edit they are marked as such.
"""

from __future__ import annotations

from reqpilot.checks import Finding
from reqpilot.models import Requirements
from reqpilot.reviewer import Review


def unresolved_flags(
    item_id: str,
    req: Requirements,
    review: Review | None,
    findings: list[Finding],
    edited: set[str] | frozenset[str] = frozenset(),
) -> list[str]:
    """One line per open flag on a story (including its criteria) or non-functional item."""
    stale = " (judged before your edit)" if item_id in edited else ""
    flags: list[str] = []
    result = review.results.get(item_id) if review else None
    if result:
        flags += [
            f"Reviewer, {v.rule.value.replace('_', ' ')}: {v.reason}{stale}"
            for v in result.verdicts
            if not v.passed
        ]
    nfr = review.non_functional.get(item_id) if review else None
    if nfr and not nfr.measurable:
        flags.append(f"Reviewer: not measurable. {nfr.reason}".rstrip(". ") + stale)
    own = {item_id} | {c.id for c in req.criteria_for(item_id)}
    flags += [f"Python check ({f.item_id}): {f.message}" for f in findings if f.item_id in own]
    return flags
