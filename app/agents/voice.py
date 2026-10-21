"""Speech-to-text via Cohere Transcribe (Canadian model).

Cohere Transcribe accepts flac/mp3/mpeg/mpga/ogg/wav (NOT webm), one pre-specified language, up to
25 MB. The frontend records 16 kHz mono WAV, so no server-side transcoding is needed. With no
COHERE_API_KEY the transcriber reports unavailable instead of crashing.
"""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass

from app.config import get_settings

log = logging.getLogger(__name__)

MODEL = "cohere-transcribe-03-2026"


@dataclass
class Transcript:
    text: str
    available: bool
    detail: str = ""


async def transcribe(audio_bytes: bytes, language: str = "en") -> Transcript:
    settings = get_settings()
    if not settings.cohere_api_key:
        return Transcript(text="", available=False, detail="COHERE_API_KEY not set")
    try:
        import cohere

        client = cohere.ClientV2(api_key=settings.cohere_api_key)
        audio = io.BytesIO(audio_bytes)
        audio.name = "audio.wav"  # lets the SDK infer filename / content-type
        resp = client.audio.transcriptions.create(model=MODEL, language=language, file=audio)
        text = getattr(resp, "text", None)
        if text is None and isinstance(resp, dict):
            text = resp.get("text", "")
        return Transcript(text=text or "", available=True)
    except Exception as exc:  # noqa: BLE001
        log.info("Cohere transcribe unavailable (%s).", type(exc).__name__)
        return Transcript(text="", available=False, detail=type(exc).__name__)
