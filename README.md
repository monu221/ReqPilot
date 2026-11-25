# ReqPilot

ReqPilot turns meeting notes into reviewed user stories, acceptance criteria, open questions and test cases, with a traceability matrix. See [docs/product-brief.md](docs/product-brief.md), [docs/method.md](docs/method.md) and [docs/plan.md](docs/plan.md).

Status: repo skeleton (M0).

## Setup

Requires Python 3.12.

```
python -m venv .venv
.venv\Scripts\activate          # Windows; on Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"
copy .env.example .env          # then add GROQ_API_KEY; .env is git-ignored
```

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
