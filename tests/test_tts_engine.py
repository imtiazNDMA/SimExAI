"""Kokoro initialization configuration without loading the real model."""
import sys
from types import SimpleNamespace

from backend import tts_engine


def test_kokoro_pipeline_receives_explicit_repo_id(monkeypatch):
    observed = {}

    class FakePipeline:
        def __init__(self, **kwargs):
            observed.update(kwargs)

    monkeypatch.setattr(tts_engine, "_pipeline", None)
    monkeypatch.setenv("KOKORO_LANG", "a")
    monkeypatch.setenv("KOKORO_REPO_ID", "hexgrad/Kokoro-82M")
    monkeypatch.setitem(sys.modules, "kokoro", SimpleNamespace(KPipeline=FakePipeline))

    tts_engine._get_pipeline()

    assert observed == {
        "lang_code": "a",
        "repo_id": "hexgrad/Kokoro-82M",
    }


def test_pipeline_init_failure_degrades_instead_of_raising(monkeypatch):
    """spacy.cli.download calls sys.exit() — SystemExit must not reach the endpoint."""

    class ExitingPipeline:
        def __init__(self, **kwargs):
            raise SystemExit(1)

    monkeypatch.setattr(tts_engine, "_pipeline", None)
    monkeypatch.setattr(tts_engine, "_init_error", None)
    monkeypatch.setattr(tts_engine, "_available", True)
    monkeypatch.setitem(sys.modules, "kokoro", SimpleNamespace(KPipeline=ExitingPipeline))

    result = tts_engine.generate_speech("Flood warning issued for Sindh.")

    assert result["audio"] == ""
    assert result["timestamps"] == []
    assert "SystemExit" in result["error"]


def test_pipeline_init_failure_is_cached(monkeypatch):
    """A failed init must not retry the slow download on every request."""
    attempts = []

    class ExitingPipeline:
        def __init__(self, **kwargs):
            attempts.append(1)
            raise SystemExit(1)

    monkeypatch.setattr(tts_engine, "_pipeline", None)
    monkeypatch.setattr(tts_engine, "_init_error", None)
    monkeypatch.setitem(sys.modules, "kokoro", SimpleNamespace(KPipeline=ExitingPipeline))

    assert tts_engine._get_pipeline() is None
    assert tts_engine._get_pipeline() is None
    assert len(attempts) == 1
