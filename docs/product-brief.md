# ReqPilot – Product Brief

ReqPilot turns meeting notes or a rough request into reviewed user stories, acceptance criteria, open questions and test cases, with a traceability matrix, and flags what a business analyst would still need to clarify.

## Problem

Turning workshop notes into clean requirements takes a business analyst hours, and gaps (missing roles, untestable criteria, unclear business rules) are often found only in UAT.

## Users

Business analysts, product owners and project leads preparing a backlog.

## What version 1 does

1. The user pastes meeting notes or uploads a text file.
2. The AI extracts user stories (role, goal, benefit), each with 2–5 Given/When/Then acceptance criteria, linked to the sentence in the notes it came from.
3. A separate AI reviewer checks every story against quality rules and lists open questions.
4. The user edits, accepts or rejects each story.
5. Test cases are generated from accepted criteria; a traceability matrix links note sentence → story → criterion → test case.
6. Export to CSV (Jira import), Markdown and GitHub Issues.

## Out of scope for version 1

Direct Jira API integration, audio transcription, non-English notes, multi-user collaboration.

## Success metric

- Evaluated on 6 realistic note sets against expert-written gold stories: share of gold stories recovered, invented facts per set, share of generated stories passing the quality rules.
- Three bundled examples run without any AI call.

## Stack

Python 3.12, Streamlit, Pydantic, pytest, GitHub Actions. LLM provider configurable; Groq (free tier) is the default, key in `.env` as `GROQ_API_KEY`.

## Key design decisions

- Every story points to its source sentence; a story without one is flagged as possibly invented.
- The reviewer is a separate AI call, so the writer does not grade its own work.
- Vague words and missing measures are also checked in plain Python, not only by the AI.
- Nothing is exported until a human accepts it.
- Tests use recorded AI responses; CI makes no live calls.
- Per-session and daily call limits protect the free quota.
