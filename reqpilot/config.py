"""Load and validate config.yaml."""

from __future__ import annotations

import os
from functools import cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = REPO_ROOT / "config.yaml"


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class GroqLlm(_Frozen):
    model: str
    max_tokens: int = Field(gt=0)
    reasoning_effort: Literal["low", "medium", "high"]


class Llm(_Frozen):
    provider: Literal["groq"]
    groq: GroqLlm
    calls_per_session: int = Field(ge=0)
    calls_per_day: int = Field(ge=0)
    counter_file: Path


def _clean_words(words: tuple[str, ...]) -> tuple[str, ...]:
    cleaned = tuple(w.strip().lower() for w in words)
    if any(not w for w in cleaned):
        raise ValueError("word lists must not contain empty entries")
    if len(set(cleaned)) != len(cleaned):
        raise ValueError("word lists must not contain duplicates")
    return cleaned


class Checks(_Frozen):
    vague_words: tuple[str, ...] = Field(min_length=1)
    performance_words: tuple[str, ...] = Field(min_length=1)
    action_verbs: tuple[str, ...] = Field(min_length=1)

    _clean = field_validator("vague_words", "performance_words", "action_verbs")(_clean_words)


class Config(_Frozen):
    llm: Llm
    checks: Checks


def load_config(path: Path | str | None = None) -> Config:
    """Load a config file. Defaults to $REQPILOT_CONFIG, then the repo's config.yaml."""
    path = Path(path or os.environ.get("REQPILOT_CONFIG") or DEFAULT_CONFIG_PATH)
    with path.open(encoding="utf-8") as f:
        return Config.model_validate(yaml.safe_load(f))


@cache
def get_config() -> Config:
    """The default config, loaded once."""
    return load_config()
