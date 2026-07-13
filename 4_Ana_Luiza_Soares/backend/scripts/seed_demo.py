from __future__ import annotations

import os
from datetime import date

from app import storage
from app.auth import ensure_user
from app.database import current_user_id, init_database
from app.services import content_map


def _find_discipline(code: str):
    return next((item for item in storage.list_disciplines() if item.get("code") == code), None)


def _ensure_discipline(code: str, name: str, **extra):
    existing = _find_discipline(code)
    if existing:
        return existing
    return storage.create_discipline({"code": code, "name": name, **extra})


def _find_node(discipline_id: str, title: str):
    return next((item for item in storage.CONTENT_NODES.get(discipline_id, {}).values() if item.get("title") == title), None)


def _ensure_node(discipline_id: str, title: str, parent_id: str | None = None, **extra):
    existing = _find_node(discipline_id, title)
    if existing:
        return existing
    return content_map.create_node(discipline_id, {"parent_id": parent_id, "title": title, "description": extra.get("description"), "difficulty": extra.get("difficulty"), "status": extra.get("status", "not_started")})


def _find_assessment(discipline_id: str, name: str):
    return next((item for item in storage.list_assessments(discipline_id) if item.get("name") == name), None)


def _ensure_assessment(discipline_id: str, name: str, **payload):
    existing = _find_assessment(discipline_id, name)
    data = {"name": name, **payload}
    if existing:
        storage.update_assessment(discipline_id, existing["id"], data)
        return storage.get_assessment(discipline_id, existing["id"])
    return storage.add_assessment(discipline_id, data)


def run():
    init_database()
    email = os.getenv("EMAIL_TESTE", "estudante@example.invalid")
    password = os.getenv("SENHA_TESTE", "troque-esta-senha")
    user = ensure_user(email, password, update_password=True)
    token = current_user_id.set(user.id)
    try:
        quality = _ensure_discipline("FGA-QS", "Qualidade de Software", workload_hours=60, professor="Docente de demonstração")
        ml = _ensure_discipline("FGA-ML", "Aprendizado de Máquina", workload_hours=60, professor="Docente de demonstração")

        storage.save_course_plan(quality["id"], {
            "code": "FGA-QS",
            "name": "Qualidade de Software",
            "semester": "2026.1",
            "workload_hours": 60,
            "term_weeks": 15,
            "objectives": ["Aplicar técnicas de qualidade e avaliação de produto."],
            "contents": ["GQM", "Métricas", "Testes", "Revisão"],
            "schedule": ["Prova 1 — 14/07/2026", "Prova 2 — 16/07/2026"],
            "evaluation_groups": [],
            "assessments": [
                {"name": "Prova 1", "date": "2026-07-14", "weight": 40, "topics": ["GQM", "Métricas"], "status": "recognized"},
                {"name": "Prova 2", "date": "2026-07-16", "weight": 60, "topics": ["Testes", "Revisão"], "status": "recognized"},
            ],
            "bibliography": ["Fixture sanitizada para demonstração."],
        })
        storage.save_course_plan(ml["id"], {
            "code": "FGA-ML",
            "name": "Aprendizado de Máquina",
            "semester": "2026.1",
            "workload_hours": 60,
            "objectives": ["Estudar fundamentos de modelos supervisionados."],
            "contents": ["Regressão", "Classificação"],
            "schedule": ["Sem avaliação datada cadastrada."],
            "evaluation_groups": [],
            "assessments": [],
            "bibliography": ["Fixture sanitizada para demonstração."],
        })

        root = _ensure_node(quality["id"], "Medição e GQM", difficulty="high", status="not_started")
        child = _ensure_node(quality["id"], "Questões e métricas GQM", parent_id=root["id"], difficulty="high", status="not_started")
        reviewed = _ensure_node(quality["id"], "Conceitos revisados", difficulty="medium", status="reviewed")
        p2_node = _ensure_node(quality["id"], "Testes e revisão", difficulty="medium", status="in_progress")
        _ensure_node(ml["id"], "Regressão linear", difficulty="medium", status="not_started")

        p1 = _ensure_assessment(quality["id"], "Prova 1", weight=40, grade=None, date=date(2026, 7, 14), topics=["GQM", "Métricas"], source="manual", status="planned")
        p2 = _ensure_assessment(quality["id"], "Prova 2", weight=60, grade=None, date=date(2026, 7, 16), topics=["Testes", "Revisão"], source="manual", status="planned")
        content_map.set_associations(quality["id"], p1["id"], [{"content_node_id": root["id"], "include_descendants": True}, {"content_node_id": reviewed["id"], "include_descendants": False}])
        content_map.set_associations(quality["id"], p2["id"], [{"content_node_id": p2_node["id"], "include_descendants": False}])

        storage.create_event({
            "discipline_id": ml["id"],
            "assessment_id": None,
            "title": "Leitura orientada de regressão",
            "description": "Evento manual sanitizado para demonstrar calendário sem avaliação datada.",
            "event_type": "activity",
            "start_at": "2026-07-17T00:00:00-03:00",
            "end_at": None,
            "all_day": True,
            "timezone": "America/Sao_Paulo",
            "weight": None,
            "status": "confirmed",
            "source": "manual",
            "source_evidence": "Seed de demonstração.",
            "extraction_confidence": None,
            "source_fingerprint": "demo:ml-reading-2026-07-17",
        }) if not storage.find_event_by_fingerprint("demo:ml-reading-2026-07-17") else None

        print({"user": user.email, "disciplines": [quality["code"], ml["code"]], "events": len(storage.list_events(start_at="2026-07-01T00:00:00-03:00", end_at="2026-07-31T23:59:59-03:00"))})
    finally:
        current_user_id.reset(token)


if __name__ == "__main__":
    run()
