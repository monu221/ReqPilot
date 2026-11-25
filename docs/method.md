# ReqPilot – Method

## 1. Writer

Input: meeting notes as plain text, split into numbered sentences.

The writer returns, in a fixed JSON schema:

| Object | Fields |
| --- | --- |
| Story | id, role, goal, benefit, source sentence numbers |
| Acceptance criterion | id, story id, given, when, then |
| Open question | id, topic, question, related story ids |
| Non-functional item | id, category (for example volume, latency, availability, security, retention), statement, measure, source sentence numbers |
| Out-of-scope item | id, statement, reason (for example "unchanged process"), source sentence numbers |

Rules for the writer:

- Use only facts in the notes. If a needed fact is missing, write an open question instead of inventing it.
- Use the most specific role the notes name (for example "ward nurse", not "user").
- One goal per story.
- Every story must cite at least one source sentence.
- Quality requirements that apply to the whole system (volume, speed, availability, security) are non-functional items, not stories. If the notes give no measure, the measure stays empty and the writer adds an open question asking for one.
- Things the notes say stay as they are, or will not be done by the system, are out-of-scope items, not stories. Each one cites its source sentence.
- If the notes contain no non-functional or out-of-scope points, those lists stay empty.

## 2. Reviewer

A separate AI call receives the notes and the stories and checks each story against these rules:

| Rule | Failure example |
| --- | --- |
| Specific role | "As a user" when the notes name a nurse |
| Single goal | "… and also …" joins two features |
| Testable criteria | "The system is fast" with no measure |
| No vague words | "user-friendly", "etc.", "as appropriate" |
| Traceable | No source sentence, or the source does not support the story |
| No invented facts | A number, rule or role not in the notes |

The reviewer returns, per story: pass or fail per rule, a one-line reason for each failure, and extra open questions.

## 3. Python checks

Independent of the AI:

- Vague-word list (configurable in `config.yaml`).
- Criteria containing performance words ("fast", "quickly", "large") without a number and unit.
- Stories whose goal contains "and" joining two verbs.
- Numbers in stories or criteria that do not appear in the notes (possible invented fact).
- Stories with no source sentence.

## 4. Test cases and traceability

For each accepted criterion: one or more test cases with id, title, preconditions, steps and expected result. The traceability matrix lists note sentence → story → criterion → test case; any accepted story without a test case, or any note sentence never used, is shown.

## 5. Evaluation

Data: 8–10 meeting-note sets written by the project owner from real BA experience (anonymised, invented names), each with hand-written gold stories in `data/gold/`.

Measures per set:

- **Recall:** share of gold stories matched by a generated story. Matching is judged by an AI pass and spot-checked by hand; the report states how many matches were checked.
- **Invented facts:** generated statements not supported by the notes.
- **Quality pass rate:** share of generated stories passing all rules.
- **Reviewer value:** problems the reviewer flagged that the writer's output contained.

The report states the sample size and that the notes were written by the developer.
