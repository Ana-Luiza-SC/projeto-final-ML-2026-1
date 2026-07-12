from __future__ import annotations

import tempfile
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, Response, UploadFile

from app import storage
from app.schemas import CoursePlanConfirmRequest, CoursePlanData, CoursePlanPreviewResponse
from app.services.course_plan import CoursePlanError, build_preview

router = APIRouter(prefix="/api/disciplines/{discipline_id}/course-plan", tags=["course-plan"])


def ensure_discipline(discipline_id: UUID) -> None:
    if storage.get_discipline(str(discipline_id)) is None:
        raise HTTPException(404, "Disciplina não encontrada.")


@router.post("/preview", response_model=CoursePlanPreviewResponse)
async def preview_course_plan(discipline_id: UUID, file: UploadFile = File(...)):
    ensure_discipline(discipline_id)
    path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(prefix="estudaunb-plan-", suffix=".pdf", delete=False) as temp:
            path = Path(temp.name)
            total = 0
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > 10 * 1024 * 1024:
                    raise CoursePlanError("PDF acima de 10 MiB.")
                temp.write(chunk)
        return build_preview(path, str(discipline_id))
    except CoursePlanError as exc:
        raise HTTPException(422, str(exc)) from exc
    finally:
        await file.close()
        if path:
            path.unlink(missing_ok=True)


@router.post("/confirm", response_model=CoursePlanData)
def confirm_course_plan(discipline_id: UUID, payload: CoursePlanConfirmRequest):
    ensure_discipline(discipline_id)
    preview = storage.COURSE_PLAN_PREVIEWS.get(str(payload.preview_id))
    if not preview or preview["discipline_id"] != str(discipline_id) or preview["expires_at"] <= storage.utc_now():
        raise HTTPException(404, "Pré-visualização expirada ou inexistente.")
    record = storage.save_course_plan(str(discipline_id), payload.data.model_dump(mode="json"))
    for assessment in payload.data.assessments:
        if assessment.status == "recognized":
            storage.add_assessment(str(discipline_id), {
                "name": assessment.name, "date": assessment.date, "weight": assessment.weight,
                "grade": None, "topics": assessment.topics, "notes": None,
                "source": "course_plan", "status": "planned",
            })
    storage.COURSE_PLAN_PREVIEWS.pop(str(payload.preview_id), None)
    return record


@router.get("", response_model=CoursePlanData | None)
def get_course_plan(discipline_id: UUID):
    ensure_discipline(discipline_id)
    return storage.COURSE_PLANS.get(str(discipline_id))


@router.delete("", status_code=204)
def delete_course_plan(discipline_id: UUID):
    ensure_discipline(discipline_id)
    storage.COURSE_PLANS.pop(str(discipline_id), None)
    return Response(status_code=204)
