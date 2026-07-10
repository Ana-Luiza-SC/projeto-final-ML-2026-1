from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import storage
from app.main import app
from app.services import sigaa_components

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def clear_state(monkeypatch, tmp_path):
    storage.DISCIPLINES.clear()
    storage.ASSESSMENTS.clear()
    monkeypatch.setattr(sigaa_components, "CACHE_FILE", tmp_path / "sigaa_components_cache.json")
    yield
    storage.DISCIPLINES.clear()
    storage.ASSESSMENTS.clear()


@pytest.fixture
def client():
    return TestClient(app)


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def create_discipline(client: TestClient):
    response = client.post(
        "/api/disciplines",
        json={"code": "FGA0315", "name": "Qualidade de Software 1"},
    )
    assert response.status_code == 201
    return response.json()


def test_parse_fixture_with_component_found():
    response = sigaa_components.parse_sigaa_search_results(
        fixture("sigaa_component_found.html"),
        "FGA0315",
    )

    assert response.status == "found"
    assert response.component is not None
    assert response.component.code == "FGA0315"
    assert response.component.name == "QUALIDADE DE SOFTWARE 1"
    assert response.component.type == "DISCIPLINA"
    assert response.component.unit == "FCTE"
    assert response.component.workload_hours == 60
    assert response.component.syllabus
    assert response.component.current_program


def test_parse_fixture_without_result():
    response = sigaa_components.parse_sigaa_search_results(
        fixture("sigaa_component_not_found.html"),
        "FGA9999",
    )

    assert response.status == "not_found"
    assert response.component is None
    assert response.warnings


def test_endpoint_search_returns_found_with_fixture(client, monkeypatch):
    def fake_fetch(query: str) -> str:
        return fixture("sigaa_component_found.html")

    monkeypatch.setattr(sigaa_components, "_fetch_public_search_html", fake_fetch)

    response = client.get("/api/sigaa/components/search", params={"query": "FGA0315"})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "found"
    assert body["component"]["code"] == "FGA0315"
    assert body["cached"] is False


def test_endpoint_search_returns_not_found_without_breaking(client, monkeypatch):
    def fake_fetch(query: str) -> str:
        return fixture("sigaa_component_not_found.html")

    monkeypatch.setattr(sigaa_components, "_fetch_public_search_html", fake_fetch)

    response = client.get("/api/sigaa/components/search", params={"query": "FGA9999"})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "not_found"
    assert body["component"] is None
    assert body["warnings"]


def test_cache_returns_cached_true_on_second_query(client, monkeypatch):
    calls = {"count": 0}

    def fake_fetch(query: str) -> str:
        calls["count"] += 1
        return fixture("sigaa_component_found.html")

    monkeypatch.setattr(sigaa_components, "_fetch_public_search_html", fake_fetch)

    first = client.get("/api/sigaa/components/search", params={"query": "FGA0315"})
    second = client.get("/api/sigaa/components/search", params={"query": "FGA0315"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["cached"] is False
    assert second.json()["cached"] is True
    assert calls["count"] == 1


def test_parser_does_not_invent_missing_syllabus():
    html = """
    <table>
      <tr><td>FGA0315</td><td>QUALIDADE DE SOFTWARE 1</td><td>DISCIPLINA</td><td>FCTE</td><td>60</td></tr>
    </table>
    """

    response = sigaa_components.parse_sigaa_search_results(html, "FGA0315")

    assert response.status == "found"
    assert response.component is not None
    assert response.component.syllabus == ""
    assert response.component.current_program == ""


def test_no_real_sigaa_call_in_automated_tests(client, monkeypatch):
    def fail_if_called(query: str) -> str:
        raise AssertionError("network should not be called in this test")

    monkeypatch.setattr(sigaa_components, "_fetch_public_search_html", fail_if_called)
    cached_response = sigaa_components.parse_sigaa_search_results(
        fixture("sigaa_component_found.html"),
        "FGA0315",
    )
    sigaa_components.set_cached_component("FGA0315", cached_response)

    response = client.get("/api/sigaa/components/search", params={"query": "FGA0315"})

    assert response.status_code == 200
    assert response.json()["cached"] is True


def test_attach_sigaa_component_to_discipline(client):
    discipline = create_discipline(client)
    search_response = sigaa_components.parse_sigaa_search_results(
        fixture("sigaa_component_found.html"),
        "FGA0315",
    )

    response = client.patch(
        f"/api/disciplines/{discipline['id']}/sigaa-component",
        json={"component": search_response.component.model_dump()},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == "FGA0315"
    assert body["name"] == "Qualidade de Software 1"
    assert body["sigaa_code"] == "FGA0315"
    assert body["workload_hours"] == 60
    assert body["syllabus"]
    assert body["current_program"]


def test_openapi_includes_sigaa_endpoint(client):
    response = client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    assert "/api/sigaa/components/search" in schema["paths"]
    assert "/api/disciplines/{discipline_id}/sigaa-component" in schema["paths"]
