# ReqPilot

ReqPilot turns meeting notes into reviewed user stories, acceptance criteria, open questions and test cases, with a traceability matrix. See [docs/product-brief.md](docs/product-brief.md), [docs/method.md](docs/method.md) and [docs/plan.md](docs/plan.md).

Status: M0–M7 built (CSV and Markdown export). The writer, reviewer and test cases run against **fake responses** until live calls are recorded; the bundled examples are labelled "demo data, not real model output".

## Setup

Requires Python 3.12.

```
python -m venv .venv
.venv\Scripts\activate          # Windows; on Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"
copy .env.example .env          # then add GROQ_API_KEY; .env is git-ignored
```

## Run the app

```
.venv\Scripts\streamlit run app\streamlit_app.py     # Windows
.venv/bin/streamlit run app/streamlit_app.py         # Linux/macOS
```

The three demo sets work without an API key and make no AI call. "My own notes" needs `GROQ_API_KEY` in `.env` and counts against the limits in `config.yaml` (20 calls per session, 100 per day).

## Importing the CSV into Jira

The CSV holds one row per item:
- each accepted story, as a **Story**;
- each accepted non-functional item, as a **Task** with the label `non-functional`;
- each open question about an accepted story (or about no particular story), as a **Task** with the label `open-question`.

Accepted items that still have reviewer or Python-check flags get the label `needs-review`, and their description lists the flags.

The columns are `Summary`, `Description`, `Acceptance Criteria`, `Issue Type` and four `Labels` columns. The Summary is a short title of up to 80 characters; the full story text is in the Description.

In Jira's CSV import, the field-mapping step lets you choose a Jira field for each column:

- Map `Summary`, `Description` and `Issue Type` to the fields of the same name, and map every `Labels` column to **Labels**.
- **`Acceptance Criteria` is not a standard Jira field.** Map it to a custom multi-line text field, such as one named "Acceptance criteria". That field must exist and be on the screen for the Story issue type, which usually means a Jira admin has to create it. If you leave the column unmapped, Jira ignores it and the criteria are lost.
- **No custom field?** In the app's export step, tick **"Put acceptance criteria in the description (no Jira custom field needed)"**. The CSV then has no `Acceptance Criteria` column, and the criteria are written into each story's Description.

Open questions name the stories they affect by their ReqPilot id (for example `S5`). Jira gives the stories new keys on import, so each story's description ends with `ReqPilot id: S5`, and you can search for that.

## Checks

```
ruff check .
ruff format --check .
pytest
```

Tests never call an LLM.

## Data

The meeting notes in `data/` are fictional. See [data/README.md](data/README.md) for where they come from.

## License

MIT, see [LICENSE](LICENSE).
