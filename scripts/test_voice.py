"""Verify the Cohere transcription path end-to-end with a generated WAV (needs COHERE_API_KEY).

    python scripts/test_voice.py

A synthetic tone isn't speech, so `text` will be empty — but `available: True` proves the SDK call,
the WAV format, and auth all work. The real words-to-text check is the live mic in the browser.
"""
from __future__ import annotations

import asyncio
import io
import math
import struct
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from app.agents.voice import transcribe  # noqa: E402


def make_wav(seconds: float = 1.0, sr: int = 16000, freq: int = 220) -> bytes:
    buf = io.BytesIO()
    w = wave.open(buf, "wb")
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(sr)
    frames = bytearray()
    for i in range(int(seconds * sr)):
        frames += struct.pack("<h", int(3000 * math.sin(2 * math.pi * freq * i / sr)))
    w.writeframes(frames)
    w.close()
    return buf.getvalue()


async def main() -> None:
    result = await transcribe(make_wav())
    print("available:", result.available, "| detail:", result.detail, "| text:", repr(result.text))
    print("RESULT:", "Cohere integration OK (auth + wav accepted)" if result.available
          else "NOT working — check COHERE_API_KEY / error above")


if __name__ == "__main__":
    asyncio.run(main())
