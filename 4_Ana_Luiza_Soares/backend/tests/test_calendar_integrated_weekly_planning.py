from fastapi.testclient import TestClient

from app import storage
from app.database import current_user_id
from app.main import app


def setup_function():
    storage.DISCIPLINES.clear()
    storage.ASSESSMENTS.clear()
    storage.EVENTS.clear()
    storage.STUDY_PLAN_PREVIEWS.clear()


def teardown_function():
    storage.DISCIPLINES.clear()
    storage.ASSESSMENTS.clear()
    storage.EVENTS.clear()
    storage.STUDY_PLAN_PREVIEWS.clear()


def client():
    return TestClient(app)


def create_discipline(c, code="FGA0001", name="Disciplina"):
    response = c.post("/api/disciplines", json={"code": code, "name": name, "workload_hours": 60})
    assert response.status_code == 201
    return response.json()


def test_availability_summary_derives_weekly_total_and_rejects_overlap():
    c = client()
    payload = {
        "week_start": "2026-07-13",
        "windows": [
            {"weekday": "monday", "start_time": "18:00", "end_time": "20:00"},
            {"weekday": "wednesday", "start_time": "14:00", "end_time": "16:30"},
        ],
    }

    response = c.post("/api/study-plans/availability/summary", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["daily_totals"] == {"monday": 120, "wednesday": 150}
    assert body["weekly_total_minutes"] == 270

    overlap = c.post(
        "/api/study-plans/availability/summary",
        json={
            "week_start": "2026-07-13",
            "windows": [
                {"weekday": "monday", "start_time": "18:00", "end_time": "20:00"},
                {"weekday": "monday", "start_time": "19:00", "end_time": "21:00"},
            ],
        },
    )
    assert overlap.status_code == 422


def test_weekly_preview_confirms_blocks_as_calendar_events_idempotently():
    c = client()
    discipline = create_discipline(c, "FGA0002", "Qualidade")
    c.post(
        f"/api/disciplines/{discipline['id']}/assessments",
        json={"name": "Prova", "weight": 40, "date": "2026-07-20", "status": "planned"},
    )

    preview = c.post(
        "/api/study-plans/weekly-preview",
        json={
            "week_start": "2026-07-13",
            "windows": [{"weekday": "monday", "start_time": "18:00", "end_time": "20:00"}],
            "objective_text": "revisar para a prova",
        },
    )

    assert preview.status_code == 200
    body = preview.json()
    assert body["availability"]["weekly_total_minutes"] == 120
    assert body["ranked_priorities"][0]["priority_score"] >= 70
    assert body["planned_blocks"][0]["start_at"] == "2026-07-13T18:00:00-03:00"

    first = c.post(f"/api/study-plans/{body['study_plan_id']}/confirm")
    second = c.post(f"/api/study-plans/{body['study_plan_id']}/confirm")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["created_count"] == 1
    assert second.json()["created_count"] == 1
    events = c.get("/api/calendar/events", params={"start_at": "2026-07-13T00:00:00-03:00", "end_at": "2026-07-13T23:59:59-03:00"}).json()
    study_blocks = [event for event in events if event["source"] == "study_plan"]
    assert len(study_blocks) == 1
    assert study_blocks[0]["event_type"] == "study_block"
    assert study_blocks[0]["priority_score"] == body["planned_blocks"][0]["priority_score"]


def test_existing_event_blocks_conflicting_study_time():
    c = client()
    create_discipline(c, "FGA0003", "Programacao")
    busy = c.post(
        "/api/calendar/events",
        json={
            "title": "Monitoria",
            "event_type": "activity",
            "start_at": "2026-07-13T18:00:00-03:00",
            "end_at": "2026-07-13T19:00:00-03:00",
            "all_day": False,
            "timezone": "America/Sao_Paulo",
        },
    )
    assert busy.status_code == 201

    preview = c.post(
        "/api/study-plans/weekly-preview",
        json={
            "week_start": "2026-07-13",
            "windows": [{"weekday": "monday", "start_time": "18:00", "end_time": "20:00"}],
        },
    ).json()

    assert preview["planned_blocks"][0]["start_at"] == "2026-07-13T19:00:00-03:00"
    assert preview["conflicts"]


def test_past_and_completed_assessments_do_not_starve_later_priorities():
    c = client()
    stale = create_discipline(c, "FGA0001", "Historico")
    future = create_discipline(c, "FGA0002", "Prioridade futura")
    c.post(
        f"/api/disciplines/{stale['id']}/assessments",
        json={"name": "Prova antiga", "weight": 80, "date": "2026-07-01", "status": "planned"},
    )
    c.post(
        f"/api/disciplines/{stale['id']}/assessments",
        json={"name": "Prova concluida", "weight": 80, "date": "2026-07-15", "status": "completed"},
    )
    c.post(
        f"/api/disciplines/{future['id']}/assessments",
        json={"name": "Prova futura", "weight": 40, "date": "2026-07-20", "status": "planned"},
    )

    response = c.post(
        "/api/study-plans/weekly-preview",
        json={
            "week_start": "2026-07-13",
            "windows": [
                {"weekday": "monday", "start_time": "18:00", "end_time": "20:00"},
                {"weekday": "wednesday", "start_time": "18:00", "end_time": "20:00"},
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    future_priority = next(
        item for item in body["ranked_priorities"] if item["discipline_id"] == future["id"]
    )
    assert future_priority["assessment_name"] == "Prova futura"
    assert any(block["discipline_id"] == future["id"] for block in body["planned_blocks"])
    assert all(
        item["assessment_name"] not in {"Prova antiga", "Prova concluida"}
        for item in body["ranked_priorities"]
    )


def test_capacity_analysis_reports_requested_usable_blocked_and_partial_minutes():
    c = client()
    discipline = create_discipline(c, "FGA0004", "Qualidade")
    c.post(
        f"/api/disciplines/{discipline['id']}/assessments",
        json={"name": "Entrega", "weight": 30, "date": "2026-07-14", "status": "planned"},
    )
    c.post(
        "/api/calendar/events",
        json={
            "title": "Aula",
            "event_type": "activity",
            "start_at": "2026-07-13T18:30:00-03:00",
            "end_at": "2026-07-13T20:00:00-03:00",
            "all_day": False,
            "timezone": "America/Sao_Paulo",
        },
    )

    response = c.post(
        "/api/study-plans/weekly-preview",
        json={
            "week_start": "2026-07-13",
            "windows": [
                {"weekday": "monday", "start_time": "18:00", "end_time": "20:00"}
            ],
        },
    )

    assert response.status_code == 200
    capacity = response.json()["capacity_analysis"][0]
    assert capacity["requested_minutes"] == 60
    assert capacity["allocated_minutes"] == 30
    assert capacity["remaining_minutes"] == 30
    assert capacity["available_minutes_before_deadline"] == 120
    assert capacity["usable_minutes_before_deadline"] == 30
    assert capacity["blocked_minutes"] == 90
    assert capacity["minimum_useful_block_minutes"] == 30
    assert capacity["reason_code"] == "partially_allocated"
    assert capacity["blocking_events"][0]["title"] == "Aula"


def test_confirmation_revalidates_conflicts_introduced_after_preview():
    c = client()
    create_discipline(c, "FGA0005", "Sistemas")
    preview = c.post(
        "/api/study-plans/weekly-preview",
        json={
            "week_start": "2026-07-13",
            "windows": [
                {"weekday": "monday", "start_time": "18:00", "end_time": "19:00"}
            ],
        },
    ).json()
    block = preview["planned_blocks"][0]
    c.post(
        "/api/calendar/events",
        json={
            "title": "Novo compromisso",
            "event_type": "activity",
            "start_at": block["start_at"],
            "end_at": block["end_at"],
            "all_day": False,
            "timezone": "America/Sao_Paulo",
        },
    )

    confirmation = c.post(f"/api/study-plans/{preview['study_plan_id']}/confirm")

    assert confirmation.status_code == 200
    assert confirmation.json()["created_count"] == 0
    assert confirmation.json()["skipped_blocks"][0]["temporary_id"] == block["temporary_id"]


def test_study_plan_preview_is_isolated_by_authenticated_owner():
    token_one = current_user_id.set("planner-one")
    try:
        storage.DISCIPLINES.clear()
        storage.create_discipline(
            {"code": "FGA0006", "name": "Usuario um", "workload_hours": 60}
        )
        from app.schemas import WeeklyPlanPreviewRequest
        from app.services.weekly_planning import build_weekly_preview

        preview = build_weekly_preview(
            WeeklyPlanPreviewRequest.model_validate(
                {
                    "week_start": "2026-07-13",
                    "windows": [
                        {
                            "weekday": "monday",
                            "start_time": "18:00",
                            "end_time": "19:00",
                        }
                    ],
                }
            )
        )
    finally:
        current_user_id.reset(token_one)

    token_two = current_user_id.set("planner-two")
    try:
        assert storage.get_study_plan_preview(preview["study_plan_id"]) is None
    finally:
        current_user_id.reset(token_two)


def test_calendar_range_expands_recurring_events():
    c = client()
    response = c.post(
        "/api/calendar/events",
        json={
            "title": "Grupo de estudo",
            "event_type": "activity",
            "start_at": "2026-07-14T18:00:00-03:00",
            "end_at": "2026-07-14T19:00:00-03:00",
            "all_day": False,
            "timezone": "America/Sao_Paulo",
            "recurrence": {
                "frequency": "weekly",
                "weekdays": ["tuesday", "thursday"],
                "ends": {"mode": "after_count", "count": 4},
            },
        },
    )
    assert response.status_code == 201

    events = c.get(
        "/api/calendar/events",
        params={"start_at": "2026-07-13T00:00:00-03:00", "end_at": "2026-07-26T23:59:59-03:00"},
    ).json()

    starts = [event["start_at"] for event in events]
    assert starts == [
        "2026-07-14T18:00:00-03:00",
        "2026-07-16T18:00:00-03:00",
        "2026-07-21T18:00:00-03:00",
        "2026-07-23T18:00:00-03:00",
    ]
    assert all(event["occurrence_id"] for event in events)
