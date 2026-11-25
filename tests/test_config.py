from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from reqpilot.config import DEFAULT_CONFIG_PATH, load_config


def test_repo_config_loads_with_decided_values():
    cfg = load_config()
    assert cfg.llm.provider == "groq"
    assert cfg.llm.groq.model == "openai/gpt-oss-120b"
    assert cfg.llm.calls_per_session == 20
    assert cfg.llm.calls_per_day == 100
    assert "user-friendly" in cfg.checks.vague_words
    assert "as appropriate" in cfg.checks.vague_words
    assert {"fast", "quickly", "large"} <= set(cfg.checks.performance_words)


def _write(tmp_path: Path, mutate) -> Path:
    data = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    mutate(data)
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def test_unknown_key_is_rejected(tmp_path):
    path = _write(tmp_path, lambda d: d["llm"].update(typo=1))
    with pytest.raises(ValidationError):
        load_config(path)


def test_negative_call_limit_is_rejected(tmp_path):
    path = _write(tmp_path, lambda d: d["llm"].update(calls_per_day=-1))
    with pytest.raises(ValidationError):
        load_config(path)


def test_duplicate_vague_word_is_rejected(tmp_path):
    path = _write(tmp_path, lambda d: d["checks"]["vague_words"].append("Etc."))
    with pytest.raises(ValidationError):
        load_config(path)


def test_env_var_selects_config(tmp_path, monkeypatch):
    path = _write(tmp_path, lambda d: d["llm"].update(calls_per_session=3))
    monkeypatch.setenv("REQPILOT_CONFIG", str(path))
    assert load_config().llm.calls_per_session == 3
