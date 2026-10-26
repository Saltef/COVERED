"""Neural TTS: provider selection and graceful fallback. httpx is mocked, so these run offline
and pin that no key means no audio (the frontend then uses the browser voice), ElevenLabs wins
when both keys are set, and the endpoint returns 204 when TTS is off."""
from __future__ import annotations

import httpx
from fastapi.testclient import TestClient

from app.agents import tts
from app.config import Settings, get_settings
from app.main import app


class _Resp:
    def __init__(self, content=b"MP3DATA"):
        self.content = content

    def raise_for_status(self):
        pass


def _fake_client(calls):
    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def post(self, url, headers=None, json=None):
            calls.append({"url": url, "headers": headers, "json": json})
            return _Resp()
    return FakeClient


def _settings(**over):
    base = dict(elevenlabs_api_key="", openai_api_key="", app_env="development")
    base.update(over)
    return Settings(**base)


def test_no_key_means_no_audio(monkeypatch):
    monkeypatch.setattr(tts, "get_settings", lambda: _settings())
    assert tts.available() is False
    assert tts.synthesize("hello") is None


def test_elevenlabs_preferred_when_both_set(monkeypatch):
    calls = []
    monkeypatch.setattr(httpx, "Client", _fake_client(calls))
    monkeypatch.setattr(tts, "get_settings",
                        lambda: _settings(elevenlabs_api_key="e", openai_api_key="o",
                                          elevenlabs_voice_id="VID"))
    out = tts.synthesize("Which province do you live in?")
    assert out == b"MP3DATA"
    assert "elevenlabs.io" in calls[0]["url"] and "VID" in calls[0]["url"]
    assert calls[0]["headers"]["xi-api-key"] == "e"


def test_openai_used_when_only_openai(monkeypatch):
    calls = []
    monkeypatch.setattr(httpx, "Client", _fake_client(calls))
    monkeypatch.setattr(tts, "get_settings", lambda: _settings(openai_api_key="o"))
    out = tts.synthesize("hello")
    assert out == b"MP3DATA"
    assert "openai.com" in calls[0]["url"]
    assert calls[0]["json"]["input"] == "hello"


def test_endpoint_204_without_provider(monkeypatch):
    # The real settings in the test env have no TTS key, so the endpoint returns 204.
    get_settings.cache_clear()
    c = TestClient(app)
    r = c.post("/voice/speak", json={"text": "hello"})
    assert r.status_code == 204
