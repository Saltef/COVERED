"""Natural text-to-speech. The browser's built-in speechSynthesis is robotic and OS-dependent;
this returns real neural audio when a provider key is set, and None otherwise so the frontend
falls back to the browser voice.

Providers, in order of preference:
  1. ElevenLabs (most natural, warm) via ELEVENLABS_API_KEY + ELEVENLABS_VOICE_ID.
  2. OpenAI TTS via OPENAI_API_KEY (OpenRouter has no audio endpoint, so this is a direct key).

Returns MP3 bytes. Degrades gracefully: any failure returns None.
"""
from __future__ import annotations

import logging

from app.config import get_settings

log = logging.getLogger(__name__)

_ELEVEN_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
_OPENAI_URL = "https://api.openai.com/v1/audio/speech"
_MAX_CHARS = 1200  # a single prompt; guards against runaway cost


def available() -> bool:
    return get_settings().tts_available


def _elevenlabs(text: str, s) -> bytes | None:
    import httpx
    url = _ELEVEN_URL.format(voice_id=s.elevenlabs_voice_id)
    headers = {"xi-api-key": s.elevenlabs_api_key, "Content-Type": "application/json"}
    body = {"text": text, "model_id": s.elevenlabs_model,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}}
    with httpx.Client(timeout=30) as c:
        r = c.post(url, headers=headers, json=body)
        r.raise_for_status()
        return r.content


def _openai(text: str, s) -> bytes | None:
    import httpx
    headers = {"Authorization": f"Bearer {s.openai_api_key}"}
    body = {"model": s.openai_tts_model, "voice": s.openai_tts_voice,
            "input": text, "response_format": "mp3"}
    with httpx.Client(timeout=30) as c:
        r = c.post(_OPENAI_URL, headers=headers, json=body)
        r.raise_for_status()
        return r.content


def synthesize(text: str) -> bytes | None:
    """Return MP3 bytes for `text`, or None if no provider is configured or the call fails."""
    text = (text or "").strip()[:_MAX_CHARS]
    if not text:
        return None
    s = get_settings()
    try:
        if s.elevenlabs_api_key:
            return _elevenlabs(text, s)
        if s.openai_api_key:
            return _openai(text, s)
    except Exception as exc:  # noqa: BLE001  never let TTS break the flow
        log.info("TTS failed (%s); frontend falls back to the browser voice.", type(exc).__name__)
    return None
