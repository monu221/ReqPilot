"""ReqPilot app: meeting notes -> reviewed stories -> test cases -> traceability -> export.

Run from the repo root:  streamlit run app/streamlit_app.py
"""

from __future__ import annotations

import streamlit as st

from reqpilot import llm, workflow
from reqpilot.checks import findings_by_item
from reqpilot.demo import DEMO_LABEL, demo_names, load_demo
from reqpilot.models import StoryStatus
from reqpilot.reviewer import compare

st.set_page_config(page_title="ReqPilot", layout="wide")

OWN = "My own notes"
STATUS_LABELS = {StoryStatus.DRAFT: "Undecided", StoryStatus.ACCEPTED: "Accept",
                 StoryStatus.REJECTED: "Reject"}  # fmt: skip
MARK = {True: "pass", False: "FAIL", None: "–"}


def _state():
    ss = st.session_state
    ss.setdefault("llm_session", llm.LlmSession())
    ss.setdefault("ws", None)
    ss.setdefault("ws_source", None)
    return ss


def _limiter() -> llm.CallLimiter:
    return workflow.make_limiter()


def _run(action, *args) -> bool:
    try:
        action(*args)
        return True
    except (llm.LlmError, ValueError) as e:
        st.error(str(e))
        return False


# --------------------------------------------------------------------------- sidebar

ss = _state()
demos = {load_demo(n).title + " (demo)": n for n in demo_names()}
with st.sidebar:
    st.title("ReqPilot")
    source = st.radio("Start from", [*demos, OWN], key="source")
    st.divider()
    per_session, per_day = _limiter().left(ss.llm_session)
    st.caption(f"AI calls left: **{per_session}** this session, **{per_day}** today.")
    st.caption("Demo sets make no AI call and need no API key.")

# --------------------------------------------------------------------------- step 1: notes

st.header("1. Meeting notes")
if source in demos:
    demo = load_demo(demos[source])
    st.warning(f"**{DEMO_LABEL}.** The stories, review and test cases for this set are "
               "hand-written examples, not answers from the AI.", icon="⚠️")  # fmt: skip
    st.text_area("Notes", demo.notes, height=260, disabled=True)
    notes = demo.notes
else:
    demo = None
    uploaded = st.file_uploader("Upload a text file", type=["txt", "md"])
    initial = uploaded.getvalue().decode("utf-8", errors="replace") if uploaded else ""
    notes = st.text_area("Or paste your notes", initial, height=260, key=f"own-{bool(uploaded)}")

if ss.ws_source != (source, notes):
    try:
        ss.ws = workflow.start(notes, demo)
    except ValueError as e:
        st.error(str(e))
        st.stop()
    ss.ws_source = (source, notes)
ws: workflow.Workspace = ss.ws

with st.expander(f"Numbered sentences ({len(ws.sentences)})"):
    st.dataframe(
        [{"#": s.number, "Sentence": s.text, "Header": "yes" if s.is_header else ""}
         for s in ws.sentences],
        hide_index=True, width="stretch",
    )  # fmt: skip

label = "Load demo stories (no AI call)" if ws.is_demo else "Write and review stories (2 AI calls)"
if st.button(label, type="primary", disabled=not ws.sentences):
    with st.spinner("Writing and reviewing ..."):
        if _run(workflow.write_and_review, ws, _limiter(), ss.llm_session):
            st.rerun()  # so the sidebar shows the calls just used

for w in ws.warnings:
    st.warning(w)

if ws.req is None:
    st.stop()
req = ws.req
findings = ws.findings()
by_item = findings_by_item(findings)

# --------------------------------------------------------------------------- step 2: review

st.header("2. Stories, review and decisions")
if ws.is_demo:
    st.caption(f"⚠️ {DEMO_LABEL}.")
fails = [s.id for s in req.stories if ws.review and s.id in ws.review.results
         and not ws.review.results[s.id].passed]  # fmt: skip
disagreements = sum(
    r.disagrees for s in req.stories if ws.review for r in compare(s.id, ws.review, findings)
)
c1, c2, c3, c4 = st.columns(4)
c1.metric("Stories", len(req.stories))
c2.metric("Failed by reviewer", len(fails) if ws.review else "–")
c3.metric("Flagged by Python checks", len({f.story_id for f in findings if f.story_id}))
c4.metric("Reviewer and Python disagree", disagreements if ws.review else "–")

b1, b2, _ = st.columns([1, 1, 4])
if b1.button("Accept all stories"):
    for s in req.stories:
        workflow.set_status(ws, s.id, StoryStatus.ACCEPTED)
if b2.button("Reset decisions"):
    for s in [*req.stories, *req.non_functional, *req.out_of_scope]:
        workflow.set_status(ws, s.id, StoryStatus.DRAFT)

text_of = {s.number: s.text for s in ws.sentences}
flagged_stories = {f.story_id for f in findings if f.story_id}
k = f"w{ws.uid}"


def _decision(item_id: str, status: StoryStatus) -> None:
    choice = st.radio(
        "Decision", list(STATUS_LABELS), index=list(STATUS_LABELS).index(status),
        format_func=STATUS_LABELS.get, horizontal=True, key=f"{k}-{item_id}-{status}-status",
    )  # fmt: skip
    if choice != status:
        workflow.set_status(ws, item_id, choice)
        st.rerun()


for story in req.stories:
    result = ws.review.results.get(story.id) if ws.review else None
    flagged = (result is not None and not result.passed) or story.id in flagged_stories
    flag = " ⚠" if flagged else ""
    with st.expander(f"{story.id} [{STATUS_LABELS[story.status]}]{flag} — {story.text}"):
        cols = st.columns(3)
        for col, name in zip(cols, ("role", "goal", "benefit"), strict=True):
            value = col.text_input(
                name.capitalize(), getattr(story, name), key=f"{k}-{story.id}-{name}"
            )
            if err := workflow.edit_text(ws, story, name, value, story.id):
                st.error(err)
        src = [f"[{n}] {text_of.get(n, '(not in the notes)')}" for n in story.source_sentences]
        st.markdown("**Source sentences:** " + ("  \n".join(src) if src else "_none cited_"))
        st.markdown("**Acceptance criteria**")
        for c in req.criteria_for(story.id):
            g, w_, t = st.columns(3)
            for col, name, lab in ((g, "given", "Given"), (w_, "when", "When"),
                                   (t, "then", "Then")):  # fmt: skip
                value = col.text_input(f"{c.id} {lab}", getattr(c, name), key=f"{k}-{c.id}-{name}")
                if err := workflow.edit_text(ws, c, name, value, story.id):
                    st.error(err)
        if ws.review:
            rows = compare(story.id, ws.review, findings)
            st.markdown("**Reviewer and Python checks**")
            st.dataframe(
                [{"Rule": r.rule.value.replace("_", " "), "Reviewer": MARK[r.reviewer],
                  "Python": MARK[r.python], "Agreement": r.agreement,
                  "Details": " | ".join(filter(None, [r.reviewer_reason, *r.python_messages]))}
                 for r in rows],
                hide_index=True, width="stretch",
            )  # fmt: skip
            if story.id in ws.edited:
                st.info("You edited this story after the review. The Python checks above are "
                        "up to date; the reviewer's verdict is for the original text.")  # fmt: skip
        else:
            for f in by_item.get(story.id, []) + [
                f for c in req.criteria_for(story.id) for f in by_item.get(c.id, [])
            ]:
                st.warning(f"{f.item_id}: {f.message}")
        _decision(story.id, story.status)

if req.non_functional or req.out_of_scope:
    st.subheader("Non-functional and out of scope")
for n in req.non_functional:
    verdict = ws.review.non_functional.get(n.id) if ws.review else None
    with st.expander(f"{n.id} [{STATUS_LABELS[n.status]}] {n.category}: {n.statement}"):
        st.markdown(f"**Measure:** {n.measure or '_none given_'}  \n**Sources:** "
                    + ", ".join(f"[{s}]" for s in n.source_sentences))  # fmt: skip
        if verdict:
            st.markdown(f"**Reviewer:** {'measurable' if verdict.measurable else 'not measurable'}"
                        + (f" — {verdict.reason}" if verdict.reason else ""))  # fmt: skip
        for f in by_item.get(n.id, []):
            st.warning(f"Python check: {f.message}")
        _decision(n.id, n.status)
for o in req.out_of_scope:
    with st.expander(f"{o.id} [{STATUS_LABELS[o.status]}] Out of scope: {o.statement}"):
        st.markdown(f"**Reason:** {o.reason or '–'}  \n**Sources:** "
                    + ", ".join(f"[{s}]" for s in o.source_sentences))  # fmt: skip
        for f in by_item.get(o.id, []):
            st.warning(f"Python check: {f.message}")
        _decision(o.id, o.status)

questions = req.open_questions + (ws.review.open_questions if ws.review else [])
st.subheader(f"Open questions ({len(questions)})")
st.dataframe(
    [{"Id": q.id, "From": q.origin, "Topic": q.topic, "Question": q.question,
      "Stories": ", ".join(q.related_story_ids)} for q in questions],
    hide_index=True, width="stretch",
)  # fmt: skip

# --------------------------------------------------------------------------- step 3: tests

st.header("3. Test cases")
accepted = [s for s in req.stories if s.status == StoryStatus.ACCEPTED]
st.caption(f"{len(accepted)} of {len(req.stories)} stories accepted. Test cases are written "
           "only for accepted stories.")  # fmt: skip
tlabel = ("Make test cases (demo, no AI call)" if ws.is_demo
          else "Write test cases for accepted criteria (1 AI call)")  # fmt: skip
if st.button(tlabel, disabled=not accepted):
    with st.spinner("Writing test cases ..."):
        if _run(workflow.make_test_cases, ws, _limiter(), ss.llm_session):
            st.rerun()
if ws.test_cases:
    if ws.is_demo:
        st.caption(f"⚠️ {DEMO_LABEL}.")
    st.dataframe(
        [{"Id": t.id, "Criterion": t.criterion_id, "Title": t.title,
          "Preconditions": "; ".join(t.preconditions),
          "Steps": " → ".join(t.steps), "Expected result": t.expected_result}
         for t in ws.test_cases],
        hide_index=True, width="stretch",
    )  # fmt: skip

# --------------------------------------------------------------------------- step 4: trace

st.header("4. Traceability")
matrix = ws.matrix()
if not matrix.rows:
    st.caption("Accept stories to build the matrix.")
else:
    st.dataframe(
        [{"Sentence": r.sentence or "–", "Note text": r.sentence_text, "Kind": r.kind,
          "Item": r.item_id, "Criterion": r.criterion_id, "Test case": r.test_case_id or "–"}
         for r in matrix.rows],
        hide_index=True, width="stretch",
    )  # fmt: skip
    gaps = {
        "Accepted stories without a test case": matrix.stories_without_test_cases,
        "Criteria without a test case": matrix.criteria_without_test_cases,
        "Accepted items without a source sentence": matrix.items_without_source,
        "Note sentences no accepted item uses": [
            f"[{n}] {text_of[n]}" for n in matrix.unused_sentences
        ],
    }
    for title, items in gaps.items():
        if items:
            st.markdown(f"**{title}:**  \n" + "  \n".join(map(str, items)))
    if matrix.complete:
        st.success("Every accepted story has test cases and every note sentence is used.")
