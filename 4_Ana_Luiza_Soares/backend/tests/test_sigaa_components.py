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
        self.get_responses = list(get_response) if isinstance(get_response, (list, tuple)) else None
        self.post_response = post_response
        self.post_responses = list(post_response) if isinstance(post_response, (list, tuple)) else None
        self.get_calls: list[dict[str, object]] = []
        self.post_calls: list[dict[str, object]] = []
        self.headers: dict[str, str] = {}
        self.closed = False

    def _resolve(self, value):
        if isinstance(value, BaseException):
            raise value
        return value

    def get(self, url: str, **kwargs):
        self.get_calls.append({"url": url, **kwargs})
        if self.get_responses is not None:
            return self._resolve(self.get_responses.pop(0))
        return self._resolve(self.get_response)

    def post(self, url: str, **kwargs):
        self.post_calls.append({"url": url, **kwargs})
        if self.post_responses is not None:
            return self._resolve(self.post_responses.pop(0))
        return self._resolve(self.post_response)

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
        [FakeResponse(fixture("sigaa_jsf_form_initial.html")), FakeResponse(fixture("sigaa_jsf_form_initial.html")), FakeResponse(fixture("sigaa_turma_search_form.html"), url=sigaa_components.SIGAA_TURMAS_URL)],
        [FakeResponse(fixture("sigaa_component_found.html")), FakeResponse(fixture("sigaa_turma_result_dynamic_id.html"), url=sigaa_components.SIGAA_TURMAS_URL), FakeResponse(fixture("sigaa_turma_detail.html"), url=sigaa_components.SIGAA_TURMAS_URL)],
    )

    response = sigaa_components.search_sigaa_component("FGA0315", session=fake_session)

    assert response.status == "found"
    assert response.component.syllabus == "Qualidade de produto, processo e medição de software."
    assert response.component.details_processed is True
    assert len(fake_session.get_calls) == 3
    assert len(fake_session.post_calls) == 3
    assert fake_session.get_calls[0]["url"] == sigaa_components.SIGAA_PUBLIC_HOME_URL
    assert fake_session.get_calls[1]["url"] == sigaa_components.SIGAA_COMPONENTS_SEARCH_URL
    assert fake_session.post_calls[0]["url"] == sigaa_components.SIGAA_COMPONENTS_URL
    assert fake_session.post_calls[1]["url"] == sigaa_components.SIGAA_TURMAS_URL
    assert fake_session.post_calls[2]["url"] == sigaa_components.SIGAA_TURMAS_URL
    payload = fake_session.post_calls[0]["data"]
    assert payload["javax.faces.ViewState"] == "j_id1"
    assert payload["form:nivel"] == "G"
    assert payload["form:checkCodigo"] == "on"
    assert payload["form:j_id_jsp_190531263_11"] == "FGA0315"
    assert payload["form:j_id_jsp_190531263_13"] == ""
    assert payload["form:btnBuscarComponentes"] == "Buscar Componentes"
    turma_search_payload = fake_session.post_calls[1]["data"]
    assert (
        turma_search_payload["formTurma:j_id_jsp_987654321_44"] == "Buscar"
    )
    detail_payload = fake_session.post_calls[2]["data"]
    assert detail_payload["formTurma"] == "formTurma"
    assert detail_payload["formTurma:inputDepto"] == "673"
    assert detail_payload["formTurma:inputAno"] == "2026"
    assert detail_payload["formTurma:inputPeriodo"] == "2"
    assert detail_payload["javax.faces.ViewState"] == "turma-vs-result"
    assert detail_payload["formTurma:aqui"] == "formTurma:aqui"
    assert detail_payload["id"] == "316553"
    assert detail_payload["publico"] == "public"


def test_endpoint_search_returns_found_with_fixture(client, monkeypatch):
    fake_session = FakeSession(
        [FakeResponse(fixture("sigaa_jsf_form_initial.html")), FakeResponse(fixture("sigaa_jsf_form_initial.html")), FakeResponse(fixture("sigaa_turma_search_form.html"), url=sigaa_components.SIGAA_TURMAS_URL)],
        [FakeResponse(fixture("sigaa_component_found.html")), FakeResponse(fixture("sigaa_turma_result_dynamic_id.html"), url=sigaa_components.SIGAA_TURMAS_URL), FakeResponse(fixture("sigaa_turma_detail.html"), url=sigaa_components.SIGAA_TURMAS_URL)],
    )
    monkeypatch.setattr(sigaa_components, "_create_session", lambda: fake_session)

    response = client.get("/api/sigaa/components/search", params={"query": "FGA0315"})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "found"
    assert body["component"]["code"] == "FGA0315"
    assert len(fake_session.get_calls) == 3
    assert len(fake_session.post_calls) == 3


def test_endpoint_search_returns_not_found_without_breaking(client, monkeypatch):
    fake_session = FakeSession(
        [FakeResponse(fixture("sigaa_jsf_form_initial.html")), FakeResponse(fixture("sigaa_jsf_form_initial.html")), FakeResponse(fixture("sigaa_turma_search_form.html"), url=sigaa_components.SIGAA_TURMAS_URL)],
        [FakeResponse(fixture("sigaa_component_not_found.html"))],
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
        "FGA0315", fixture("sigaa_turma_detail.html"), details_processed=True,
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
    catalog = storage.get_catalog_component("FGA0315")
    assert body["syllabus"] == catalog["syllabus"]
    assert (body["current_program"] or "") == catalog["current_program"]


def test_openapi_includes_sigaa_endpoint(client):
    response = client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    assert "/api/sigaa/components/search" in schema["paths"]
    assert "/api/disciplines/{discipline_id}/sigaa-component" in schema["paths"]


@pytest.mark.integration
@pytest.mark.skipif(os.getenv("RUN_SIGAA_INTEGRATION") != "1", reason="SIGAA real integration disabled by default")
def test_real_sigaa_search_smoke():
    response = sigaa_components.search_sigaa_component(
        "FGA0003", force_refresh=True
    )
    assert response.status == "found"
    assert response.component is not None
    assert response.component.syllabus
    assert response.component.details_processed is True
    assert response.component.code == "FGA0003"
    assert response.component.name


def test_catalog_refresh_bypasses_search_cache(client, monkeypatch):
    from app.routers import catalog

    discipline = create_discipline(client)
    enriched = sigaa_components.parse_component_results(
        fixture("sigaa_component_found.html"),
        "FGA0315",
        fixture("sigaa_turma_detail.html"),
        details_processed=True,
    )
    calls = []

    def fake_search(query, force_refresh=False):
        calls.append((query, force_refresh))
        return enriched

    monkeypatch.setattr(catalog, "search_sigaa_component", fake_search)
    response = client.post(
        f"/api/disciplines/{discipline['id']}/catalog-refresh"
    )

    assert response.status_code == 200
    assert calls == [("FGA0315", True)]
    assert response.json()["syllabus"]

def test_detail_redirect_to_login_is_rejected():
    session = FakeSession(FakeResponse("login", url="https://sigaa.unb.br/sigaa/logar.do"), FakeResponse(""))
    with pytest.raises(sigaa_components.SigaaSessionRedirectError):
        sigaa_components.fetch_component_details(session, "/sigaa/public/componentes/detalhe.jsf?id=1", sigaa_components.SIGAA_COMPONENTS_URL)

def test_incomplete_legacy_cache_is_invalidated():
    legacy = sigaa_components.parse_component_results(fixture("sigaa_component_found.html"), "FGA0315")
    sigaa_components._write_cache({"FGA0315": legacy.model_dump(mode="json")})
    assert sigaa_components.get_cached_component("FGA0315") is None


def test_current_failed_detail_cache_is_retried_instead_of_reused():
    basic = sigaa_components.parse_component_results(
        fixture("sigaa_component_found.html"), "FGA0315"
    )
    sigaa_components.set_cached_component("FGA0315", basic)

    assert sigaa_components.get_cached_component("FGA0315") is None


def test_dynamic_turma_search_submit_is_discovered_by_semantics():
    name, value = sigaa_components._extract_turma_search_submit(
        fixture("sigaa_turma_search_form.html")
    )

    assert name == "formTurma:j_id_jsp_987654321_44"
    assert value == "Buscar"
    assert all(
        "j_id_jsp" not in key
        for key in sigaa_components.build_turma_search_payload("view-state")
    )

def test_detail_without_syllabus_does_not_invent_value():
    details = sigaa_components.parse_sigaa_component_details("<div><b>Programa atual:</b> Unidade 1</div>", "https://sigaa.unb.br/sigaa/public/x")
    assert details["syllabus"] == ""


def test_extract_turma_detail_id_from_dynamic_result_page():
    turma_id = sigaa_components.extract_turma_detail_id(
        fixture("sigaa_turma_result_dynamic_id.html"),
        "FGA0315",
    )

    assert turma_id == "316553"


def test_extract_turma_detail_id_with_changed_jsp_identifier():
    turma_id = sigaa_components.extract_turma_detail_id(
        fixture("sigaa_turma_result_changed_jids.html"),
        "FGA0315",
    )

    assert turma_id == "316554"


def test_extract_turma_detail_id_returns_none_for_malformed_result_link():
    assert sigaa_components.extract_turma_detail_id(fixture("sigaa_turma_result_malformed_link.html"), "FGA0315") is None


def test_parse_turma_detail_semantic_labels_with_colons():
    details = sigaa_components.parse_sigaa_component_details(
        fixture("sigaa_turma_detail.html"),
        sigaa_components.SIGAA_TURMAS_URL,
    )

    assert details["code"] == "FGA0315"
    assert details["name"] == "QUALIDADE DE SOFTWARE 1"
    assert details["prerequisites"] == "FGA0001"
    assert details["syllabus"] == "Qualidade de produto, processo e medição de software."
    assert details["theoretical_workload_hours"] == "30 h"
    assert details["practical_workload_hours"] == "30 h"


def test_turma_detail_missing_syllabus_does_not_invent_value():
    response = sigaa_components.parse_component_results(
        fixture("sigaa_component_found.html"),
        "FGA0315",
        fixture("sigaa_turma_detail_missing_syllabus.html"),
        details_processed=True,
    )

    assert response.component is not None
    assert response.component.syllabus == ""
    assert response.component.details_processed is True
    assert response.component.workload_hours == 60


def test_empty_refresh_does_not_erase_persisted_syllabus(client):
    discipline = create_discipline(client)
    enriched = sigaa_components.parse_component_results(
        fixture("sigaa_component_found.html"),
        "FGA0315",
        fixture("sigaa_turma_detail.html"),
        details_processed=True,
    )
    attached = client.patch(
        f"/api/disciplines/{discipline['id']}/sigaa-component",
        json={"component": enriched.component.model_dump()},
    )
    assert attached.status_code == 200
    expected = attached.json()["syllabus"]
    assert expected

    basic = sigaa_components.parse_component_results(
        fixture("sigaa_component_found.html"), "FGA0315"
    )
    refreshed = client.patch(
        f"/api/disciplines/{discipline['id']}/sigaa-component",
        json={"component": basic.component.model_dump()},
    )

    assert refreshed.status_code == 200
    assert refreshed.json()["syllabus"] == expected


def test_turma_detail_missing_workload_preserves_primary_workload():
    response = sigaa_components.parse_component_results(
        fixture("sigaa_component_found.html"),
        "FGA0315",
        fixture("sigaa_turma_detail_missing_workload.html"),
        details_processed=True,
    )

    assert response.component is not None
    assert response.component.syllabus == "Qualidade de produto, processo e medição de software."
    assert response.component.workload_hours == 60
    assert response.component.theoretical_workload_hours is None
    assert response.component.practical_workload_hours is None


def test_expired_turma_viewstate_preserves_basic_component_data():
    fake_session = FakeSession(
        [FakeResponse(fixture("sigaa_jsf_form_initial.html")), FakeResponse(fixture("sigaa_jsf_form_initial.html")), FakeResponse(fixture("sigaa_turma_search_form.html"), url=sigaa_components.SIGAA_TURMAS_URL)],
        [FakeResponse(fixture("sigaa_component_found.html")), FakeResponse(fixture("sigaa_turma_result_dynamic_id.html"), url=sigaa_components.SIGAA_TURMAS_URL), FakeResponse(fixture("sigaa_turma_detail_expired_viewstate.html"), url=sigaa_components.SIGAA_TURMAS_URL)],
    )

    response = sigaa_components.search_sigaa_component("FGA0315", session=fake_session)

    assert response.status == "found"
    assert response.component is not None
    assert response.component.code == "FGA0315"
    assert response.component.name == "QUALIDADE DE SOFTWARE 1"
    assert response.component.details_processed is False
    assert response.warnings


def test_turma_detail_timeout_preserves_basic_component_data():
    fake_session = FakeSession(
        [FakeResponse(fixture("sigaa_jsf_form_initial.html")), FakeResponse(fixture("sigaa_jsf_form_initial.html")), FakeResponse(fixture("sigaa_turma_search_form.html"), url=sigaa_components.SIGAA_TURMAS_URL)],
        [FakeResponse(fixture("sigaa_component_found.html")), FakeResponse(fixture("sigaa_turma_result_dynamic_id.html"), url=sigaa_components.SIGAA_TURMAS_URL), requests.Timeout("timeout")],
    )

    response = sigaa_components.search_sigaa_component("FGA0315", session=fake_session)

    assert response.status == "found"
    assert response.component is not None
    assert response.component.code == "FGA0315"
    assert response.component.name == "QUALIDADE DE SOFTWARE 1"
    assert response.component.syllabus == ""
    assert response.warnings


def test_external_domain_rejected_for_public_sigaa_url():
    with pytest.raises(sigaa_components.SigaaSessionRedirectError):
        sigaa_components.fetch_component_details(
            FakeSession(FakeResponse("", url="https://evil.example/sigaa/public/x"), FakeResponse("")),
            "https://evil.example/sigaa/public/componentes/detalhe.jsf?id=1",
            sigaa_components.SIGAA_COMPONENTS_URL,
        )


def test_malformed_turma_result_preserves_code_and_name():
    fake_session = FakeSession(
        [FakeResponse(fixture("sigaa_jsf_form_initial.html")), FakeResponse(fixture("sigaa_jsf_form_initial.html")), FakeResponse(fixture("sigaa_turma_search_form.html"), url=sigaa_components.SIGAA_TURMAS_URL)],
        [FakeResponse(fixture("sigaa_component_found.html")), FakeResponse(fixture("sigaa_turma_result_malformed_link.html"), url=sigaa_components.SIGAA_TURMAS_URL)],
    )

    response = sigaa_components.search_sigaa_component("FGA0315", session=fake_session)

    assert response.status == "found"
    assert response.component is not None
    assert response.component.code == "FGA0315"
    assert response.component.name == "QUALIDADE DE SOFTWARE 1"
    assert response.component.syllabus == ""
    assert response.warnings


def test_cache_file_stores_parser_metadata_and_detail_status():
    response = sigaa_components.parse_component_results(
        fixture("sigaa_component_found.html"),
        "FGA0315",
        fixture("sigaa_turma_detail.html"),
        details_processed=True,
    )

    assert response.component is not None
    response.component.source_url = sigaa_components.SIGAA_TURMAS_URL
    sigaa_components.set_cached_component("FGA0315", response)
    cached = sigaa_components._read_cache()["FGA0315"]

    assert cached["metadata"]["parser_version"] == sigaa_components.CACHE_PARSER_VERSION
    assert cached["metadata"]["source_url"] == sigaa_components.SIGAA_TURMAS_URL
    assert cached["metadata"]["fetched_at"]
    assert cached["metadata"]["detail_status"] == "detail_found"
