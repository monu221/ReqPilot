# ReqPilot

ReqPilot turns meeting notes into reviewed user stories, acceptance criteria, open questions and test cases, with a traceability matrix. See [docs/product-brief.md](docs/product-brief.md), [docs/method.md](docs/method.md) and [docs/plan.md](docs/plan.md).

Status: M0–M6 built. The writer, reviewer and test cases run against **fake responses** until live calls are recorded; the bundled examples are labelled "demo data, not real model output".

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
