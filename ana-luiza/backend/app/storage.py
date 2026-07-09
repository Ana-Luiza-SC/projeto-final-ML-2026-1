from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

DISCIPLINES: dict[str, dict] = {}
ASSESSMENTS: dict[str, list[dict]] = {}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def create_discipline(payload: dict) -> dict:
    discipline_id = str(uuid4())
    now = utc_now()
    record = {"id": discipline_id, **payload, "created_at": now, "updated_at": now}
    DISCIPLINES[discipline_id] = record
    ASSESSMENTS[discipline_id] = []
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


def add_assessment(discipline_id: str, payload: dict) -> dict | None:
    if discipline_id not in DISCIPLINES:
        return None
    assessment = {"id": str(uuid4()), "discipline_id": discipline_id, **payload}
    ASSESSMENTS.setdefault(discipline_id, []).append(assessment)
    DISCIPLINES[discipline_id]["updated_at"] = utc_now()
    return assessment


def list_assessments(discipline_id: str) -> list[dict]:
    return ASSESSMENTS.get(discipline_id, [])
