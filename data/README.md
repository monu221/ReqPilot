# Data

## Where it comes from

The meeting notes are **fictional**. All organisations, people and systems in them are invented (for example "Northfield Clinic" and "NHX"). The project owner based them on their own experience as a business analyst. They do not come from any real project, client or patient.

The notes and the gold files were **drafted with AI help, then reviewed and edited by the project owner**. The evaluation report says the same thing.

Because the developer wrote both the notes and the gold answers, the evaluation measures the tool against one analyst's judgement. It is not an independent benchmark.

## Layout

| Folder | Content |
| --- | --- |
| `notes/` | One meeting-note set per file, plain text |
| `gold/` | The hand-written answer for the note set with the same file name |

Each gold file holds these sections, in this order. Every gold file has every section. A section with nothing in it reads `none stated`, for example `NON-FUNCTIONAL: none stated`.

Gold files are the reference answer, so they must also meet the quality rules in [method.md](../docs/method.md) §2.

- `STORY n:` written as "As a …, I want …, so that …", followed by `ACn:` Given/When/Then acceptance criteria
- `NON-FUNCTIONAL:` quality requirements such as volume, latency or availability
- `OUT OF SCOPE (...):` things the notes mention that the system will deliberately not do
- `OPEN QUESTIONS:` facts the notes leave open that a BA would have to clarify

## Sets

| Set | Topic | Stories | Status |
| --- | --- | --- | --- |
| 01_maintenance | Equipment maintenance requests | 6 | Complete |
| 02_procurement | Purchase request approvals | 7 | Complete |
| 03_lab_results | Lab results to a national health record | 6 | Complete |

Three sets are enough to build with. The owner will add more before the final evaluation, with a target of 6.
