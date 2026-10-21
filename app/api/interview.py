"""Voice interview + frontend-serving routes."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.agents.voice import transcribe
from app.domain.interview import FIELD_INDEX, QUESTIONS, parse_answer
from app.security.auth import Principal, get_current_user

router = APIRouter()
WEB_DIR = Path(__file__).resolve().parents[2] / "web"


@router.get("/")
async def index() -> FileResponse:
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


@router.post("/voice/transcribe")
async def voice_transcribe(
    file: UploadFile = File(...),
    user: Principal = Depends(get_current_user),
) -> dict:
    audio = await file.read()
    result = await transcribe(audio)
    return {"text": result.text, "available": result.available, "detail": result.detail}
