import pytest
from fastapi.testclient import TestClient
from app import storage
from app.main import app

@pytest.fixture(autouse=True)
def clear():
    storage.DISCIPLINES.clear(); storage.ASSESSMENTS.clear(); storage.ABSENCES.clear(); storage.CONTENT_NODES.clear(); storage.ASSESSMENT_CONTENT_LINKS.clear(); storage.COURSE_PLANS.clear(); storage.CONTENT_EXTRACTION_PREVIEWS.clear()
@pytest.fixture
def client(): return TestClient(app)
def discipline(client, code="EDA0001"):
    response = client.post("/api/disciplines", json={"code": code, "name": "EDA 2"}); assert response.status_code == 201; return response.json()
def node(client, discipline_id, title, parent_id=None, **extra):
    path = f"/api/disciplines/{discipline_id}/contents" if parent_id is None else f"/api/disciplines/{discipline_id}/contents/{parent_id}/children"
    response = client.post(path, json={"title": title, **extra}); assert response.status_code == 201, response.text; return response.json()
def assessment(client, discipline_id, name="Prova 1"):
    response = client.post(f"/api/disciplines/{discipline_id}/assessments", json={"name": name, "weight": 100}); assert response.status_code == 201; return response.json()

def test_create_roots_children_and_hierarchical_listing(client):
    d = discipline(client); root = node(client, d["id"], "Ordenação"); child = node(client, d["id"], "Quicksort", root["id"], difficulty="high")
    tree = client.get(f"/api/disciplines/{d['id']}/contents").json()
    assert tree[0]["title"] == "Ordenação" and tree[0]["children"][0]["id"] == child["id"]
    assert client.get(f"/api/disciplines/{d['id']}/contents/{root['id']}").json()["children"][0]["title"] == "Quicksort"

def test_edit_and_move_with_cycle_rejection(client):
    d = discipline(client); a = node(client, d["id"], "A"); b = node(client, d["id"], "B", a["id"]); c = node(client, d["id"], "C")
    edited = client.patch(f"/api/disciplines/{d['id']}/contents/{b['id']}", json={"title": "B2", "status": "studied"}); assert edited.json()["title"] == "B2"
    assert client.post(f"/api/disciplines/{d['id']}/contents/{b['id']}/move", json={"parent_id": c["id"]}).status_code == 200
    assert client.post(f"/api/disciplines/{d['id']}/contents/{c['id']}/move", json={"parent_id": b["id"]}).status_code == 409
    assert client.post(f"/api/disciplines/{d['id']}/contents/{b['id']}/move", json={"parent_id": b["id"]}).status_code == 409

def test_parent_from_other_discipline_and_html_are_rejected(client):
    one, two = discipline(client), discipline(client, "EDA0002"); parent = node(client, one["id"], "A")
    assert client.post(f"/api/disciplines/{two['id']}/contents", json={"title": "B", "parent_id": parent["id"]}).status_code == 404
    assert client.post(f"/api/disciplines/{one['id']}/contents", json={"title": "<script>x</script>"}).status_code == 422
    assert client.post(f"/api/disciplines/{one['id']}/contents", json={"title": "   "}).status_code == 422

def test_depth_limit_and_safe_delete(client):
    d = discipline(client); current = node(client, d["id"], "L1")
    for level in range(2, 6): current = node(client, d["id"], f"L{level}", current["id"])
    assert client.post(f"/api/disciplines/{d['id']}/contents/{current['id']}/children", json={"title": "L6"}).status_code == 409
    root = client.get(f"/api/disciplines/{d['id']}/contents").json()[0]
    assert client.delete(f"/api/disciplines/{d['id']}/contents/{root['id']}").status_code == 409
    assert client.delete(f"/api/disciplines/{d['id']}/contents/{current['id']}").status_code == 204

def test_association_descendants_deduplicates_and_preserves_selection(client):
    d = discipline(client); root = node(client, d["id"], "Ordenação"); quick = node(client, d["id"], "Quicksort", root["id"]); merge = node(client, d["id"], "Mergesort", root["id"]); proof = assessment(client, d["id"])
    payload = {"selections": [{"content_node_id": quick["id"], "include_descendants": False}, {"content_node_id": root["id"], "include_descendants": True}]}
    response = client.put(f"/api/disciplines/{d['id']}/assessments/{proof['id']}/content-associations", json=payload); assert response.status_code == 200
    body = response.json(); assert len(body["selections"]) == 2
    assert {item["id"] for item in body["resolved_nodes"]} == {root["id"], quick["id"], merge["id"]} and len(body["resolved_nodes"]) == 3
    assert next(item for item in body["resolved_nodes"] if item["id"] == quick["id"])["association_origin"] == "inherited"
    assert client.delete(f"/api/disciplines/{d['id']}/contents/{root['id']}").status_code == 409

def test_direct_specific_selection_and_cross_discipline_rejected(client):
    one, two = discipline(client), discipline(client, "EDA0002"); quick = node(client, one["id"], "Quicksort"); foreign = node(client, two["id"], "Grafos"); proof = assessment(client, one["id"])
    direct = client.put(f"/api/disciplines/{one['id']}/assessments/{proof['id']}/content-associations", json={"selections": [{"content_node_id": quick["id"], "include_descendants": False}]}); assert direct.status_code == 200 and len(direct.json()["resolved_nodes"]) == 1
    cross = client.put(f"/api/disciplines/{one['id']}/assessments/{proof['id']}/content-associations", json={"selections": [{"content_node_id": foreign["id"], "include_descendants": False}]}); assert cross.status_code == 404

def test_full_eda_flow_agent_fallback_uses_associated_quicksort(client, monkeypatch):
    from datetime import date, timedelta
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    d = discipline(client); ordering = node(client, d["id"], "Ordenação"); node(client, d["id"], "Quicksort", ordering["id"], difficulty="high", status="not_started"); node(client, d["id"], "Mergesort", ordering["id"], difficulty="medium", status="studied")
    proof = client.post(f"/api/disciplines/{d['id']}/assessments", json={"name": "Prova 1", "weight": 100, "date": str(date.today() + timedelta(days=2)), "status": "planned"}).json()
    assert client.put(f"/api/disciplines/{d['id']}/assessments/{proof['id']}/content-associations", json={"selections": [{"content_node_id": ordering["id"], "include_descendants": True}]}).status_code == 200
    response = client.post("/api/agent/study-recommendation", json={"discipline_id": d["id"], "target_average": 5, "pending_topics": [], "user_goal": "preparar a prova"}); assert response.status_code == 200
    body = response.json(); assert body["used_fallback"] is True and body["provider"] == "rules"
    quick_actions = [item for item in body["study_actions"] if item["topic"] == "Quicksort"]
    assert quick_actions and quick_actions[0]["strategy_id"] in {"concrete_examples", "self_explanation"}
    assert "Prova 1" in quick_actions[0]["evidence"] and "Ordenação" in quick_actions[0]["evidence"]
    assert quick_actions[0]["evidence"].startswith("Quicksort")

def test_unassociated_content_is_not_presented_as_exam_content(client):
    from datetime import date, timedelta
    d = discipline(client); associated = node(client, d["id"], "Quicksort", difficulty="high"); node(client, d["id"], "Grafos", difficulty="high")
    proof = client.post(f"/api/disciplines/{d['id']}/assessments", json={"name": "Prova 1", "weight": 100, "date": str(date.today() + timedelta(days=2)), "status": "planned"}).json()
    client.put(f"/api/disciplines/{d['id']}/assessments/{proof['id']}/content-associations", json={"selections": [{"content_node_id": associated["id"], "include_descendants": False}]})
    body = client.post("/api/agent/study-recommendation", json={"discipline_id": d["id"], "target_average": 5, "pending_topics": []}).json()
    graph = next(item for item in body["study_actions"] if item["topic"] == "Grafos")
    assert "sem associação a avaliação" in graph["evidence"] and "Prova 1" not in graph["evidence"]

def test_not_started_precedes_reviewed_and_difficulty_is_tiebreaker(client):
    from datetime import date, timedelta
    d = discipline(client); root = node(client, d["id"], "Bloco"); node(client, d["id"], "Revisado difícil", root["id"], difficulty="high", status="reviewed"); node(client, d["id"], "Novo médio", root["id"], difficulty="medium", status="not_started"); node(client, d["id"], "Novo difícil", root["id"], difficulty="high", status="not_started")
    proof = client.post(f"/api/disciplines/{d['id']}/assessments", json={"name": "P1", "weight": 100, "date": str(date.today() + timedelta(days=4)), "status": "planned"}).json()
    client.put(f"/api/disciplines/{d['id']}/assessments/{proof['id']}/content-associations", json={"selections": [{"content_node_id": root["id"], "include_descendants": True}]})
    body = client.post("/api/agent/study-recommendation", json={"discipline_id": d["id"], "target_average": 5, "pending_topics": []}).json()
    topics = [item["topic"] for item in body["study_actions"]]
    assert topics.index("Novo difícil") < topics.index("Novo médio") < topics.index("Revisado difícil")

def test_weekly_plan_uses_associated_nodes_without_changing_minutes(client):
    from datetime import date, timedelta
    d = discipline(client); root = node(client, d["id"], "Ordenação", status="studied"); node(client, d["id"], "Quicksort", root["id"], difficulty="high", status="not_started"); node(client, d["id"], "Mergesort", root["id"], status="in_progress")
    proof = client.post(f"/api/disciplines/{d['id']}/assessments", json={"name": "P1", "weight": 100, "date": str(date.today() + timedelta(days=3)), "status": "planned"}).json()
    client.put(f"/api/disciplines/{d['id']}/assessments/{proof['id']}/content-associations", json={"selections": [{"content_node_id": root["id"], "include_descendants": True}]})
    payload = {"discipline_ids": [d["id"]], "availability": {"available_hours_per_week": 1, "days_available": ["monday"]}, "max_session_minutes": 60, "priorities": [], "objective_text": "prova"}
    body = client.post("/api/study-plans/generate", json=payload).json()
    assert sum(item["duration_minutes"] for item in body["plan"]) == 60
    assert "Quicksort" in body["plan"][0]["activity"]
    assert any("ficaram pendentes" in warning and "Mergesort" in warning for warning in body["warnings"])

def confirmed_plan(discipline_id, contents=None):
    storage.save_course_plan(discipline_id, {"contents": contents if contents is not None else ["Ordenação", "Quicksort", "Mergesort"], "objectives": [], "schedule": [], "evaluation_groups": [], "assessments": [], "bibliography": []})

def test_extraction_requires_confirmed_plan(client):
    d = discipline(client)
    response = client.post(f"/api/disciplines/{d['id']}/contents/extract-preview")
    assert response.status_code == 422
    assert "Confirme um plano" in response.json()["detail"]

def test_local_preview_does_not_persist_and_confirmation_revalidates(client, monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    d = discipline(client); confirmed_plan(d["id"])
    preview = client.post(f"/api/disciplines/{d['id']}/contents/extract-preview")
    assert preview.status_code == 200
    body = preview.json()
    assert body["used_fallback"] is True and body["fallback_reason"] == "missing_api_key"
    assert client.get(f"/api/disciplines/{d['id']}/contents").json() == []
    drafts = body["draft_nodes"]
    drafts[1]["parent_temporary_id"] = drafts[0]["temporary_id"]
    drafts[1]["title"] = "Quicksort editado"
    confirmation = client.post(f"/api/disciplines/{d['id']}/contents/confirm-preview", json={"preview_id": body["preview_id"], "draft_nodes": drafts})
    assert confirmation.status_code == 200, confirmation.text
    assert confirmation.json()["created_count"] == 3
    tree = client.get(f"/api/disciplines/{d['id']}/contents").json()
    quick = tree[0]["children"][0]
    assert quick["title"] == "Quicksort editado" and quick["status"] == "not_started" and quick["difficulty"] is None
    assert client.post(f"/api/disciplines/{d['id']}/contents/confirm-preview", json={"preview_id": body["preview_id"], "draft_nodes": drafts}).status_code == 422

def test_valid_agent_preview_is_structured_and_auditable(client, monkeypatch):
    from app.services import content_extraction
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    d = discipline(client); confirmed_plan(d["id"], ["Unidade 3 — Métodos de ordenação", "Quicksort"])
    monkeypatch.setattr(content_extraction, "generate_google_json", lambda prompt, timeout: {"draft_nodes": [
        {"temporary_id": "root", "parent_temporary_id": None, "title": "Ordenação", "description": "Métodos de ordenação", "source_evidence": "Unidade 3 — Métodos de ordenação", "confidence": .94, "warnings": []},
        {"temporary_id": "quick", "parent_temporary_id": "root", "title": "Quicksort", "description": None, "source_evidence": "Quicksort", "confidence": .9, "warnings": ["Hierarquia proposta para revisão humana."]},
    ]})
    body = client.post(f"/api/disciplines/{d['id']}/contents/extract-preview").json()
    assert body["source"] == "gemini" and body["used_fallback"] is False
    assert body["draft_nodes"][1]["parent_temporary_id"] == "root"
    assert body["draft_nodes"][1]["source_evidence"] == "Quicksort"

@pytest.mark.parametrize("failure,reason", [(ValueError("bad json"), "invalid_response"), (TimeoutError("timeout"), "timeout"), (RuntimeError("down"), "unavailable")])
def test_invalid_or_unavailable_agent_uses_identified_fallback(client, monkeypatch, failure, reason):
    from app.services import content_extraction
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    d = discipline(client); confirmed_plan(d["id"], ["Árvores AVL"])
    def fail(prompt, timeout): raise failure
    monkeypatch.setattr(content_extraction, "generate_google_json", fail)
    body = client.post(f"/api/disciplines/{d['id']}/contents/extract-preview").json()
    assert body["source"] == "local_fallback" and body["fallback_reason"] == reason
    assert body["draft_nodes"][0]["title"] == "Árvores AVL"

def test_invented_evidence_uses_fallback(client, monkeypatch):
    from app.services import content_extraction
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    d = discipline(client); confirmed_plan(d["id"], ["Busca binária"])
    monkeypatch.setattr(content_extraction, "generate_google_json", lambda prompt, timeout: {"draft_nodes": [{"temporary_id": "x", "parent_temporary_id": None, "title": "Redes neurais", "description": None, "source_evidence": "Redes neurais", "confidence": .99, "warnings": []}]})
    body = client.post(f"/api/disciplines/{d['id']}/contents/extract-preview").json()
    assert body["fallback_reason"] == "invalid_response"
    assert body["draft_nodes"][0]["title"] == "Busca binária"

def test_confirmation_rejects_cycle_without_partial_persistence(client, monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    d = discipline(client); confirmed_plan(d["id"], ["A", "B"])
    preview = client.post(f"/api/disciplines/{d['id']}/contents/extract-preview").json()
    drafts = preview["draft_nodes"]
    drafts[0]["parent_temporary_id"] = drafts[1]["temporary_id"]
    drafts[1]["parent_temporary_id"] = drafts[0]["temporary_id"]
    response = client.post(f"/api/disciplines/{d['id']}/contents/confirm-preview", json={"preview_id": preview["preview_id"], "draft_nodes": drafts})
    assert response.status_code == 422 and "ciclo" in response.json()["detail"]
    assert storage.CONTENT_NODES[d["id"]] == {}

def test_empty_confirmed_plan_returns_friendly_empty_preview(client, monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    d = discipline(client); confirmed_plan(d["id"], [])
    body = client.post(f"/api/disciplines/{d['id']}/contents/extract-preview").json()
    assert body["draft_nodes"] == [] and body["fallback_reason"] == "no_explicit_content"
    assert "cadastro manual" not in str(body).lower() or body["warnings"]

def test_expired_or_foreign_preview_cannot_be_confirmed(client, monkeypatch):
    from datetime import timedelta
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    one, two = discipline(client), discipline(client, "EDA0002"); confirmed_plan(one["id"], ["A"])
    preview = client.post(f"/api/disciplines/{one['id']}/contents/extract-preview").json()
    foreign = client.post(f"/api/disciplines/{two['id']}/contents/confirm-preview", json={"preview_id": preview["preview_id"], "draft_nodes": preview["draft_nodes"]})
    assert foreign.status_code == 422
    storage.CONTENT_EXTRACTION_PREVIEWS[preview["preview_id"]]["expires_at"] = storage.utc_now() - timedelta(seconds=1)
    expired = client.post(f"/api/disciplines/{one['id']}/contents/confirm-preview", json={"preview_id": preview["preview_id"], "draft_nodes": preview["draft_nodes"]})
    assert expired.status_code == 422

def test_extraction_logs_only_metadata(client, monkeypatch, caplog):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    d = discipline(client); confirmed_plan(d["id"], ["Conteúdo privado da disciplina"])
    with caplog.at_level("INFO", logger="estudaunb.content_extraction"):
        client.post(f"/api/disciplines/{d['id']}/contents/extract-preview")
    logs = " ".join(record.getMessage() for record in caplog.records)
    assert "Conteúdo privado" not in logs and "node_count=1" in logs and d["id"] in logs

def test_deleting_assessment_removes_its_content_selection(client):
    d = discipline(client); content = node(client, d["id"], "Quicksort"); proof = assessment(client, d["id"])
    client.put(f"/api/disciplines/{d['id']}/assessments/{proof['id']}/content-associations", json={"selections": [{"content_node_id": content["id"], "include_descendants": False}]})
    assert proof["id"] in storage.ASSESSMENT_CONTENT_LINKS
    assert client.delete(f"/api/disciplines/{d['id']}/assessments/{proof['id']}").status_code == 204
    assert proof["id"] not in storage.ASSESSMENT_CONTENT_LINKS
