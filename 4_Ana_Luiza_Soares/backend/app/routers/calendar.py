from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response

from app import storage
from app.schemas import (
    AcademicEventCreate,
    AcademicEventRead,
    AcademicEventUpdate,
    CalendarEventStatus,
    CalendarEventType,
    CalendarExtractionPreviewResponse,
    CalendarPreviewConfirmRequest,
    CalendarPreviewConfirmResponse,
)
from app.services.calendar_events import CalendarExtractionError, build_event_extraction_preview, confirm_event_preview

router = APIRouter(prefix="/api", tags=["calendar"])


def _ensure_discipline(discipline_id: UUID) -> None:
    if storage.get_discipline(str(discipline_id)) is None:
        raise HTTPException(404, "Disciplina não encontrada.")


def _event_or_404(event_id: UUID) -> dict:
    event = storage.get_event(str(event_id))
    if event is None:
        raise HTTPException(404, "Evento não encontrado.")
    return event


@router.get("/calendar/events", response_model=list[AcademicEventRead])
def list_calendar_events(
    start_at: datetime = Query(..., description="Início do intervalo."),
    end_at: datetime = Query(..., description="Fim do intervalo."),
    discipline_id: UUID | None = None,
    event_type: CalendarEventType | None = None,
    status: CalendarEventStatus | None = None,
):
    if end_at < start_at:
        raise HTTPException(422, "Data final deve ser posterior à inicial.")
    if discipline_id:
        _ensure_discipline(discipline_id)
    return storage.list_events(start_at=start_at, end_at=end_at, discipline_id=str(discipline_id) if discipline_id else None, event_type=event_type, status=status)


@router.get("/calendar/events/upcoming", response_model=list[AcademicEventRead])
def upcoming_calendar_events(limit: int = Query(default=8, ge=1, le=30)):
    return storage.upcoming_events(limit=limit)


@router.get("/calendar/events/{event_id}", response_model=AcademicEventRead)
def get_calendar_event(event_id: UUID):
    return _event_or_404(event_id)


@router.post("/calendar/events", response_model=AcademicEventRead, status_code=201)
def create_calendar_event(payload: AcademicEventCreate):
    try:
        return storage.create_event(payload.model_dump(mode="json"))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.patch("/calendar/events/{event_id}", response_model=AcademicEventRead)
def update_calendar_event(event_id: UUID, payload: AcademicEventUpdate):
    try:
        event = storage.update_event(str(event_id), payload.model_dump(mode="json", exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    if event is None:
        raise HTTPException(404, "Evento não encontrado.")
    return event


@router.post("/calendar/events/{event_id}/confirm", response_model=AcademicEventRead)
def confirm_calendar_event(event_id: UUID):
    event = storage.set_event_status(str(event_id), "confirmed")
    if event is None:
        raise HTTPException(404, "Evento não encontrado.")
    return event


@router.post("/calendar/events/{event_id}/complete", response_model=AcademicEventRead)
def complete_calendar_event(event_id: UUID):
    event = storage.set_event_status(str(event_id), "completed")
    if event is None:
        raise HTTPException(404, "Evento não encontrado.")
    return event


@router.post("/calendar/events/{event_id}/cancel", response_model=AcademicEventRead)
def cancel_calendar_event(event_id: UUID):
    event = storage.set_event_status(str(event_id), "cancelled")
    if event is None:
        raise HTTPException(404, "Evento não encontrado.")
    return event


@router.delete("/calendar/events/{event_id}", status_code=204)
def delete_calendar_event(event_id: UUID):
    if not storage.delete_event(str(event_id)):
        raise HTTPException(404, "Evento não encontrado.")
    return Response(status_code=204)


@router.post("/disciplines/{discipline_id}/calendar/extract-preview", response_model=CalendarExtractionPreviewResponse)
def extract_calendar_preview(discipline_id: UUID):
    _ensure_discipline(discipline_id)
    try:
        return build_event_extraction_preview(str(discipline_id))
    except CalendarExtractionError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/disciplines/{discipline_id}/calendar/confirm-preview", response_model=CalendarPreviewConfirmResponse)
def confirm_calendar_preview(discipline_id: UUID, payload: CalendarPreviewConfirmRequest):
    _ensure_discipline(discipline_id)
    try:
        created, skipped = confirm_event_preview(str(discipline_id), str(payload.preview_id), payload.draft_events)
        return {"created_events": created, "skipped_events": skipped, "created_count": len(created)}
    except CalendarExtractionError as exc:
        raise HTTPException(422, str(exc)) from exc
