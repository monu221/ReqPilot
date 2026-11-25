"""Export accepted items: CSV for Jira import and Markdown (docs/plan.md, M7).

Only accepted stories, non-functional and out-of-scope items are exported. Open questions
are exported if they concern an accepted story or no story in particular (Markdown lists all).
Accepted items that still have unresolved flags are labelled "needs-review". Exports made
from a demo set say so in every file ("demo-data" label in CSV, a banner in Markdown).

The output has no timestamps, so the same input always gives the same file.
"""

from __future__ import annotations

import csv
import io
from typing import TYPE_CHECKING

from reqpilot.checks import Finding, run_checks
from reqpilot.demo import DEMO_LABEL
from reqpilot.flags import unresolved_flags
from reqpilot.models import OpenQuestion, Requirements, Story, StoryStatus, TestCase
from reqpilot.notes import Sentence
from reqpilot.reviewer import Review
from reqpilot.traceability import build_matrix

if TYPE_CHECKING:
    from reqpilot.workflow import Workspace

JIRA_LABEL_COLUMNS = 4
JIRA_SUMMARY_MAX = 80
NEEDS_REVIEW = "needs-review"
A = StoryStatus.ACCEPTED


def jira_columns(criteria_in_description: bool = False) -> list[str]:
    criteria = [] if criteria_in_description else ["Acceptance Criteria"]
    return ["Summary", "Description", *criteria, "Issue Type", *["Labels"] * JIRA_LABEL_COLUMNS]


JIRA_COLUMNS = jira_columns()


def has_accepted(req: Requirements) -> bool:
    return any(i.status == A for i in [*req.stories, *req.non_functional, *req.out_of_scope])


def short_title(text: str, limit: int = JIRA_SUMMARY_MAX) -> str:
    """A Jira summary: capitalised, at most `limit` characters, cut at a word boundary."""
    text = " ".join(text.split())
    text = text[:1].upper() + text[1:]
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rsplit(" ", 1)[0].rstrip(",;:")
    return cut + "…"


def story_title(story: Story) -> str:
    """The goal without a leading "to": "Report broken equipment from the ward PC"."""
    goal = story.goal
    return short_title(goal[3:] if goal.lower().startswith("to ") else goal)


def _sources(cited: list[int], sentences: list[Sentence] | None) -> str:
    if not cited:
        return "none cited"
    text_of = {s.number: s.text for s in sentences or []}
    return "; ".join(f"[{n}] {text_of[n]}" if n in text_of else f"[{n}]" for n in cited)


def _labels(*labels: str) -> list[str]:
    kept = [label for label in labels if label]
    return kept + [""] * (JIRA_LABEL_COLUMNS - len(kept))


def exported_questions(req: Requirements, review: Review | None) -> list[OpenQuestion]:
    """Open questions about at least one accepted story, or about no story in particular."""
    accepted = {s.id for s in req.stories if s.status == A}
    questions = req.open_questions + (review.open_questions if review else [])
    return [
        q for q in questions
        if not q.related_story_ids or accepted.intersection(q.related_story_ids)
    ]  # fmt: skip


def to_jira_csv(
    req: Requirements,
    test_cases: list[TestCase],
    sentences: list[Sentence] | None = None,
    demo: bool = False,
    review: Review | None = None,
    findings: list[Finding] | None = None,
    edited: set[str] | frozenset[str] = frozenset(),
    criteria_in_description: bool = False,
) -> str:
    """Rows: accepted stories (Story), accepted non-functional items (Task) and open questions
    (Task, "open-question"). Items with unresolved flags get the "needs-review" label and a
    list of the flags in the description.

    `findings` default to the Python checks on `req` (against `sentences`, if given).
    With `criteria_in_description`, the criteria go into the description and the
    "Acceptance Criteria" column is left out, so no custom field is needed in Jira.
    """
    if findings is None:
        findings = run_checks(req, sentences)
    buf = io.StringIO()
    out = csv.writer(buf, lineterminator="\n")
    out.writerow(jira_columns(criteria_in_description))
    banner = f"{DEMO_LABEL.upper()}.\n\n" if demo else ""
    demo_label = "demo-data" if demo else ""
    tests_for: dict[str, list[TestCase]] = {}
    for t in test_cases:
        tests_for.setdefault(t.criterion_id, []).append(t)

    def row(summary: str, description: str, criteria: str, kind: str, labels: list[str]):
        middle = [] if criteria_in_description else [criteria]
        out.writerow([summary, description, *middle, kind, *labels])

    def flag_text(flags: list[str]) -> str:
        if not flags:
            return ""
        return "\n\nUnresolved flags (accepted anyway):\n" + "\n".join(f"- {f}" for f in flags)

    titles = {s.id: story_title(s) for s in req.stories}
    for s in req.stories:
        if s.status != A:
            continue
        criteria = req.criteria_for(s.id)
        criteria_text = "\n".join(f"{c.id}: {c.text}" for c in criteria)
        tests = [t for c in criteria for t in tests_for.get(c.id, [])]
        flags = unresolved_flags(s.id, req, review, findings, edited)
        description = (
            f"{banner}{s.text}"
            + flag_text(flags)
            + f"\n\nSource: {_sources(s.source_sentences, sentences)}"
            + (f"\n\nAcceptance criteria:\n{criteria_text}" if criteria_in_description else "")
            + (
                "\n\nTest cases:\n" + "\n".join(f"- {t.id}: {t.title}" for t in tests)
                if tests
                else ""
            )
            + f"\n\nReqPilot id: {s.id}"
        )
        labels = _labels("reqpilot", demo_label, NEEDS_REVIEW if flags else "")
        row(titles[s.id], description, criteria_text, "Story", labels)
    for n in req.non_functional:
        if n.status != A:
            continue
        flags = unresolved_flags(n.id, req, review, findings, edited)
        measure = n.measure or "not given (open question)"
        description = (
            f"{banner}{n.statement}"
            + flag_text(flags)
            + f"\n\nMeasure: {measure}\n\nSource: {_sources(n.source_sentences, sentences)}"
            + f"\n\nReqPilot id: {n.id}"
        )
        labels = _labels("reqpilot", "non-functional", demo_label, NEEDS_REVIEW if flags else "")
        row(short_title(f"{n.category}: {n.statement}"), description, "", "Task", labels)
    for q in exported_questions(req, review):
        affects = (
            "Affects stories: "
            + ", ".join(f"{i} ({titles[i]})" for i in q.related_story_ids)
            + "\n(ReqPilot ids; each story's description ends with its ReqPilot id.)"
            if q.related_story_ids
            else "Affects: the whole set (no particular story)."
        )
        description = (
            f"{banner}{q.question}\n\n{affects}\n\nRaised by: {q.origin}\n\nReqPilot id: {q.id}"
        )
        summary = short_title(f"{q.topic}: {q.question}" if q.topic else q.question)
        row(summary, description, "", "Task", _labels("reqpilot", "open-question", demo_label))
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
    edited: set[str] | frozenset[str] = frozenset(),
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
        if flags := unresolved_flags(s.id, req, review, findings, edited):
            lines += ["**Needs review.** Unresolved flags (accepted anyway):", ""]
            lines += [f"- {f}" for f in flags] + [""]
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
        edited=ws.edited,
    )


def workspace_jira_csv(
    ws: Workspace, findings: list[Finding] | None = None, criteria_in_description: bool = False
) -> str:
    return to_jira_csv(
        ws.req or Requirements(),
        ws.test_cases,
        ws.sentences,
        demo=ws.is_demo,
        review=ws.review,
        findings=findings if findings is not None else ws.findings(),
        edited=ws.edited,
        criteria_in_description=criteria_in_description,
    )
