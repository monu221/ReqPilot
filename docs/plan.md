# ReqPilot – Plan

Scope: [product-brief.md](product-brief.md). Method: [method.md](method.md). Data: [../data/README.md](../data/README.md).

## Working rules

- **No live LLM calls until the owner says so.** Until then, all LLM code is tested against hand-written fake responses. Recording real responses (M3) waits for the go-ahead.
- CI never makes live calls. Tests replay recorded responses (the JunctionLab pattern: `tests/data/llm/*.json` plus a `record_groq.py` script that is run by hand).
- At the end of every milestone: commit, push, check that CI passes on Ubuntu and Windows, then stop.
- The API key lives only in `.env` (git-ignored). It is never printed, logged or written into a recording.
- JunctionLab (`../JunctionLab`) is read-only. Patterns are reused by copying them into this repo, never by editing that project.

## Settings (config.yaml)

| Setting | Value | Source |
| --- | --- | --- |
| `llm.provider` | `groq` | brief |
| `llm.groq.model` | `openai/gpt-oss-120b` (structured outputs) | same as JunctionLab |
| `llm.calls_per_session` | 20 | owner, 2026-11-25 |
| `llm.calls_per_day` | 100 (UTC date, counter in `var/llm_calls.json`) | owner, 2026-11-25 |
| `checks.vague_words` | list from method §3 (`user-friendly`, `etc.`, `as appropriate`, …) | method §3 |
| `checks.performance_words` | `fast`, `quickly`, `large`, … | method §3 |

A full run on one note set takes 2 calls: the writer and the reviewer. Test-case generation adds 1 more. The session limit therefore covers about 6 complete runs.

## Data model (Pydantic)

These follow the writer schema in method §1, which also covers non-functional and out-of-scope items (added 2026-11-25).

| Object | Fields |
| --- | --- |
| `Sentence` | number, text (the notes split into numbered sentences, with bullets and sub-bullets as separate sentences) |
| `Story` | id, role, goal, benefit, source sentence numbers, status (`draft` / `accepted` / `rejected`) |
| `AcceptanceCriterion` | id, story id, given, when, then |
| `OpenQuestion` | id, topic, question, related story ids, origin (`writer` / `reviewer`) |
| `NonFunctional` | id, category (volume, latency, availability, security, retention, …), statement, measure (empty if the notes give none), source sentence numbers |
| `OutOfScope` | id, statement, reason (for example "unchanged process"), source sentence numbers |
| `ReviewResult` | story id, one pass/fail per rule, a one-line reason per failure |
| `TestCase` | id, criterion id, title, preconditions, steps, expected result |

**Rules for the new objects.** A non-functional item with no measure, such as "near real time", must also produce an open question. The Python check flags it as untestable, just as it flags criteria. Out-of-scope items need a source sentence.

## Milestones

| # | Milestone | Content | Done when |
| --- | --- | --- | --- |
| M0 | Repo skeleton | `pyproject.toml` (Python 3.12), `reqpilot/` package, `config.yaml`, `.env.example`, `.gitattributes` (`eol=lf`), pytest, ruff, GitHub Actions on Ubuntu and Windows | CI is green on both systems |
| M1 | Notes and data model | Sentence splitter, Pydantic models above, a parser for the gold-file format (stories, ACs, non-functional, out-of-scope, open questions; `none stated` reads as an empty list) | Every `data/gold/*.txt` parses and has all sections. The splitter numbers every line of every note set. |
| M2 | Python checks (method §3) | Vague words, performance words without a number and unit, "and" joining two verbs in a goal, numbers missing from the notes, stories with no source sentence, unmeasured non-functional items | Unit tests cover a pass and a fail case for each check. A test checks that every gold story passes the checks, because gold is the reference answer and must meet the rules. Known gaps such as gold 03's "near real time" are expected flags on non-functional items, not on stories. |
| M3 | Writer (method §1) | Groq client with structured output (`additionalProperties: false`), call limits, error types (`LimitReached`, `LlmUnavailable`, `RateLimited`), prompt with the method §1 rules. The output includes non-functional and out-of-scope items. | Tests pass on fake responses. Real recordings are made only after the go-ahead. |
| M4 | Reviewer (method §2) | A **separate** call with its own prompt. It receives the notes and the writer's output (never the writer's reasoning) and checks the six rules for each story, plus the non-functional items for measurability. It returns pass/fail and reasons for each rule and any extra open questions. Results are shown next to the Python checks, and disagreements between the two are highlighted. | Tests pass on fake responses, including a case where the reviewer fails a story that the Python checks pass |
| M5 | Test cases and traceability (method §4) | Test cases only for accepted criteria. The matrix runs sentence → story → criterion → test case. It shows accepted stories with no test case and note sentences that nothing uses. Non-functional and out-of-scope items also appear as rows with their source sentences. | Unit tests on hand-built data |
| M6 | Streamlit app | Paste or upload notes → numbered sentences → stories with criteria, the reviewer verdict and the Python checks → edit, accept or reject each story → test cases → matrix. Calls left in the session and day are shown. | Manual check plus an app smoke test |
| M7 | Export | **CSV** (Jira import columns: Summary, Description, Acceptance Criteria, Issue Type, Labels) and **Markdown**. XLSX is optional, via openpyxl, if time allows. Only accepted items are exported. | Golden-file tests for each format |
| M8 | Bundled examples | The three note sets ship with stored writer, reviewer and test-case output and run with no API key | The examples run in CI without a key |
| M9 | Evaluation (method §5) | Runs on all the note sets available at that point (target 6). Per set it records recall against gold stories (an AI match pass, with N matches checked by hand and that N stated), invented facts, quality pass rate and reviewer value. Recall is also given for non-functional items and open questions. Out-of-scope items are checked so that none is written up as a story. The report is `docs/evaluation.md`. | The report states the sample size, that the developer wrote the notes, and that the notes and gold files were drafted with AI help and reviewed and edited by the owner |

| M10 | GitHub Issues export | Each accepted story becomes one issue: title from the goal, body with the story, criteria, test cases and source sentences, plus labels. Runs through `gh` or the REST API with a token from `.env`. A dry-run mode writes the payloads to a file. | Tests check the dry-run payloads. No live GitHub calls run in CI. |

M3, M4 and M9 need live calls for recordings and evaluation, so those steps wait for the owner's go-ahead. M0–M2, M5–M7 and the dry-run part of M10 need no calls at all.

## Data for building and evaluation

Three note sets (01–03) are enough to build with. The owner will add more before the final evaluation, with a target of **6**. This is below the 8–10 that the brief and method §5 mention. The evaluation report states the actual sample size.

## Evaluation details

- **Matching.** One AI pass per set matches generated stories to gold stories one-to-one. The owner checks by hand at least one set in full plus a sample from the others, and the report gives the numbers.
- **Invented facts.** These are counted from the Python number check plus the reviewer's "no invented facts" rule, and spot-checked by hand.
- **Reviewer value.** This counts the reviewer flags that point to a real fault in the writer's output (confirmed by hand), and separately the flags that the Python checks also caught.
- **Cost.** About 4 calls per set (3 calls plus 1 matching call), so roughly 24 calls for 6 sets. That fits within one day's limit of 100.

## Decisions

Recorded 2026-11-25.

1. Set 01 notes were refilled by the owner.
2. Gold is the reference answer and must meet the rules. Gold 01, story 6, now reads "As a hospital staff member" (it used to say "As a user").
3. Every gold file has all sections. Gold 01 and 02 say `NON-FUNCTIONAL: none stated` and `OUT OF SCOPE: none stated`.
4. method.md §1 now includes non-functional and out-of-scope items.
5. GitHub Issues export stays in v1 as the last milestone (M10).
6. Three note sets are enough to build with. The target is 6 before the final evaluation.
