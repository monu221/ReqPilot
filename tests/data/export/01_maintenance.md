# ReqPilot export: Equipment maintenance requests

> **Demo data, not real model output.** Stories, review and test cases are hand-written examples, not answers from the AI.

Accepted: 7 of 7 stories, 1 of 1 non-functional items, 0 of 0 out-of-scope items. Open questions: 8.

## User stories

### S1: As a ward nurse, I want to report broken equipment from the ward PC, so that requests are not lost.

Source: [4] Anna: nurses report broken equipment by phone today, requests often get lost; [5] want to report from the ward PC, with a photo if possible

Acceptance criteria:

- **S1-AC1** Given I am logged in on the ward PC, when I submit a request with equipment, location and description, then the request is saved and I see a reference number.
- **S1-AC2** Given I am creating a request, when I attach a photo, then the photo is stored with the request.
- **S1-AC3** Given a required field is empty, when I submit, then the request is not saved and the missing field is shown.

Test cases:

| Id | Criterion | Title | Preconditions | Steps | Expected |
| --- | --- | --- | --- | --- | --- |
| T1 | S1-AC1 | Submit a complete request | Nurse is logged in on a ward PC | Open the new request form → Enter equipment, location and description → Submit | The request is saved and a reference number is shown. |
| T2 | S1-AC2 | Attach a photo | Nurse is creating a request | Attach a photo → Submit the request → Open the saved request | The photo is stored with the request. |
| T3 | S1-AC3 | Missing required field | Nurse is creating a request | Leave the location empty → Submit | The request is not saved and the location field is marked as missing. |

### S2: As a biomedical engineer, I want requests to be prioritised with life-support equipment first, so that critical equipment is repaired first.

Source: [6] Ravi: engineers need a priority, life-support equipment first

Acceptance criteria:

- **S2-AC1** Given a request for life-support equipment, when it is submitted, then it gets the highest priority.

Test cases:

| Id | Criterion | Title | Preconditions | Steps | Expected |
| --- | --- | --- | --- | --- | --- |
| T4 | S2-AC1 | Life-support request gets top priority | A device is classified as life-support | Submit a request for that device → Open the engineering queue | The request has the highest priority. |

### S3: As a biomedical engineer, I want each request routed to the right engineering team (imaging, lab, general), so that the right engineers see it.

Source: [7] requests should go to the right engineering team (imaging, lab, general)

Acceptance criteria:

- **S3-AC1** Given a request for imaging equipment, when it is submitted, then it appears in the imaging team's queue.

Test cases:

| Id | Criterion | Title | Preconditions | Steps | Expected |
| --- | --- | --- | --- | --- | --- |
| T5 | S3-AC1 | Imaging request goes to imaging | – | Submit a request for an imaging device → Open the imaging team's queue | The request appears in the imaging team's queue. |

### S4: As a head of biomedical engineering, I want to see open requests per team and how long each has been open, so that I can manage the workload.

Source: [8] Ravi wants to see open requests per team and how long they have been open

Acceptance criteria:

- **S4-AC1** Given open requests exist, when I open the overview, then the overview loads quickly and shows the number of open requests per team and the age of each request.

Quality notes:

- Python check (S4-AC1): "quickly" without a number and unit; not testable

Test cases:

| Id | Criterion | Title | Preconditions | Steps | Expected |
| --- | --- | --- | --- | --- | --- |
| T6 | S4-AC1 | Overview shows open requests per team | Open requests exist for two teams | Open the overview | The number of open requests per team and the age of each request are shown. |

### S5: As a ward nurse, I want to be notified when the equipment I reported is fixed and track its repair, so that I know when it can be used again.

Source: [10] notify the nurse when the equipment is fixed

Acceptance criteria:

- **S5-AC1** Given a request I submitted, when it is marked fixed, then I receive a notification.

Quality notes:

- Reviewer, single goal: 'is fixed and track its repair' joins two goals: notification and repair tracking.
- Python check (S5): goal joins two actions ("and track"); split it into two stories

Test cases:

| Id | Criterion | Title | Preconditions | Steps | Expected |
| --- | --- | --- | --- | --- | --- |
| T7 | S5-AC1 | Nurse notified when fixed | Nurse submitted a request | Engineer marks the request fixed | The nurse receives a notification. |

### S6: As an user, I want to sign in with my hospital login, so that I don't need a separate password.

Source: [9] Tom: must use the hospital login, no separate passwords

Acceptance criteria:

- **S6-AC1** Given I have a hospital account, when I open the system, then I sign in with it and no separate password is required.

Quality notes:

- Reviewer, specific role: 'user' is generic; the notes concern hospital staff signing in with the hospital login.

Test cases:

| Id | Criterion | Title | Preconditions | Steps | Expected |
| --- | --- | --- | --- | --- | --- |
| T8 | S6-AC1 | Sign in with hospital login | User has a hospital account | Open the system → Sign in with the hospital account | The user is signed in and no separate password is asked for. |

### S7: As a head of biomedical engineering, I want to receive a monthly maintenance report within 5 working days of month end, so that management sees how equipment is maintained.

Source: [11] monthly report for management, Ravi will send the format

Acceptance criteria:

- **S7-AC1** Given a month has ended, when the report is produced, then the head of biomedical engineering receives it.

Quality notes:

- Reviewer, no invented facts: 'within 5 working days of month end' is not in the notes.
- Python check (S7): number(s) not in the notes, possibly invented: 5

Test cases:

| Id | Criterion | Title | Preconditions | Steps | Expected |
| --- | --- | --- | --- | --- | --- |
| T9 | S7-AC1 | Monthly report delivered | A month has ended | Produce the monthly report | The head of biomedical engineering receives it. |

## Non-functional

- **N1** (availability) A downtime target for equipment was mentioned but not decided. Measure: not given. Source: [12] a downtime target was mentioned but not decided

## Out of scope

None accepted.

## Open questions

- **Q1** (writer) Priority owner: Who sets the priority: the nurse when reporting, or engineering on triage? Stories: S2.
- **Q2** (writer) Life-support list: How is life-support equipment identified: from an asset list, or chosen by the nurse? Stories: S2.
- **Q3** (writer) Team routing: Is a request routed by equipment type, or is the team chosen by hand? Stories: S3.
- **Q4** (writer) Meaning of fixed: What counts as fixed: repaired, tested, or returned to the ward? Stories: S5.
- **Q5** (writer) Report format: What format will the monthly report have? Ravi will send it. Stories: S7.
- **Q6** (writer) Downtime target: What is the downtime target, and who decides it?
- **R1** (reviewer) Notification channel: How should the nurse be notified: email, in the system, or on the ward PC? Stories: S5.
- **R2** (reviewer) Report recipients: Who receives the monthly report, and when? Stories: S7.

## Traceability

| Sentence | Item | Criterion | Test case |
| --- | --- | --- | --- |
| 4 | S1 | S1-AC1 | T1 |
| 4 | S1 | S1-AC2 | T2 |
| 4 | S1 | S1-AC3 | T3 |
| 5 | S1 | S1-AC1 | T1 |
| 5 | S1 | S1-AC2 | T2 |
| 5 | S1 | S1-AC3 | T3 |
| 6 | S2 | S2-AC1 | T4 |
| 7 | S3 | S3-AC1 | T5 |
| 8 | S4 | S4-AC1 | T6 |
| 10 | S5 | S5-AC1 | T7 |
| 9 | S6 | S6-AC1 | T8 |
| 11 | S7 | S7-AC1 | T9 |
| 12 | N1 | – | – |

Gaps:

- none
