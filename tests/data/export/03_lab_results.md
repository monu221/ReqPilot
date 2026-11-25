# ReqPilot export: Lab results to a national health record

> **Demo data, not real model output.** Stories, review and test cases are hand-written examples, not answers from the AI.

Accepted: 6 of 6 stories, 2 of 2 non-functional items, 1 of 1 out-of-scope items. Open questions: 8.

## User stories

### S1: As a clinician at another provider, I want validated lab results from Northfield Clinic available in the national health record, so that I can see them when treating the patient.

Source: [4] lab results stay in the hospital system today, other providers cannot see them; [5] NHX requires results sent as FHIR resources, Jonas has the spec; [6] send results automatically once the lab validates them

Acceptance criteria:

- **S1-AC1** Given a lab result is validated and the patient has consented, when validation is completed, then the result is sent to NHX as a FHIR resource as the NHX specification requires.
- **S1-AC2** Given a lab result is not yet validated, when it is saved, then it is not sent.

Test cases:

| Id | Criterion | Title | Preconditions | Steps | Expected |
| --- | --- | --- | --- | --- | --- |
| T1 | S1-AC1 | Validated result is sent as FHIR | Patient has consent recorded in the HIS | Validate a lab result → Inspect the message sent to the NHX test endpoint | A FHIR resource matching the NHX specification is received. |
| T2 | S1-AC2 | Unvalidated result is not sent | – | Save a lab result without validating it | No message is sent to NHX. |

### S2: As a data protection officer, I want results sent only for patients who have consented, so that patient data is shared lawfully.

Source: [9] Mrs. Weber: send only if the patient has consented, consent stored in the HIS

Acceptance criteria:

- **S2-AC1** Given the HIS records no consent for the patient, when a result is validated, then it is not sent and the reason is logged.

Test cases:

| Id | Criterion | Title | Preconditions | Steps | Expected |
| --- | --- | --- | --- | --- | --- |
| T3 | S2-AC1 | No consent, no message | The HIS has no consent for the patient | Validate a lab result → Check the log | Nothing is sent, and the log states missing consent as the reason. |

### S3: As a lab manager, I want a corrected result to replace the earlier version in NHX, so that no outdated or duplicate results are shown.

Source: [7] Priya: corrected results must replace the earlier version, not duplicate it

Acceptance criteria:

- **S3-AC1** Given a result was already sent, when a corrected version is validated, then NHX receives it as an update of the same result, not as a new result.

Test cases:

| Id | Criterion | Title | Preconditions | Steps | Expected |
| --- | --- | --- | --- | --- | --- |
| T4 | S3-AC1 | Correction updates the same result | A result was already sent | Correct and re-validate the result → Inspect the message sent to NHX | The message updates the existing result rather than creating a new one. |

### S4: As an integration lead, I want every message to NHX authenticated with a token, so that only authorised systems can send data.

Source: [10] every message must be authenticated, NHX uses tokens

Acceptance criteria:

- **S4-AC1** Given a message is ready, when it is transmitted, then it carries a valid NHX token.
- **S4-AC2** Given the token is invalid or expired, when a message is sent, then it is not transmitted and an error is logged.

Test cases:

| Id | Criterion | Title | Preconditions | Steps | Expected |
| --- | --- | --- | --- | --- | --- |
| T5 | S4-AC1 | Messages carry a token | A valid NHX token is configured | Send a message | The message carries a valid NHX token. |
| T6 | S4-AC2 | Invalid token blocks sending | The configured token is expired | Send a message → Check the log | The message is not transmitted and an error is logged. |

### S5: As an integration lead, I want messages kept and retried when NHX is unavailable, so that no result is lost.

Source: [11] if NHX is down, messages should not be lost, retry later

Acceptance criteria:

- **S5-AC1** Given NHX does not respond, when a message is sent, then it is retried every 5 minutes for up to 24 hours.

**Needs review.** Unresolved flags (accepted anyway):

- Reviewer, no invented facts: 'every 5 minutes for up to 24 hours' is not in the notes.
- Python check (S5-AC1): number(s) not in the notes, possibly invented: 5

Test cases:

| Id | Criterion | Title | Preconditions | Steps | Expected |
| --- | --- | --- | --- | --- | --- |
| T7 | S5-AC1 | Retry when NHX is down | The NHX test endpoint is unavailable | Validate a result → Make the endpoint available again | The message is retried and delivered once NHX responds. |

### S6: As an integration lead, I want to see messages rejected by NHX with the reason, so that the rejections can be fixed and resent.

Source: [12] Jonas: NHX can reject a message, someone must see and fix the rejections

Acceptance criteria:

- **S6-AC1** Given NHX rejects a message, when the rejection is received, then it appears in a rejection list with the reason and can be resent after correction.

Test cases:

| Id | Criterion | Title | Preconditions | Steps | Expected |
| --- | --- | --- | --- | --- | --- |
| T8 | S6-AC1 | Rejected message can be corrected and resent | The NHX test endpoint rejects a message | Open the rejection list → Correct the message → Resend | The rejection is listed with its reason, and the corrected message is resent. |

## Non-functional

- **N1** (volume) Roughly 3,000 results per day, with a peak in the morning. Measure: 3,000 results per day. Source: [13] volume roughly 3,000 results per day, peak in the morning
- **N2** (latency) Results are sent near real time. Measure: not given. Source: [14] should be "near real time", nobody defined a number

## Out of scope

- **X1** Critical results are still phoned to the doctor, as today. (unchanged process) Source: [8] Dr. Lin: critical results must still be phoned to the doctor, as today

## Open questions

- **Q1** (writer) Delivery delay: What is the maximum delay from validation to delivery that counts as 'near real time'?
- **Q2** (writer) Morning peak: How many results per hour arrive at the morning peak?
- **Q3** (writer) Retry policy: How often and for how long are messages retried, and who is alerted when retries stop? Stories: S5.
- **Q4** (writer) Rejection owner: Who owns the rejection list, and how fast must rejections be fixed? Stories: S6.
- **Q5** (writer) Go-live date: What is the confirmed national deadline?
- **R1** (reviewer) Consent withdrawal: What happens when a patient withdraws consent after a result was sent? Stories: S2.
- **R2** (reviewer) Consent check: Is consent checked per result or per patient, and how current must it be? Stories: S2.
- **R3** (reviewer) FHIR version: Which version of the NHX FHIR specification applies? Stories: S1.

## Traceability

| Sentence | Item | Criterion | Test case |
| --- | --- | --- | --- |
| 4 | S1 | S1-AC1 | T1 |
| 4 | S1 | S1-AC2 | T2 |
| 5 | S1 | S1-AC1 | T1 |
| 5 | S1 | S1-AC2 | T2 |
| 6 | S1 | S1-AC1 | T1 |
| 6 | S1 | S1-AC2 | T2 |
| 9 | S2 | S2-AC1 | T3 |
| 7 | S3 | S3-AC1 | T4 |
| 10 | S4 | S4-AC1 | T5 |
| 10 | S4 | S4-AC2 | T6 |
| 11 | S5 | S5-AC1 | T7 |
| 12 | S6 | S6-AC1 | T8 |
| 13 | N1 | – | – |
| 14 | N2 | – | – |
| 8 | X1 | – | – |

Gaps:

- Note sentences no accepted item uses: 15
