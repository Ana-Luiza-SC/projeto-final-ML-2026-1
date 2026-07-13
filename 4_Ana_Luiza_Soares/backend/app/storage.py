from __future__ import annotations
from collections.abc import MutableMapping, Iterator
from datetime import datetime, timezone
from uuid import uuid4
from bs4 import BeautifulSoup
from sqlalchemy import delete, select
from app.database import (
    SessionLocal,
    User,
    DisciplineRecord,
    AssessmentRecord,
    AcademicEventRecord,
    AbsenceRecord,
    CoursePlanRecord,
    ContentNodeRecord,
    AssessmentContentLinkRecord,
    CatalogComponent,
    ComplexityAnalysisRecord,
    current_user_id,
    decode_payload,
    encode_payload,
    init_database,
)

IMPORT_PREVIEWS: dict[str, dict] = {}
COURSE_PLAN_PREVIEWS: dict[str, dict] = {}
CONTENT_EXTRACTION_PREVIEWS: dict[str, dict] = {}
EVENT_EXTRACTION_PREVIEWS: dict[str, dict] = {}


def utc_now():
    return datetime.now(timezone.utc)


init_database()


def _owner():
    uid = current_user_id.get()
    with SessionLocal() as s:
        if s.get(User, uid) is None:
            s.add(User(id=uid, email=f"{uid}@local.invalid", password_hash="disabled"))
            s.commit()
    return uid


class RecordMap(MutableMapping):
    def __init__(self, model, group_field=None, collection="one"):
        self.model = model
        self.group_field = group_field
        self.collection = collection

    def _query(self, s, key=None):
        q = select(self.model).where(self.model.user_id == _owner())
        if key is not None:
            field = getattr(self.model, self.group_field or "id")
            q = q.where(field == key)
        return s.scalars(q).all()

    def __getitem__(self, key):
        with SessionLocal() as s:
            rows = self._query(s, key)
        if not rows and self.collection == "one":
            raise KeyError(key)
        if self.collection == "list":
            return [decode_payload(r.payload) for r in rows]
        if self.collection == "dict":
            return {r.id: decode_payload(r.payload) for r in rows}
        return decode_payload(rows[0].payload)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def __setitem__(self, key, value):
        uid = _owner()
        with SessionLocal() as s:
            if self.collection in {"list", "dict"}:
                field = getattr(self.model, self.group_field)
                s.execute(
                    delete(self.model).where(self.model.user_id == uid, field == key)
                )
                values = (
                    list(value.values()) if self.collection == "dict" else list(value)
                )
                for item in values:
                    kwargs = {
                        "id": str(item["id"]),
                        "user_id": uid,
                        "payload": encode_payload(item),
                        self.group_field: key,
                    }
                    s.add(self.model(**kwargs))
            else:
                row = s.scalar(
                    select(self.model).where(
                        self.model.user_id == uid, self.model.id == key
                    )
                )
                if row:
                    row.payload = encode_payload(value)
                    row.updated_at = utc_now()
                else:
                    s.add(
                        self.model(id=key, user_id=uid, payload=encode_payload(value))
                    )
            s.commit()

    def __delitem__(self, key):
        uid = _owner()
        with SessionLocal() as s:
            field = getattr(self.model, self.group_field or "id")
            result = s.execute(
                delete(self.model).where(self.model.user_id == uid, field == key)
            )
            s.commit()
        if not result.rowcount:
            raise KeyError(key)

    def pop(self, key, default=...):
        try:
            value = self[key]
            del self[key]
            return value
        except KeyError:
            if default is ...:
                raise
            return default

    def setdefault(self, key, default=None):
        value = self.get(key)
        if value is None:
            self[key] = default
            return self[key]
        return value

    def __iter__(self) -> Iterator:
        with SessionLocal() as s:
            rows = self._query(s)
        return iter(dict.fromkeys(getattr(r, self.group_field or "id") for r in rows))

    def __len__(self):
        return sum(1 for _ in self)

    def clear(self):
        uid = _owner()
        with SessionLocal() as s:
            s.execute(delete(self.model).where(self.model.user_id == uid))
            s.commit()


DISCIPLINES = RecordMap(DisciplineRecord)
ASSESSMENTS = RecordMap(AssessmentRecord, "discipline_id", "list")
EVENTS = RecordMap(AcademicEventRecord)
ABSENCES = RecordMap(AbsenceRecord, "discipline_id", "list")
COURSE_PLANS = RecordMap(CoursePlanRecord)
CONTENT_NODES = RecordMap(ContentNodeRecord, "discipline_id", "dict")
ASSESSMENT_CONTENT_LINKS = RecordMap(AssessmentContentLinkRecord)
COMPLEXITY_ANALYSES = RecordMap(ComplexityAnalysisRecord)


def create_discipline(payload):
    did = str(uuid4())
    now = utc_now()
    record = {"id": did, **payload, "created_at": now, "updated_at": now}
    DISCIPLINES[did] = record
    return record


def list_disciplines():
    return list(DISCIPLINES.values())


def get_discipline(discipline_id):
    return DISCIPLINES.get(discipline_id)


def _save_discipline(record):
    DISCIPLINES[record["id"]] = record
    return record


def update_attendance(discipline_id, payload):
    record = get_discipline(discipline_id)
    if record is None:
        return None
    record.update({k: v for k, v in payload.items() if v is not None})
    record["updated_at"] = utc_now()
    return _save_discipline(record)


def _clean_text(value, limit=20000):
    soup = BeautifulSoup(str(value or ""), "html.parser")
    for unsafe in soup.find_all(["script", "style", "iframe", "object"]):
        unsafe.decompose()
    return " ".join(soup.get_text(" ", strip=True).split())[:limit]


def upsert_catalog_component(component):
    code = "".join(c for c in str(component.get("code") or "").upper() if c.isalnum())
    if not code:
        return None
    now = utc_now()
    with SessionLocal() as s:
        row = s.get(CatalogComponent, code)
        values = {
            "name": _clean_text(component.get("name"), 300) or code,
            "workload_hours": component.get("workload_hours"),
            "academic_unit": _clean_text(
                component.get("academic_unit") or component.get("unit"), 300
            )
            or None,
            "syllabus": _clean_text(component.get("syllabus")),
            "current_program": _clean_text(component.get("current_program")),
            "source_url": str(component.get("source_url") or "")[:2000] or None,
            "source": "sigaa_public_components",
            "synced_at": now,
        }
        if row:
            for k, v in values.items():
                setattr(row, k, v)
        else:
            row = CatalogComponent(code=code, **values)
            s.add(row)
        s.commit()
    return get_catalog_component(code)


def get_catalog_component(code):
    normalized = "".join(c for c in str(code).upper() if c.isalnum())
    with SessionLocal() as s:
        row = s.get(CatalogComponent, normalized)
        if not row:
            return None
        return {
            "code": row.code,
            "name": row.name,
            "workload_hours": row.workload_hours,
            "academic_unit": row.academic_unit,
            "syllabus": row.syllabus,
            "current_program": row.current_program,
            "source_url": row.source_url,
            "source": row.source,
            "synced_at": row.synced_at,
        }


def attach_sigaa_component(discipline_id, component):
    record = get_discipline(discipline_id)
    if record is None:
        return None
    catalog = upsert_catalog_component(component)
    now = utc_now()
    record.update(
        {
            "sigaa_code": component.get("code"),
            "sigaa_source_url": component.get("source_url"),
            "syllabus": (catalog or {}).get("syllabus", ""),
            "current_program": (catalog or {}).get("current_program", ""),
            "workload_hours": (catalog or {}).get("workload_hours"),
            "sigaa_cached_at": now,
            "updated_at": now,
        }
    )
    _save_discipline(record)
    return record


def add_assessment(discipline_id, payload):
    if get_discipline(discipline_id) is None:
        return None
    item = {"id": str(uuid4()), "discipline_id": discipline_id, **payload}
    items = ASSESSMENTS.get(discipline_id, [])
    items.append(item)
    ASSESSMENTS[discipline_id] = items
    sync_assessment_event(discipline_id, item)
    record = get_discipline(discipline_id)
    record["updated_at"] = utc_now()
    _save_discipline(record)
    return item


def list_assessments(discipline_id):
    return ASSESSMENTS.get(discipline_id, [])


def normalize_discipline_code(v):
    return "".join(c for c in v.upper() if c.isalnum()) or None if v else None


def normalize_discipline_name(v):
    return " ".join(v.casefold().strip().split()) or None if v else None


def find_discipline_by_code(code):
    n = normalize_discipline_code(code)
    return (
        next(
            (
                d
                for d in DISCIPLINES.values()
                if normalize_discipline_code(d.get("code")) == n
            ),
            None,
        )
        if n
        else None
    )


def find_discipline_by_name(name):
    n = normalize_discipline_name(name)
    return (
        next(
            (
                d
                for d in DISCIPLINES.values()
                if normalize_discipline_name(d.get("name")) == n
            ),
            None,
        )
        if n
        else None
    )


def save_import_preview(p):
    IMPORT_PREVIEWS[str(p["preview_id"])] = p
    return p


def get_import_preview(pid):
    p = IMPORT_PREVIEWS.get(pid)
    if p and p.get("expires_at") and p["expires_at"] <= utc_now():
        IMPORT_PREVIEWS.pop(pid, None)
        return None
    return p


def delete_import_preview(pid):
    IMPORT_PREVIEWS.pop(pid, None)


def cleanup_expired_import_previews():
    expired = [
        k
        for k, v in IMPORT_PREVIEWS.items()
        if v.get("expires_at") and v["expires_at"] <= utc_now()
    ]
    for k in expired:
        IMPORT_PREVIEWS.pop(k, None)
    return len(expired)


def get_assessment(did, aid):
    return next((i for i in list_assessments(did) if i["id"] == aid), None)


def update_assessment(did, aid, payload):
    items = list_assessments(did)
    item = next((i for i in items if i["id"] == aid), None)
    if item is None:
        return None
    item.update(payload)
    ASSESSMENTS[did] = items
    sync_assessment_event(did, item)
    record = get_discipline(did)
    record["updated_at"] = utc_now()
    _save_discipline(record)
    return item


def delete_assessment(did, aid):
    items = list_assessments(did)
    new = [i for i in items if i["id"] != aid]
    ASSESSMENTS[did] = new
    if len(new) != len(items):
        ASSESSMENT_CONTENT_LINKS.pop(aid, None)
        cancel_assessment_event(aid)
        return True
    return False


def add_absence(did, payload):
    items = ABSENCES.get(did, [])
    if any(
        i["date"] == payload["date"] and i["class_hours"] == payload["class_hours"]
        for i in items
    ):
        raise ValueError("Já existe uma falta com a mesma data e duração.")
    item = {"id": str(uuid4()), "discipline_id": did, **payload}
    items.append(item)
    ABSENCES[did] = items
    return item


def list_absences(did):
    return sorted(ABSENCES.get(did, []), key=lambda i: i["date"], reverse=True)


def update_absence(did, aid, payload):
    items = ABSENCES.get(did, [])
    item = next((i for i in items if i["id"] == aid), None)
    if item is None:
        return None
    candidate = {**item, **payload}
    if any(
        o["id"] != aid
        and o["date"] == candidate["date"]
        and o["class_hours"] == candidate["class_hours"]
        for o in items
    ):
        raise ValueError("Já existe uma falta com a mesma data e duração.")
    item.update(payload)
    ABSENCES[did] = items
    return item


def delete_absence(did, aid):
    items = ABSENCES.get(did, [])
    new = [i for i in items if i["id"] != aid]
    ABSENCES[did] = new
    return len(new) != len(items)


def get_content_extraction_preview(pid):
    p = CONTENT_EXTRACTION_PREVIEWS.get(pid)
    if p and p["expires_at"] <= utc_now():
        CONTENT_EXTRACTION_PREVIEWS.pop(pid, None)
        return None
    return p


def delete_content_extraction_preview(pid):
    CONTENT_EXTRACTION_PREVIEWS.pop(pid, None)


def save_course_plan(did, payload):
    record = {**payload, "discipline_id": did, "confirmed_at": utc_now()}
    COURSE_PLANS[did] = record
    if record.get("workload_hours") is not None:
        discipline = get_discipline(did)
        discipline["workload_hours"] = record["workload_hours"]
        _save_discipline(discipline)
    return record


def _assessment_event_type(assessment: dict) -> str:
    name = str(assessment.get("name") or "").casefold()
    if any(word in name for word in ["prova", "teste", "taf", "mtai"]):
        return "exam"
    if any(word in name for word in ["entrega", "trabalho", "relatório", "relatorio"]):
        return "assignment"
    if "apresent" in name or "semin" in name:
        return "presentation"
    if "prazo" in name or "deadline" in name:
        return "deadline"
    return "activity"


def _date_to_event_start(value):
    if not value:
        return None
    raw = value.isoformat() if hasattr(value, "isoformat") else str(value)
    return raw[:10] + "T00:00:00-03:00"


def _assessment_event_payload(discipline_id: str, assessment: dict) -> dict | None:
    start_at = _date_to_event_start(assessment.get("date"))
    if not start_at:
        return None
    discipline = get_discipline(discipline_id) or {}
    now = utc_now()
    aid = str(assessment["id"])
    return {
        "id": str(uuid4()),
        "discipline_id": discipline_id,
        "assessment_id": aid,
        "title": str(assessment.get("name") or "Avaliação"),
        "description": assessment.get("description") or assessment.get("notes"),
        "event_type": _assessment_event_type(assessment),
        "start_at": start_at,
        "end_at": None,
        "all_day": True,
        "timezone": "America/Sao_Paulo",
        "weight": assessment.get("weight") or assessment.get("group_weight"),
        "status": "completed" if assessment.get("status") == "completed" else "cancelled" if assessment.get("status") == "cancelled" else "confirmed",
        "source": "assessment",
        "source_evidence": f'Avaliação cadastrada: {assessment.get("name") or "sem título"}' + (f' — peso {assessment.get("weight")}%.' if assessment.get("weight") is not None else "."),
        "extraction_confidence": 1.0,
        "source_fingerprint": f"assessment:{aid}",
        "created_at": now,
        "updated_at": now,
        "discipline_code": discipline.get("code"),
        "discipline_name": discipline.get("name"),
    }


def _save_event(record: dict) -> dict:
    EVENTS[str(record["id"])] = record
    return record


def _with_discipline_meta(event: dict) -> dict:
    discipline_id = event.get("discipline_id")
    if discipline_id:
        discipline = get_discipline(str(discipline_id))
        if discipline:
            event = {**event, "discipline_code": discipline.get("code"), "discipline_name": discipline.get("name")}
    return event


def list_events(start_at=None, end_at=None, discipline_id=None, event_type=None, status=None):
    def parse(value):
        if value is None:
            return None
        raw = value.isoformat() if hasattr(value, "isoformat") else str(value)
        return raw
    start_raw, end_raw = parse(start_at), parse(end_at)
    items = []
    for event in EVENTS.values():
        if discipline_id and str(event.get("discipline_id")) != str(discipline_id):
            continue
        if event_type and event.get("event_type") != event_type:
            continue
        if status and event.get("status") != status:
            continue
        event_start = str(event.get("start_at"))
        if start_raw and event_start < start_raw:
            continue
        if end_raw and event_start > end_raw:
            continue
        items.append(_with_discipline_meta(event))
    return sorted(items, key=lambda item: (str(item.get("start_at")), item.get("title") or ""))


def upcoming_events(limit=8, reference=None):
    start = reference or utc_now().isoformat()
    return list_events(start_at=start, status="confirmed")[:limit]


def get_event(event_id):
    event = EVENTS.get(str(event_id))
    return _with_discipline_meta(event) if event else None


def create_event(payload):
    if payload.get("discipline_id") and get_discipline(str(payload["discipline_id"])) is None:
        raise ValueError("Disciplina não encontrada.")
    now = utc_now()
    event = {"id": str(uuid4()), **payload, "created_at": now, "updated_at": now}
    return _with_discipline_meta(_save_event(event))


def update_event(event_id, payload):
    event = EVENTS.get(str(event_id))
    if event is None:
        return None
    if event.get("source") == "assessment" and any(key in payload for key in ["title", "start_at", "weight", "discipline_id"]):
        raise ValueError("Eventos originados de avaliação devem ser alterados na própria avaliação.")
    if payload.get("discipline_id") and get_discipline(str(payload["discipline_id"])) is None:
        raise ValueError("Disciplina não encontrada.")
    event.update({k: v for k, v in payload.items() if v is not None})
    event["updated_at"] = utc_now()
    return _with_discipline_meta(_save_event(event))


def set_event_status(event_id, status):
    event = EVENTS.get(str(event_id))
    if event is None:
        return None
    event["status"] = status
    event["updated_at"] = utc_now()
    return _with_discipline_meta(_save_event(event))


def delete_event(event_id):
    event = EVENTS.get(str(event_id))
    if event is None:
        return False
    if event.get("source") == "assessment":
        event["status"] = "cancelled"
        event["updated_at"] = utc_now()
        _save_event(event)
        return True
    EVENTS.pop(str(event_id), None)
    return True


def find_event_by_assessment(assessment_id):
    return next((event for event in EVENTS.values() if event.get("source") == "assessment" and str(event.get("assessment_id")) == str(assessment_id)), None)


def find_event_by_fingerprint(fingerprint):
    if not fingerprint:
        return None
    return next((event for event in EVENTS.values() if event.get("source_fingerprint") == fingerprint), None)


def sync_assessment_event(discipline_id, assessment):
    existing = find_event_by_assessment(assessment["id"])
    payload = _assessment_event_payload(discipline_id, assessment)
    if payload is None:
        if existing:
            existing["status"] = "cancelled"
            existing["updated_at"] = utc_now()
            _save_event(existing)
        return None
    if existing:
        preserved = {"id": existing["id"], "created_at": existing.get("created_at", payload["created_at"])}
        existing.update({**payload, **preserved, "updated_at": utc_now()})
        return _save_event(existing)
    return _save_event(payload)


def cancel_assessment_event(assessment_id):
    event = find_event_by_assessment(assessment_id)
    if event:
        event["status"] = "cancelled"
        event["updated_at"] = utc_now()
        _save_event(event)
    return event


def save_event_extraction_preview(preview):
    EVENT_EXTRACTION_PREVIEWS[str(preview["preview_id"])] = preview
    return preview


def get_event_extraction_preview(preview_id):
    preview = EVENT_EXTRACTION_PREVIEWS.get(str(preview_id))
    if preview and preview.get("expires_at") and preview["expires_at"] <= utc_now():
        EVENT_EXTRACTION_PREVIEWS.pop(str(preview_id), None)
        return None
    return preview


def delete_event_extraction_preview(preview_id):
    EVENT_EXTRACTION_PREVIEWS.pop(str(preview_id), None)
