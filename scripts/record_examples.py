"""Record REAL model output for the bundled examples. MAKES LIVE GROQ CALLS.

Not run in CI and not run by tests. Needs GROQ_API_KEY in .env. Run from the repo root:

    python scripts/record_examples.py --live [set ...]

Per note set it makes 3 calls (writer, reviewer, test cases for all stories, which it
accepts for the recording), counted against the limits in config.yaml. It waits between
calls to stay inside the free tier's tokens-per-minute limit. Output goes to
examples/recorded/<set>/<kind>.json with "fake": false and "source": "live". The API key is
only sent as a request header and never written to disk.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from reqpilot import llm, reviewer, testcases, writer  # noqa: E402
from reqpilot.config import get_config  # noqa: E402
from reqpilot.demo import NOTES_DIR  # noqa: E402
from reqpilot.models import StoryStatus  # noqa: E402
from reqpilot.notes import split_notes  # noqa: E402

OUT_DIR = ROOT / "examples" / "recorded"
PAUSE_S = 20


class Capture(llm.httpx2.HTTPTransport):
    """Passes requests to the network and keeps the last answer's content."""

    last_content: str | None = None

    def handle_request(self, request):
        response = super().handle_request(request)
        body = response.read()
        try:
            self.last_content = json.loads(body)["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError):
            self.last_content = None
        headers = {
            k: v
            for k, v in response.headers.items()
            if k.lower() not in ("content-encoding", "content-length", "transfer-encoding")
        }
        return llm.httpx2.Response(response.status_code, headers=headers, content=body)


def save(set_name: str, kind: str, content: str | None) -> None:
    path = OUT_DIR / set_name / f"{kind}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "fake": False,
        "source": "live",
        "label": "Recorded model output",
        "model": get_config().llm.groq.model,
        "recorded_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "set": set_name,
        "kind": kind,
        "content": json.loads(content) if content else None,
    }
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"  saved {path.relative_to(ROOT)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--live", action="store_true", help="required: confirms live calls")
    parser.add_argument("sets", nargs="*", help="note set names; default: all in data/notes")
    args = parser.parse_args()
    if not args.live:
        print("Refusing to run without --live: this script makes real Groq calls.")
        return 2
    names = args.sets or sorted(p.stem for p in NOTES_DIR.glob("*.txt"))
    transport = Capture()
    client = llm.make_client(transport=transport)
    limiter, session = llm.CallLimiter(), llm.LlmSession()
    for name in names:
        print(name)
        sentences = split_notes((NOTES_DIR / f"{name}.txt").read_text(encoding="utf-8"))
        limiter.reserve(session)
        req = writer.write(sentences, client)
        save(name, "writer", transport.last_content)
        time.sleep(PAUSE_S)
        limiter.reserve(session)
        reviewer.review(sentences, req, client)
        save(name, "reviewer", transport.last_content)
        time.sleep(PAUSE_S)
        for s in req.stories:
            s.status = StoryStatus.ACCEPTED
        limiter.reserve(session)
        testcases.generate(req, client)
        save(name, "test_cases", transport.last_content)
        time.sleep(PAUSE_S)
    print(f"Calls used this run: {session.calls}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
