"""Tests for the .env loader."""

import os

from cultural_signal_graph.config import load_dotenv


def test_load_dotenv_sets_vars(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# a comment\nDEEPSEEK_API_KEY=sk-test-123\nQUOTED=\"hello world\"\n\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("QUOTED", raising=False)
    load_dotenv(env_file)
    assert os.environ["DEEPSEEK_API_KEY"] == "sk-test-123"
    assert os.environ["QUOTED"] == "hello world"


def test_load_dotenv_does_not_override_existing(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("DEEPSEEK_API_KEY=sk-from-file\n", encoding="utf-8")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-already-set")
    load_dotenv(env_file)
    assert os.environ["DEEPSEEK_API_KEY"] == "sk-already-set"
