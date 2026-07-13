from fastapi.testclient import TestClient
from app.main import app
from app import storage
from app.auth import create_token, ensure_user, verify_password
from app.services import content_map
from app.database import SessionLocal, User, current_user_id, engine


def headers(user):
    return {"Authorization": f"Bearer {create_token(user)}"}


def test_login_hash_and_academic_isolation(monkeypatch):
    monkeypatch.setenv("AUTH_SECRET", "a-secure-test-secret")
    monkeypatch.setenv("AUTH_REQUIRED_IN_TESTS", "true")
    one = ensure_user("one@example.invalid", "password-one", user_id="user-one")
    two = ensure_user("two@example.invalid", "password-two", user_id="user-two")
    context = current_user_id.set(one.id)
    storage.DISCIPLINES.clear()
    current_user_id.reset(context)
    context = current_user_id.set(two.id)
    storage.DISCIPLINES.clear()
    current_user_id.reset(context)
    with SessionLocal() as session:
        persisted = session.get(User, "user-one")
        assert persisted.password_hash != "password-one" and verify_password(
            "password-one", persisted.password_hash
        )
    with TestClient(app) as client:
        assert client.get("/api/disciplines").status_code == 401
        login = client.post(
            "/api/auth/login",
            json={"email": "one@example.invalid", "password": "password-one"},
        )
        assert login.status_code == 200 and login.json()["access_token"]
        created = client.post(
            "/api/disciplines",
            json={"code": "FGA0001", "name": "Persistência"},
            headers=headers(one),
        )
        assert created.status_code == 201
        assert len(client.get("/api/disciplines", headers=headers(one)).json()) == 1
        assert client.get("/api/disciplines", headers=headers(two)).json() == []
        assert (
            client.get(
                f"/api/disciplines/{created.json()['id']}", headers=headers(two)
            ).status_code
            == 404
        )


def test_records_survive_new_database_session(monkeypatch):
    token = current_user_id.set("restart-user")
    try:
        storage.DISCIPLINES.clear()
        record = storage.create_discipline(
            {"code": "FGA0002", "name": "Dados duráveis"}
        )
        assessment = storage.add_assessment(
            record["id"], {"name": "P1", "weight": 40, "status": "planned"}
        )
        storage.add_absence(
            record["id"], {"date": "2026-07-01", "class_hours": 2, "notes": None}
        )
        storage.save_course_plan(
            record["id"],
            {
                "contents": ["Persistência"],
                "schedule": [],
                "evaluation_groups": [],
                "assessments": [],
                "workload_hours": 60,
            },
        )
        node = content_map.create_node(
            record["id"],
            {
                "parent_id": None,
                "title": "Banco",
                "description": None,
                "difficulty": "medium",
                "status": "not_started",
            },
        )
        content_map.set_associations(
            record["id"],
            assessment["id"],
            [{"content_node_id": node["id"], "include_descendants": False}],
        )
        engine.dispose()
        assert storage.get_discipline(record["id"])["name"] == "Dados duráveis"
        assert storage.list_assessments(record["id"])[0]["name"] == "P1"
        assert storage.list_absences(record["id"])[0]["class_hours"] == 2
        assert storage.COURSE_PLANS[record["id"]]["contents"] == ["Persistência"]
        assert storage.CONTENT_NODES[record["id"]][node["id"]]["title"] == "Banco"
        assert (
            storage.ASSESSMENT_CONTENT_LINKS[assessment["id"]][0]["content_node_id"]
            == node["id"]
        )
    finally:
        current_user_id.reset(token)


def test_catalog_sanitizes_syllabus_and_study_demand_is_cached(monkeypatch):
    token = current_user_id.set("catalog-user")
    try:
        component = storage.upsert_catalog_component(
            {
                "code": "FGA 0003",
                "name": "Algoritmos",
                "workload_hours": 60,
                "unit": "FGA",
                "syllabus": "<script>mal()</script><p>Algoritmos e projeto de laboratório.</p>",
                "source_url": "https://sigaa.unb.br/sigaa/public/x",
            }
        )
        assert (
            "<" not in component["syllabus"]
            and "mal()" not in component["syllabus"]
            and component["code"] == "FGA0003"
        )
        discipline = storage.create_discipline(
            {"code": "FGA0003", "name": "Algoritmos", "syllabus": component["syllabus"]}
        )
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        from app.services.complexity_analysis import analyze

        first = analyze(discipline["id"])
        second = analyze(discipline["id"])
        assert first["mode"] == "deterministic_fallback"
        assert second["analyzed_at"] == first["analyzed_at"]
        assert any(item["type"] == "syllabus" for item in first["evidence_used"])
    finally:
        current_user_id.reset(token)


def test_missing_syllabus_is_insufficient_evidence_not_low_demand(monkeypatch):
    token = current_user_id.set("complexity-invalid-user")
    try:
        storage.COMPLEXITY_ANALYSES.clear()
        discipline = storage.create_discipline(
            {"code": "FGA0004", "name": "Teste", "workload_hours": 60}
        )
        from app.services.complexity_analysis import analyze

        result = analyze(discipline["id"], True)
        assert result["demand_level"] == "insufficient_evidence"
        assert result["confidence"] == 0.1
        assert "ementa" in result["missing_evidence"]
        assert result["warnings"]
    finally:
        current_user_id.reset(token)


def test_v1_complexity_cache_is_invalidated_and_recomputed(monkeypatch):
    token = current_user_id.set("complexity-valid-user")
    try:
        syllabus = "Algoritmos de ordenação, projeto e análise de complexidade."
        discipline = storage.create_discipline(
            {"code": "FGA0005", "name": "Teste", "syllabus": syllabus}
        )
        storage.COMPLEXITY_ANALYSES[discipline["id"]] = {
            "estimated_level": "low",
            "confidence": 0.25,
            "model_or_rule_version": "complexity-v1",
            "analyzed_at": storage.utc_now(),
        }
        from app.services.complexity_analysis import analyze

        result = analyze(discipline["id"])
        assert result["model_or_rule_version"] == "study-demand-v2"
        assert "estimated_level" not in result
        assert result["demand_level"] in {"low", "moderate", "high"}
    finally:
        current_user_id.reset(token)


def test_learner_specific_difficulty_is_separate_from_course_demand():
    token = current_user_id.set("study-demand-learner-user")
    try:
        storage.DISCIPLINES.clear()
        storage.ASSESSMENTS.clear()
        storage.COMPLEXITY_ANALYSES.clear()
        discipline = storage.create_discipline(
            {
                "code": "FGA0006",
                "name": "Projeto",
                "syllabus": "Projeto de software com implementação e relatório.",
            }
        )
        storage.add_assessment(
            discipline["id"],
            {
                "name": "Entrega",
                "weight": 100,
                "grade": 3.0,
                "status": "completed",
            },
        )
        from app.services.complexity_analysis import analyze

        result = analyze(discipline["id"], True)
        assert result["learner_specific_difficulty"]["level"] == "high"
        assert result["demand_level"] != "insufficient_evidence"
        assert "priority_score" not in result
    finally:
        current_user_id.reset(token)
