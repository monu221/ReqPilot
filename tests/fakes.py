"""Helpers for tests that use FAKE responses (never the network)."""

from pathlib import Path

from reqpilot import llm
from reqpilot.config import REPO_ROOT

FAKE_DIR = REPO_ROOT / "tests" / "data" / "fake"
DEMO_DIR = REPO_ROOT / "examples" / "demo"


def fake(name: str) -> dict:
    """An error-case fake from tests/data/fake."""
    return llm.load_fake(FAKE_DIR / f"{name}.json")


def demo(set_name: str, kind: str) -> dict:
    """A demo fake from examples/demo."""
    return llm.load_fake(DEMO_DIR / set_name / f"{kind}.json")


def client(*responses: dict) -> tuple[llm.GroqClient, llm.FakeTransport]:
    transport = llm.FakeTransport(*responses)
    return llm.make_client(key="fake-key", transport=transport, max_retries=0), transport


def all_fake_files() -> list[Path]:
    return sorted([*FAKE_DIR.glob("*.json"), *DEMO_DIR.glob("*/*.json")])
