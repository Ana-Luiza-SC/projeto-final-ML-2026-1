from __future__ import annotations

import os
from pathlib import Path

import pytest
import requests
from fastapi.testclient import TestClient

from app import storage
from app.main import app
from app.services import sigaa_components

FIXTURES = Path(__file__).parent / "fixtures"


class FakeResponse:
    def __init__(
        self,
        text: str,
        status_code: int = 200,
        url: str = sigaa_components.SIGAA_COMPONENTS_URL,
    ):
        self.text = text
        self.status_code = status_code
        self.url = url
        self.history: list[FakeResponse] = []
        self.headers = {"content-type": "text/html; charset=utf-8"}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            response = requests.Response()
            response.status_code = self.status_code
            response.url = sigaa_components.SIGAA_COMPONENTS_SEARCH_URL
            raise requests.HTTPError(f"{self.status_code} error", response=response)


class FakeSession:
    def __init__(self, get_response: FakeResponse, post_response: FakeResponse):
        self.get_response = get_response
        self.post_response = post_response
        self.get_calls: list[dict[str, object]] = []
        self.post_calls: list[dict[str, object]] = []
        self.headers: dict[str, str] = {}
        self.closed = False

    def get(self, url: str, **kwargs):
        self.get_calls.append({"url": url, **kwargs})
        return self.get_response

    def post(self, url: str, **kwargs):
        self.post_calls.append({"url": url, **kwargs})
        return self.post_response

    def close(self) -> None:
        self.closed = True


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


def test_extract_viewstate_from_jsf_form():
    form = sigaa_components.extract_jsf_form(fixture("sigaa_jsf_form_initial.html"), sigaa_components.SIGAA_COMPONENTS_SEARCH_URL)

    assert form.action_url == sigaa_components.SIGAA_COMPONENTS_URL
    assert form.view_state_name == "javax.faces.ViewState"
    assert form.view_state_value == "j_id1"
    assert form.field_values["javax.faces.ViewState"] == "j_id1"
    assert form.field_values["form:nivel"] == "G"


def test_discovers_dynamic_code_field_from_label_association():
    form = sigaa_components.extract_jsf_form(fixture("sigaa_jsf_form_changed_ids.html"), sigaa_components.SIGAA_COMPONENTS_SEARCH_URL)

    assert form.code_field == "form:j_id_jsp_777777777_21"


def test_discovers_dynamic_name_field_from_label_association():
    form = sigaa_components.extract_jsf_form(fixture("sigaa_jsf_form_changed_ids.html"), sigaa_components.SIGAA_COMPONENTS_SEARCH_URL)

    assert form.name_field == "form:j_id_jsp_777777777_23"


def test_build_payload_preserves_hidden_inputs_and_button():
    form = sigaa_components.extract_jsf_form(fixture("sigaa_jsf_form_initial.html"), sigaa_components.SIGAA_COMPONENTS_SEARCH_URL)
    payload = sigaa_components.build_search_payload(form, "code", "FGA0315")

    assert payload["javax.faces.ViewState"] == "j_id1"
    assert payload["form:nivel"] == "G"
    assert payload["form:tipo"] == "0"
    assert payload["form:unidades"] == "0"
    assert payload[form.code_field] == "FGA0315"
    assert payload[form.name_field] == ""
    assert payload[form.code_checkbox] == "on"
    assert payload[form.search_button] == "Buscar Componentes"
    assert "form:checkTipo" not in payload
    assert "form:checkNome" not in payload
    assert "form:checkUnidade" not in payload


def test_payload_uses_real_checkbox_value_when_it_is_declared():
    form = sigaa_components.extract_jsf_form(
        fixture("sigaa_jsf_form_changed_ids.html"),
        sigaa_components.SIGAA_COMPONENTS_SEARCH_URL,
    )

    payload = sigaa_components.build_search_payload(form, "code", "FGA0315")

    assert payload["form:checkCodigo"] == "codigo-real"


def test_parse_component_results_found():
    response = sigaa_components.parse_component_results(
        fixture("sigaa_component_found.html"),
        "FGA0315",
    )

    assert response.status == "found"
    assert response.component is not None
    assert response.component.code == "FGA0315"
    assert response.component.name == "QUALIDADE DE SOFTWARE 1"
    assert response.component.type == "DISCIPLINA"
    assert response.component.unit is None
    assert response.component.workload_hours == 60
    assert response.component.syllabus == ""
    assert response.component.current_program == ""


def test_instructional_text_is_not_misclassified_as_jsf_validation():
    html = "<div>Informe os critérios de consulta</div>" + fixture("sigaa_component_found.html")

    response = sigaa_components.parse_component_results(html, "FGA0315")

    assert response.status == "found"


def test_parse_component_results_not_found():
    response = sigaa_components.parse_component_results(
        fixture("sigaa_component_not_found.html"),
        "FGA9999",
    )

    assert response.status == "not_found"
    assert response.component is None
    assert response.warnings


def test_parse_component_results_form_only_returns_error():
    response = sigaa_components.parse_component_results(
        fixture("sigaa_jsf_form_initial.html"),
        "FGA0315",
    )

    assert response.status == "error"
    assert response.component is None
    assert "formulário" in response.warnings[0].lower()


def test_extract_jsf_form_rejects_missing_viewstate():
    with pytest.raises(ValueError, match="ViewState ausente"):
        sigaa_components.extract_jsf_form(
            fixture("sigaa_jsf_form_missing_viewstate.html"),
            sigaa_components.SIGAA_COMPONENTS_SEARCH_URL,
        )


def test_search_sigaa_component_uses_same_session_and_posts_payload():
    fake_session = FakeSession(
        FakeResponse(fixture("sigaa_jsf_form_initial.html")),
        FakeResponse(fixture("sigaa_component_found.html")),
    )

    response = sigaa_components.search_sigaa_component("FGA0315", session=fake_session)

    assert response.status == "found"
    assert len(fake_session.get_calls) == 2
    assert len(fake_session.post_calls) == 1
    assert fake_session.get_calls[0]["url"] == sigaa_components.SIGAA_PUBLIC_HOME_URL
    assert fake_session.get_calls[1]["url"] == sigaa_components.SIGAA_COMPONENTS_SEARCH_URL
    assert fake_session.post_calls[0]["url"] == sigaa_components.SIGAA_COMPONENTS_URL
    payload = fake_session.post_calls[0]["data"]
    assert payload["javax.faces.ViewState"] == "j_id1"
    assert payload["form:nivel"] == "G"
    assert payload["form:checkCodigo"] == "on"
    assert payload["form:j_id_jsp_190531263_11"] == "FGA0315"
    assert payload["form:j_id_jsp_190531263_13"] == ""
    assert payload["form:btnBuscarComponentes"] == "Buscar Componentes"


def test_endpoint_search_returns_found_with_fixture(client, monkeypatch):
    fake_session = FakeSession(
        FakeResponse(fixture("sigaa_jsf_form_initial.html")),
        FakeResponse(fixture("sigaa_component_found.html")),
    )
    monkeypatch.setattr(sigaa_components, "_create_session", lambda: fake_session)

    response = client.get("/api/sigaa/components/search", params={"query": "FGA0315"})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "found"
    assert body["component"]["code"] == "FGA0315"
    assert len(fake_session.get_calls) == 2
    assert len(fake_session.post_calls) == 1


def test_endpoint_search_returns_not_found_without_breaking(client, monkeypatch):
    fake_session = FakeSession(
        FakeResponse(fixture("sigaa_jsf_form_initial.html")),
        FakeResponse(fixture("sigaa_component_not_found.html")),
    )
    monkeypatch.setattr(sigaa_components, "_create_session", lambda: fake_session)

    response = client.get("/api/sigaa/components/search", params={"query": "FGA9999"})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "not_found"
    assert body["component"] is None
    assert body["warnings"]


def test_cache_returns_cached_true_on_second_query(client, monkeypatch):
    cached_response = sigaa_components.parse_component_results(
        fixture("sigaa_component_found.html"),
        "FGA0315",
    )
    sigaa_components.set_cached_component("FGA0315", cached_response)

    def fail_if_called():
        raise AssertionError("network should not be called when cache is warm")

    monkeypatch.setattr(sigaa_components, "_create_session", fail_if_called)

    response = client.get("/api/sigaa/components/search", params={"query": "FGA0315"})

    assert response.status_code == 200
    assert response.json()["cached"] is True


def test_attach_sigaa_component_to_discipline(client):
    discipline = create_discipline(client)
    search_response = sigaa_components.parse_component_results(
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
    assert body["syllabus"] == ""
    assert body["current_program"] == ""


def test_openapi_includes_sigaa_endpoint(client):
    response = client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    assert "/api/sigaa/components/search" in schema["paths"]
    assert "/api/disciplines/{discipline_id}/sigaa-component" in schema["paths"]


@pytest.mark.integration
@pytest.mark.skipif(os.getenv("RUN_SIGAA_INTEGRATION") != "1", reason="SIGAA real integration disabled by default")
def test_real_sigaa_search_smoke():
    response = sigaa_components.search_sigaa_component("FGA0124")

    assert response.query == "FGA0124"
    assert response.status == "found"
    assert response.component is not None
    assert response.component.code == "FGA0124"
    assert response.component.name
