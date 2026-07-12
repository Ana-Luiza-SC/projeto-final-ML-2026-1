from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

DISCIPLINES: dict[str, dict] = {}
ASSESSMENTS: dict[str, list[dict]] = {}
IMPORT_PREVIEWS: dict[str, dict] = {}
COURSE_PLAN_PREVIEWS: dict[str, dict] = {}
COURSE_PLANS: dict[str, dict] = {}
ABSENCES: dict[str, list[dict]] = {}
CONTENT_EXTRACTION_PREVIEWS: dict[str, dict] = {}
CONTENT_NODES: dict[str, dict[str, dict]] = {}
ASSESSMENT_CONTENT_LINKS: dict[str, list[dict]] = {}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def create_discipline(payload: dict) -> dict:
    discipline_id = str(uuid4())
    now = utc_now()
    record = {"id": discipline_id, **payload, "created_at": now, "updated_at": now}
    DISCIPLINES[discipline_id] = record
    ASSESSMENTS[discipline_id] = []
    ABSENCES[discipline_id] = []
    CONTENT_NODES[discipline_id] = {}
    return record


def list_disciplines() -> list[dict]:
    return list(DISCIPLINES.values())


def get_discipline(discipline_id: str) -> dict | None:
    return DISCIPLINES.get(discipline_id)


def update_attendance(discipline_id: str, payload: dict) -> dict | None:
    record = get_discipline(discipline_id)
    if record is None:
        return None
    for field, value in payload.items():
        if value is not None:
            record[field] = value
    record["updated_at"] = utc_now()
    return record




def attach_sigaa_component(discipline_id: str, component: dict) -> dict | None:
    record = get_discipline(discipline_id)
    if record is None:
        return None
    now = utc_now()
    record.update(
        {
            "sigaa_code": component.get("code"),
            "sigaa_source_url": component.get("source_url"),
            "syllabus": component.get("syllabus") or "",
            "current_program": component.get("current_program") or "",
            "workload_hours": component.get("workload_hours"),
            "sigaa_cached_at": now,
            "updated_at": now,
        }
    )
    return record


def add_assessment(discipline_id: str, payload: dict) -> dict | None:
    if discipline_id not in DISCIPLINES:
        return None
    assessment = {"id": str(uuid4()), "discipline_id": discipline_id, **payload}
    ASSESSMENTS.setdefault(discipline_id, []).append(assessment)
    DISCIPLINES[discipline_id]["updated_at"] = utc_now()
    return assessment


def list_assessments(discipline_id: str) -> list[dict]:
    return ASSESSMENTS.get(discipline_id, [])


def normalize_discipline_code(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = "".join(char for char in value.upper() if char.isalnum())
    return normalized or None


def normalize_discipline_name(value: str | None) -> str | None:
    if value is None:
        return None
    return " ".join(value.casefold().strip().split()) or None


def find_discipline_by_code(code: str | None) -> dict | None:
    normalized = normalize_discipline_code(code)
    if normalized is None:
        return None
    for discipline in DISCIPLINES.values():
        if normalize_discipline_code(discipline.get("code")) == normalized:
            return discipline
    return None


def find_discipline_by_name(name: str | None) -> dict | None:
    normalized = normalize_discipline_name(name)
    if normalized is None:
        return None
    for discipline in DISCIPLINES.values():
        if normalize_discipline_name(discipline.get("name")) == normalized:
            return discipline
    return None


def save_import_preview(preview: dict) -> dict:
    IMPORT_PREVIEWS[str(preview["preview_id"])] = preview
    return preview


def get_import_preview(preview_id: str) -> dict | None:
    preview = IMPORT_PREVIEWS.get(preview_id)
    if preview is None:
        return None
    expires_at = preview.get("expires_at")
    if expires_at is not None and expires_at <= utc_now():
        IMPORT_PREVIEWS.pop(preview_id, None)
        return None
    return preview


def delete_import_preview(preview_id: str) -> None:
    IMPORT_PREVIEWS.pop(preview_id, None)


def cleanup_expired_import_previews() -> int:
    now = utc_now()
    expired = [key for key, value in IMPORT_PREVIEWS.items() if value.get("expires_at") and value["expires_at"] <= now]
    for key in expired:
        IMPORT_PREVIEWS.pop(key, None)
    return len(expired)



def get_assessment(discipline_id: str, assessment_id: str) -> dict | None:
    return next((item for item in list_assessments(discipline_id) if item["id"] == assessment_id), None)


def update_assessment(discipline_id: str, assessment_id: str, payload: dict) -> dict | None:
    item = get_assessment(discipline_id, assessment_id)
    if item is None:
        return None
    item.update(payload)
    DISCIPLINES[discipline_id]["updated_at"] = utc_now()
    return item


def delete_assessment(discipline_id: str, assessment_id: str) -> bool:
    items = ASSESSMENTS.get(discipline_id, [])
    ASSESSMENTS[discipline_id] = [item for item in items if item["id"] != assessment_id]
    deleted = len(items) != len(ASSESSMENTS[discipline_id])
    if deleted:
        ASSESSMENT_CONTENT_LINKS.pop(assessment_id, None)
    return deleted


def add_absence(discipline_id: str, payload: dict) -> dict:
    if any(item["date"] == payload["date"] and item["class_hours"] == payload["class_hours"] for item in ABSENCES.get(discipline_id, [])):
        raise ValueError("Já existe uma falta com a mesma data e duração.")
    item = {"id": str(uuid4()), "discipline_id": discipline_id, **payload}
    ABSENCES.setdefault(discipline_id, []).append(item)
    return item


def list_absences(discipline_id: str) -> list[dict]:
    return sorted(ABSENCES.get(discipline_id, []), key=lambda item: item["date"], reverse=True)


def update_absence(discipline_id: str, absence_id: str, payload: dict) -> dict | None:
    item = next((item for item in ABSENCES.get(discipline_id, []) if item["id"] == absence_id), None)
    if item is None:
        return None
    candidate = {**item, **payload}
    if any(other["id"] != absence_id and other["date"] == candidate["date"] and other["class_hours"] == candidate["class_hours"] for other in ABSENCES.get(discipline_id, [])):
        raise ValueError("Já existe uma falta com a mesma data e duração.")
    item.update(payload)
    return item


def delete_absence(discipline_id: str, absence_id: str) -> bool:
    items = ABSENCES.get(discipline_id, [])
    ABSENCES[discipline_id] = [item for item in items if item["id"] != absence_id]
    return len(items) != len(ABSENCES[discipline_id])


def get_content_extraction_preview(preview_id: str) -> dict | None:
    preview = CONTENT_EXTRACTION_PREVIEWS.get(preview_id)
    if preview and preview["expires_at"] <= utc_now():
        CONTENT_EXTRACTION_PREVIEWS.pop(preview_id, None)
        return None
    return preview


def delete_content_extraction_preview(preview_id: str) -> None:
    CONTENT_EXTRACTION_PREVIEWS.pop(preview_id, None)


def save_course_plan(discipline_id: str, payload: dict) -> dict:
    record = {**payload, "discipline_id": discipline_id, "confirmed_at": utc_now()}
    COURSE_PLANS[discipline_id] = record
    if record.get("workload_hours") is not None:
        DISCIPLINES[discipline_id]["workload_hours"] = record["workload_hours"]
    return record
