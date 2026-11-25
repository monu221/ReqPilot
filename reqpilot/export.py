"""Export accepted items: CSV for Jira import and Markdown (docs/plan.md, M7).

Only accepted stories, non-functional and out-of-scope items are exported. Open questions
are all exported in Markdown, since they are unresolved by nature. Exports made from a demo
set say so in every file ("demo-data" label in CSV, a banner in Markdown).

The output has no timestamps, so the same input always gives the same file.
"""

from __future__ import annotations

import csv
import io
from typing import TYPE_CHECKING

from reqpilot.checks import Finding
from reqpilot.demo import DEMO_LABEL
from reqpilot.models import Requirements, StoryStatus, TestCase
from reqpilot.notes import Sentence
from reqpilot.reviewer import Review
from reqpilot.traceability import build_matrix

if TYPE_CHECKING:
    from reqpilot.workflow import Workspace

JIRA_COLUMNS = [
    "Summary",
    "Description",
    "Acceptance Criteria",
    "Issue Type",
    "Labels",
    "Labels",
    "Labels",
]
JIRA_SUMMARY_MAX = 255
A = StoryStatus.ACCEPTED


def has_accepted(req: Requirements) -> bool:
    return any(i.status == A for i in [*req.stories, *req.non_functional, *req.out_of_scope])


def _summary(text: str) -> str:
    return text if len(text) <= JIRA_SUMMARY_MAX else text[: JIRA_SUMMARY_MAX - 1] + "…"


def _sources(cited: list[int], sentences: list[Sentence] | None) -> str:
    if not cited:
        return "none cited"
    text_of = {s.number: s.text for s in sentences or []}
    return "; ".join(f"[{n}] {text_of[n]}" if n in text_of else f"[{n}]" for n in cited)


def to_jira_csv(
    req: Requirements,
    test_cases: list[TestCase],
    sentences: list[Sentence] | None = None,
    demo: bool = False,
) -> str:
    """One row per accepted story (Story) and accepted non-functional item (Task)."""
    buf = io.StringIO()
    out = csv.writer(buf, lineterminator="\n")
    out.writerow(JIRA_COLUMNS)
    banner = f"{DEMO_LABEL.upper()}.\n\n" if demo else ""
    demo_label = "demo-data" if demo else ""
    tests_for: dict[str, list[TestCase]] = {}
    for t in test_cases:
        tests_for.setdefault(t.criterion_id, []).append(t)
    for s in req.stories:
        if s.status != A:
            continue
        criteria = req.criteria_for(s.id)
        tests = [t for c in criteria for t in tests_for.get(c.id, [])]
        description = (
            f"{banner}{s.text}\n\nSource: {_sources(s.source_sentences, sentences)}"
            + (
                "\n\nTest cases:\n" + "\n".join(f"- {t.id}: {t.title}" for t in tests)
                if tests
                else ""
            )
            + f"\n\nReqPilot id: {s.id}"
        )
        out.writerow(
            [
                _summary(s.text),
                description,
                "\n".join(f"{c.id}: {c.text}" for c in criteria),
                "Story",
                "reqpilot",
                demo_label,
                "",
            ]
        )
    for n in req.non_functional:
        if n.status != A:
            continue
        measure = n.measure or "not given (open question)"
        out.writerow(
            [
                _summary(f"Non-functional ({n.category}): {n.statement}"),
                f"{banner}{n.statement}\n\nMeasure: {measure}\n\n"
                f"Source: {_sources(n.source_sentences, sentences)}\n\nReqPilot id: {n.id}",
                "",
                "Task",
                "reqpilot",
                "non-functional",
                demo_label,
            ]
        )
    return buf.getvalue()


def _md_escape(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def to_markdown(
    sentences: list[Sentence],
    req: Requirements,
    test_cases: list[TestCase],
    review: Review | None = None,
    findings: list[Finding] | None = None,
    demo: bool = False,
    title: str = "ReqPilot export",
) -> str:
    findings = findings or []
    lines = [f"# {title}", ""]
    if demo:
        lines += [
            f"> **{DEMO_LABEL}.** Stories, review and test cases are hand-written "
            "examples, not answers from the AI.",
            "",
        ]
    stories = [s for s in req.stories if s.status == A]
    nfr = [n for n in req.non_functional if n.status == A]
    oos = [o for o in req.out_of_scope if o.status == A]
    questions = req.open_questions + (review.open_questions if review else [])
    lines += [
        f"Accepted: {len(stories)} of {len(req.stories)} stories, {len(nfr)} of "
        f"{len(req.non_functional)} non-functional items, {len(oos)} of "
        f"{len(req.out_of_scope)} out-of-scope items. Open questions: {len(questions)}.",
        "",
        "## User stories",
        "",
    ]
    tests_for: dict[str, list[TestCase]] = {}
    for t in test_cases:
        tests_for.setdefault(t.criterion_id, []).append(t)
    if not stories:
        lines += ["None accepted.", ""]
    for s in stories:
        lines += [
            f"### {s.id}: {s.text}",
            "",
            f"Source: {_sources(s.source_sentences, sentences)}",
            "",
        ]
        lines += ["Acceptance criteria:", ""]
        lines += [f"- **{c.id}** {c.text}" for c in req.criteria_for(s.id)] or ["- none"]
        lines.append("")
        notes = []
        result = review.results.get(s.id) if review else None
        if result:
            notes += [
                f"Reviewer, {v.rule.value.replace('_', ' ')}: {v.reason}"
                for v in result.verdicts
                if not v.passed
            ]
        own = {s.id} | {c.id for c in req.criteria_for(s.id)}
        notes += [f"Python check ({f.item_id}): {f.message}" for f in findings if f.item_id in own]
        if notes:
            lines += ["Quality notes:", ""] + [f"- {n}" for n in notes] + [""]
        tests = [t for c in req.criteria_for(s.id) for t in tests_for.get(c.id, [])]
        if tests:
            lines += [
                "Test cases:",
                "",
                "| Id | Criterion | Title | Preconditions | Steps | Expected |",
                "| --- | --- | --- | --- | --- | --- |",
            ]
            lines += [
                f"| {t.id} | {t.criterion_id} | {_md_escape(t.title)} | "
                f"{_md_escape('; '.join(t.preconditions)) or '–'} | "
                f"{_md_escape(' → '.join(t.steps))} | {_md_escape(t.expected_result)} |"
                for t in tests
            ]
            lines.append("")
    lines += ["## Non-functional", ""]
    lines += [
        f"- **{n.id}** ({n.category}) {n.statement} Measure: {n.measure or 'not given'}. "
        f"Source: {_sources(n.source_sentences, sentences)}"
        for n in nfr
    ] or ["None accepted."]
    lines += ["", "## Out of scope", ""]
    lines += [
        f"- **{o.id}** {o.statement}"
        + (f" ({o.reason})" if o.reason else "")
        + f" Source: {_sources(o.source_sentences, sentences)}"
        for o in oos
    ] or ["None accepted."]
    lines += ["", "## Open questions", ""]
    lines += [
        f"- **{q.id}** ({q.origin}){' ' + q.topic + ':' if q.topic else ''} {q.question}"
        + (f" Stories: {', '.join(q.related_story_ids)}." if q.related_story_ids else "")
        for q in questions
    ] or ["None."]
    m = build_matrix(sentences, req, test_cases)
    lines += ["", "## Traceability", ""]
    if m.rows:
        lines += ["| Sentence | Item | Criterion | Test case |", "| --- | --- | --- | --- |"]
        lines += [
            f"| {r.sentence or '–'} | {r.item_id} | {r.criterion_id or '–'} | "
            f"{r.test_case_id or '–'} |"
            for r in m.rows
        ]
        gaps = [
            ("Accepted stories without a test case", m.stories_without_test_cases),
            ("Criteria without a test case", m.criteria_without_test_cases),
            ("Accepted items without a source sentence", m.items_without_source),
            ("Note sentences no accepted item uses", [str(n) for n in m.unused_sentences]),
        ]
        gap_lines = [f"- {name}: {', '.join(items)}" for name, items in gaps if items]
        lines += ["", "Gaps:", ""] + (gap_lines or ["- none"])
    else:
        lines.append("No accepted items.")
    return "\n".join(lines) + "\n"


def workspace_markdown(ws: Workspace, findings: list[Finding] | None = None) -> str:
    title = f"ReqPilot export: {ws.demo.title}" if ws.demo else "ReqPilot export"
    return to_markdown(
        ws.sentences,
        ws.req or Requirements(),
        ws.test_cases,
        review=ws.review,
        findings=findings if findings is not None else ws.findings(),
        demo=ws.is_demo,
        title=title,
    )
