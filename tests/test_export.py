"""Export tests. Golden files in tests/data/export are made from the FAKE demo sets.

To regenerate them after a deliberate format change: set UPDATE_GOLDEN=1 and run pytest.
"""

import csv
import io
import os

import pytest

from reqpilot import export, workflow
from reqpilot.config import REPO_ROOT
from reqpilot.demo import DEMO_LABEL, load_demo
from reqpilot.models import StoryStatus

GOLDEN = REPO_ROOT / "tests" / "data" / "export"
A = StoryStatus.ACCEPTED


def _workspace(name, accept=all, demo=True):
    d = load_demo(name)
    ws = workflow.start(d.notes, d)
    workflow.write_and_review(ws)
    for item in [*ws.req.stories, *ws.req.non_functional, *ws.req.out_of_scope]:
        if accept is all or item.id in accept:
            workflow.set_status(ws, item.id, A)
    workflow.make_test_cases(ws)
    if not demo:
        ws.demo = None
    return ws


def _check_golden(name: str, text: str):
    path = GOLDEN / name
    if os.environ.get("UPDATE_GOLDEN"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    assert text == path.read_text(encoding="utf-8"), f"{name} changed; see module docstring"


@pytest.mark.parametrize("name", ["01_maintenance", "03_lab_results"])
def test_jira_csv_golden(name):
    _check_golden(f"{name}_jira.csv", export.workspace_jira_csv(_workspace(name)))


@pytest.mark.parametrize("name", ["01_maintenance", "03_lab_results"])
def test_markdown_golden(name):
    _check_golden(f"{name}.md", export.workspace_markdown(_workspace(name)))


def _rows(text):
    return list(csv.reader(io.StringIO(text)))


def _csv(ws, **kw):
    return _rows(export.workspace_jira_csv(ws, **kw))


def _by_id(rows):
    """Rows keyed by the ReqPilot id at the end of the description."""
    return {r[1].rsplit("ReqPilot id: ", 1)[1]: r for r in rows[1:]}


def _labels(row):
    return [x for x in row[-export.JIRA_LABEL_COLUMNS :] if x]


def test_csv_has_jira_columns_and_only_accepted_items():
    ws = _workspace("03_lab_results", accept={"S1", "S4", "N1"})
    rows = _csv(ws)
    assert rows[0] == export.JIRA_COLUMNS
    by_id = _by_id(rows)
    assert [k for k in by_id if not k.startswith(("Q", "R"))] == ["S1", "S4", "N1"]
    assert "S1-AC1: Given a lab result is validated" in by_id["S1"][2]
    assert "T1:" in by_id["S1"][1]
    assert _labels(by_id["N1"]) == ["reqpilot", "non-functional", "demo-data"]


def test_demo_marking_in_csv_and_markdown():
    ws = _workspace("02_procurement", accept={"S1"})
    row = _by_id(_csv(ws))["S1"]
    assert row[1].startswith(DEMO_LABEL.upper())
    assert "demo-data" in _labels(row)
    assert DEMO_LABEL in export.workspace_markdown(ws)


def test_live_export_is_not_marked_demo():
    ws = _workspace("02_procurement", accept={"S1"}, demo=False)
    assert "demo" not in export.workspace_jira_csv(ws).lower()
    assert DEMO_LABEL not in export.workspace_markdown(ws)


def test_nothing_accepted_exports_only_set_wide_questions():
    ws = _workspace("02_procurement", accept=set())
    assert not export.has_accepted(ws.req)
    assert len(_csv(ws)) == 1  # every question in set 02 concerns a story
    md = export.workspace_markdown(ws)
    assert "None accepted." in md and "Open questions: 7" in md


# --- 1. accepted with unresolved flags -------------------------------------------------


def test_flagged_story_gets_needs_review_label_and_flag_list():
    """The BA's case: S5-AC1 'every 5 minutes for up to 24 hours' is not in the notes."""
    rows = _by_id(_csv(_workspace("03_lab_results")))
    s5 = rows["S5"]
    assert export.NEEDS_REVIEW in _labels(s5)
    assert "Unresolved flags (accepted anyway):" in s5[1]
    assert "Reviewer, no invented facts: 'every 5 minutes for up to 24 hours'" in s5[1]
    assert "Python check (S5-AC1): number(s) not in the notes" in s5[1]
    assert export.NEEDS_REVIEW not in _labels(rows["S1"])
    assert "Unresolved flags" not in rows["S1"][1]


def test_flagged_non_functional_item_gets_needs_review():
    n2 = _by_id(_csv(_workspace("03_lab_results")))["N2"]
    assert export.NEEDS_REVIEW in _labels(n2)
    assert "Reviewer: not measurable" in n2[1]


def test_flags_after_edit_are_marked_as_judged_before_the_edit():
    ws = _workspace("03_lab_results")
    criterion = ws.req.criteria_for("S5")[0]
    workflow.edit_text(ws, criterion, "then", "it is retried later", "S5")
    s5 = _by_id(_csv(ws))["S5"]
    assert "Python check" not in s5[1]  # the invented number is gone
    assert "(judged before your edit)" in s5[1]  # the reviewer has not seen the new text


def test_accepting_flagged_story_returns_flags_for_the_warning():
    d = load_demo("03_lab_results")
    ws = workflow.start(d.notes, d)
    workflow.write_and_review(ws)
    flags = workflow.set_status(ws, "S5", A)
    assert len(flags) == 2 and "every 5 minutes" in flags[0]
    assert workflow.set_status(ws, "S1", A) == []
    assert workflow.set_status(ws, "S5", A) == []  # no change, no second warning
    assert workflow.set_status(ws, "S5", StoryStatus.REJECTED) == []


def test_markdown_marks_needs_review():
    md = export.workspace_markdown(_workspace("02_procurement"))
    assert "**Needs review.** Unresolved flags (accepted anyway):" in md
    assert "Reviewer, traceable: Sentence 16 is about the ERP export" in md
    assert "Python check (S4-AC1): number(s) not in the notes, possibly invented: 3" in md


# --- 2. short summary ------------------------------------------------------------------


def test_summary_is_a_short_title_and_full_text_stays_in_description():
    ws = _workspace("03_lab_results", accept={"S1", "S5"})
    rows = _by_id(_csv(ws))
    assert rows["S5"][0] == "Messages kept and retried when NHX is unavailable"
    s1 = rows["S1"]
    assert len(s1[0]) <= export.JIRA_SUMMARY_MAX and s1[0].endswith("…")
    assert s1[0] == "Validated lab results from Northfield Clinic available in the national health…"
    assert ws.req.stories[0].text in s1[1]
    assert all(len(r[0]) <= export.JIRA_SUMMARY_MAX for r in _csv(_workspace("01_maintenance")))


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("to report broken equipment", "Report broken equipment"),
        ("x" * 100, "X" + "x" * 78 + "…"),  # no space: hard cut
        ("word " * 30, "Word" + " word" * 14 + "…"),  # cut at a word boundary
    ],
)
def test_short_title(text, expected):
    story_text = text[3:] if text.startswith("to ") else text
    assert export.short_title(story_text) == expected
    assert len(export.short_title(story_text)) <= export.JIRA_SUMMARY_MAX


# --- 3. open questions -----------------------------------------------------------------


def test_open_questions_are_tasks_linked_to_their_stories():
    rows = _by_id(_csv(_workspace("03_lab_results")))
    q3 = rows["Q3"]
    assert q3[3] == "Task"
    assert _labels(q3) == ["reqpilot", "open-question", "demo-data"]
    assert "Affects stories: S5 (Messages kept and retried when NHX is unavailable)" in q3[1]
    assert "Affects: the whole set" in rows["Q1"][1]
    assert "Raised by: reviewer" in rows["R1"][1]
    assert set(k for k in rows if k[0] in "QR") == {"Q1", "Q2", "Q3", "Q4", "Q5", "R1", "R2", "R3"}


def test_questions_only_about_unaccepted_stories_are_left_out():
    rows = _by_id(_csv(_workspace("03_lab_results", accept={"S5"})))
    questions = {k for k in rows if k[0] in "QR"}
    assert "Q3" in questions  # about S5
    assert "Q4" not in questions  # about S6 only, not accepted
    assert {"Q1", "Q2", "Q5"} <= questions  # about no particular story


# --- 4. acceptance criteria column or description --------------------------------------


def test_criteria_can_go_into_the_description_instead():
    ws = _workspace("02_procurement", accept={"S2"})
    rows = _csv(ws, criteria_in_description=True)
    assert rows[0] == export.jira_columns(criteria_in_description=True)
    assert "Acceptance Criteria" not in rows[0]
    s2 = _by_id(rows)["S2"]
    assert len(s2) == len(rows[0])
    assert "Acceptance criteria:\nS2-AC1: Given a request under 5,000 EUR" in s2[1]
    assert s2[2] == "Story"


def test_criteria_column_by_default():
    rows = _csv(_workspace("02_procurement", accept={"S2"}))
    s2 = _by_id(rows)["S2"]
    assert rows[0][2] == "Acceptance Criteria"
    assert s2[2].count("\n") == 2 and "5,000 EUR" in s2[2]  # three criteria, quoted
    assert "Acceptance criteria:" not in s2[1]


def test_readme_explains_the_criteria_field_mapping():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "Acceptance Criteria" in readme and "custom field" in readme
    assert "Put acceptance criteria in the description" in readme
