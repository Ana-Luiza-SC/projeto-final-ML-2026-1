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


def test_catalog_sanitizes_syllabus_and_complexity_is_cached(monkeypatch):
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
        assert (
            first["mode"] == "fallback"
            and second["analyzed_at"] == first["analyzed_at"]
        )
        assert first["syllabus_evidence"]
    finally:
        current_user_id.reset(token)


def test_complexity_invalid_llm_response_uses_fallback(monkeypatch):
    token = current_user_id.set("complexity-invalid-user")
    try:
        storage.COMPLEXITY_ANALYSES.clear()
        discipline = storage.create_discipline(
            {
                "code": "FGA0004",
                "name": "Teste",
                "syllabus": "Estruturas de dados e algoritmos.",
            }
        )
        monkeypatch.setenv("GOOGLE_API_KEY", "fake")
        monkeypatch.setenv("LLM_PROVIDER", "google")
        from app.services.complexity_analysis import analyze

        result = analyze(
            discipline["id"],
            True,
            generator=lambda *_: {
                "estimated_level": "invented",
                "syllabus_evidence": ["não existe"],
            },
        )
        assert result["mode"] == "fallback" and result["warnings"]
    finally:
        current_user_id.reset(token)


def test_complexity_valid_llm_is_structured_and_evidenced(monkeypatch):
    token = current_user_id.set("complexity-valid-user")
    try:
        syllabus = "Algoritmos de ordenação e análise de complexidade."
        discipline = storage.create_discipline(
            {"code": "FGA0005", "name": "Teste", "syllabus": syllabus}
        )
        monkeypatch.setenv("GOOGLE_API_KEY", "fake")
        monkeypatch.setenv("LLM_PROVIDER", "google")
        from app.services.complexity_analysis import analyze

        result = analyze(
            discipline["id"],
            True,
            generator=lambda *_: {
                "estimated_level": "medium",
                "confidence": 0.8,
                "factors": ["análise"],
                "syllabus_evidence": [syllabus],
            },
        )
        assert result["mode"] == "llm" and result["syllabus_evidence"] == [syllabus]
    finally:
        current_user_id.reset(token)
