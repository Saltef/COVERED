"""Voice interview + frontend-serving routes."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.agents import tts
from app.agents.voice import transcribe
from app.domain.interview import FIELD_INDEX, QUESTIONS, parse_answer
from app.security.auth import Principal, get_current_user

router = APIRouter()
WEB_DIR = Path(__file__).resolve().parents[2] / "web"


@router.get("/")
async def index() -> FileResponse:
    """Front door: a guided entry (what brings you here?), the before/after, and what is real vs
    demo. Routes people, and judges, into the working flows; home care lives at /homecare."""
    return FileResponse(WEB_DIR / "start.html")


@router.get("/benefits")
async def benefits() -> FileResponse:
    """The broader benefits screener (DTC, CDCP, Trillium and the rest), demoted from the front door."""
    return FileResponse(WEB_DIR / "index.html")


@router.get("/caregiver")
async def caregiver() -> FileResponse:
    return FileResponse(WEB_DIR / "caregiver.html")


@router.get("/clinician")
async def clinician() -> FileResponse:
    return FileResponse(WEB_DIR / "clinician.html")


@router.get("/agency")
async def agency() -> FileResponse:
    return FileResponse(WEB_DIR / "agency.html")


@router.get("/homecare")
async def homecare() -> FileResponse:
    """The home-care journey: Direct Funding (CILT) screening and application prep."""
    return FileResponse(WEB_DIR / "homecare.html")


@router.get("/pharmacy")
async def pharmacy() -> FileResponse:
    """Demo partner host: a mock pharmacy portal with the Covered widget embedded."""
    return FileResponse(WEB_DIR / "pharmacy.html")


@router.get("/tax")
async def tax() -> FileResponse:
    """Demo partner host: a mock tax-filing app that embeds the widget, pre-filled from the return."""
    return FileResponse(WEB_DIR / "taxsoftware.html")


@router.get("/developers")
async def developers() -> FileResponse:
    """Developer docs: the embed snippet and the v1 API contract."""
    return FileResponse(WEB_DIR / "developers.html")


@router.get("/interview/script")
async def interview_script() -> list[dict]:
    return [
        {"id": q.id, "field": q.field, "prompt": q.prompt,
         "type": q.type, "unit": q.unit, "spell_check": q.spell_check}
        for q in QUESTIONS
    ]


class ParseIn(BaseModel):
    field: str
    text: str


@router.post("/interview/parse")
async def interview_parse(body: ParseIn, user: Principal = Depends(get_current_user)) -> dict:
    q = FIELD_INDEX.get(body.field)
    if not q:
        return {"error": f"unknown field: {body.field}"}
    pr = parse_answer(q, body.text)
    return {
        "field": pr.field,
        "value": pr.value,
        "confirmation": pr.confirmation,
        "needs_clarification": pr.needs_clarification,
    }


class SpeakIn(BaseModel):
    text: str


@router.post("/voice/speak")
async def voice_speak(body: SpeakIn, user: Principal = Depends(get_current_user)) -> Response:
    """Return natural neural audio (MP3) for the given text, or 204 when no TTS provider is
    configured so the frontend falls back to the browser voice."""
    audio = tts.synthesize(body.text)
    if not audio:
        return Response(status_code=204)
    return Response(content=audio, media_type="audio/mpeg",
                    headers={"Cache-Control": "no-store"})


@router.post("/voice/transcribe")
async def voice_transcribe(
    file: UploadFile = File(...),
    user: Principal = Depends(get_current_user),
) -> dict:
    audio = await file.read()
    result = await transcribe(audio)
    return {"text": result.text, "available": result.available, "detail": result.detail}
