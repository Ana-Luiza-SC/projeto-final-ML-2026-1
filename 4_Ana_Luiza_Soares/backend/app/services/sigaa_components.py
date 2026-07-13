from __future__ import annotations

import json
import logging
import re
import threading
import time
import unicodedata
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from bs4.element import Tag

from app.schemas import SigaaComponent, SigaaComponentSearchResponse

logger = logging.getLogger(__name__)

SIGAA_COMPONENTS_URL = "https://sigaa.unb.br/sigaa/public/componentes/busca_componentes.jsf"
SIGAA_COMPONENTS_SEARCH_URL = SIGAA_COMPONENTS_URL + "?nivel=G&aba=p-graduacao"
SIGAA_TURMAS_URL = "https://sigaa.unb.br/sigaa/public/turmas/listar.jsf"
SIGAA_PUBLIC_HOME_URL = "https://sigaa.unb.br/sigaa/public/home.jsf"
SIGAA_ORIGIN = "https://sigaa.unb.br"
SIGAA_ALLOWED_HOST = "sigaa.unb.br"
SOURCE = "sigaa_public_components"
USER_AGENT = "EstudaUnB/0.1 public-components-lookup"
TIMEOUT_SECONDS = 6
MAX_RESPONSE_BYTES = 1_000_000
CACHE_PARSER_VERSION = "sigaa-components-v4-turma-search-submit"
SIGAA_TURMA_SEARCH_FIELDS = {
    "formTurma": "formTurma",
    "formTurma:inputNivel": "",
    "formTurma:inputDepto": "673",
    "formTurma:inputAno": "2026",
    "formTurma:inputPeriodo": "2",
}
MIN_REQUEST_INTERVAL_SECONDS = 0.25
_rate_lock = threading.Lock()
_last_public_request = 0.0
CACHE_FILE = Path(__file__).resolve().parents[1] / "cache" / "sigaa_components_cache.json"


@dataclass(slots=True)
class JsfSearchForm:
    action_url: str
    field_values: dict[str, str]
    hidden_fields: dict[str, str]
    view_state_name: str
    view_state_value: str
    code_field: str | None
    name_field: str | None
    type_field: str | None
    unit_field: str | None
    code_checkbox: str | None
    code_checkbox_value: str | None
    name_checkbox: str | None
    name_checkbox_value: str | None
    unit_checkbox: str | None
    search_button: str | None
    search_button_value: str | None


class SigaaSessionRedirectError(ValueError):
    pass


class SigaaResponseTooLargeError(ValueError):
    pass


def normalize_query(query: str) -> str:
    return " ".join(query.strip().upper().split())


def _strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _normalize_text(text: str) -> str:
    return " ".join(_strip_accents(text).casefold().split())


def _public_sigaa_url(url: str, base_url: str = SIGAA_COMPONENTS_URL) -> str:
    resolved = urljoin(base_url, url)
    parsed = urlparse(resolved)
    path = parsed.path.casefold()
    if parsed.scheme != "https" or parsed.netloc != SIGAA_ALLOWED_HOST or not path.startswith("/sigaa/public/") or "login" in path:
        raise SigaaSessionRedirectError("URL fora da área pública permitida do SIGAA.")
    return resolved


def _response_text(response: requests.Response) -> str:
    content_length = response.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > MAX_RESPONSE_BYTES:
        raise SigaaResponseTooLargeError("Resposta do SIGAA excedeu o limite permitido.")
    text = response.text
    if len(text.encode(getattr(response, "encoding", None) or "utf-8", errors="ignore")) > MAX_RESPONSE_BYTES:
        raise SigaaResponseTooLargeError("Resposta do SIGAA excedeu o limite permitido.")
    return text


def _empty_response(status: str, query: str, warning: str) -> SigaaComponentSearchResponse:
    return SigaaComponentSearchResponse(
        status=status,
        source=SOURCE,
        query=query,
        component=None,
        cached=False,
        warnings=[warning],
    )


def _read_cache() -> dict[str, Any]:
    if not CACHE_FILE.exists():
        return {}
    try:
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _write_cache(cache: dict[str, Any]) -> None:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cache_detail_status(response: SigaaComponentSearchResponse) -> str:
    if response.component is None:
        return response.status
    if response.component.details_processed:
        return "detail_found"
    return "detail_unavailable"


def get_cached_component(query: str) -> SigaaComponentSearchResponse | None:
    cache_key = normalize_query(query)
    cached = _read_cache().get(cache_key)
    if not cached:
        return None

    metadata: dict[str, Any] = {}
    payload = cached
    if isinstance(cached, dict) and "response" in cached:
        metadata = cached.get("metadata") or {}
        payload = cached.get("response") or {}
        if metadata.get("parser_version") != CACHE_PARSER_VERSION:
            return None
        if metadata.get("detail_status") == "detail_unavailable":
            return None

    response = SigaaComponentSearchResponse.model_validate(payload)
    if response.component is not None and not response.component.details_processed and not metadata.get("detail_status"):
        return None
    response.cached = True
    return response


def set_cached_component(query: str, response: SigaaComponentSearchResponse) -> None:
    cache_key = normalize_query(query)
    cache = _read_cache()
    payload = response.model_dump(mode="json")
    payload["cached"] = False
    cache[cache_key] = {
        "metadata": {
            "parser_version": CACHE_PARSER_VERSION,
            "source_url": response.component.source_url if response.component else SIGAA_COMPONENTS_URL,
            "fetched_at": _utc_iso(),
            "detail_status": _cache_detail_status(response),
        },
        "response": payload,
    }
    _write_cache(cache)


def _text(element: Any) -> str:
    if element is None:
        return ""
    return " ".join(element.get_text(" ", strip=True).split())


def _control_name(control: Tag) -> str | None:
    return control.get("name") or control.get("id")


def _control_value(control: Tag) -> str:
    if control.name == "textarea":
        return control.get_text("", strip=False)
    if control.name == "select":
        selected = control.find("option", selected=True)
        if selected is not None:
            return selected.get("value") or _text(selected)
        option = control.find("option")
        return option.get("value") or _text(option) if option is not None else ""
    return control.get("value", "")


def _first_control(container: Tag) -> Tag | None:
    return container.find(["input", "select", "textarea"])


def _resolve_control_from_label(label: Tag, form: Tag) -> Tag | None:
    target_id = label.get("for")
    if target_id:
        control = form.find(attrs={"id": target_id})
        if isinstance(control, Tag) and control.name in {"input", "select", "textarea"}:
            return control

    wrapped = label.find(["input", "select", "textarea"])
    if isinstance(wrapped, Tag):
        return wrapped

    parent = label.parent
    if isinstance(parent, Tag):
        sibling_control = parent.find(["input", "select", "textarea"])
        if isinstance(sibling_control, Tag) and sibling_control is not label:
            return sibling_control

    next_control = label.find_next(["input", "select", "textarea"])
    if isinstance(next_control, Tag):
        return next_control
    return None


def find_field_by_label(form: Tag, label_text: str) -> str | None:
    target = _normalize_text(label_text)
    for label in form.find_all("label"):
        label_value = _normalize_text(_text(label))
        if target not in label_value and label_value not in target:
            continue
        control = _resolve_control_from_label(label, form)
        if control is not None:
            return _control_name(control)

    for container in form.find_all(["tr", "div", "p", "li", "td", "th", "span"]):
        container_text = _normalize_text(_text(container))
        if target not in container_text and container_text not in target:
            continue
        control = _first_control(container)
        if control is not None:
            return _control_name(control)
    return None


def _find_control_by_name_suffix(form: Tag, suffix: str) -> str | None:
    for control in form.find_all(["input", "select", "textarea", "button"]):
        name = control.get("name") or ""
        control_id = control.get("id") or ""
        if name.endswith(suffix) or control_id.endswith(suffix):
            return _control_name(control)
    return None


def _find_control(form: Tag, name: str | None) -> Tag | None:
    if not name:
        return None
    control = form.find(attrs={"name": name}) or form.find(attrs={"id": name})
    return control if isinstance(control, Tag) else None


def _checkbox_value(form: Tag, name: str | None) -> str | None:
    control = _find_control(form, name)
    if control is None:
        return None
    return control.get("value", "on")


def _find_related_text_field(form: Tag, checkbox_name: str | None, label_text: str) -> str | None:
    checkbox = _find_control(form, checkbox_name)
    if checkbox is not None:
        row = checkbox.find_parent("tr")
        if isinstance(row, Tag):
            control = row.find(
                "input",
                attrs={"type": lambda value: (value or "text").lower() in {"text", "search"}},
            )
            if isinstance(control, Tag):
                return _control_name(control)
            textarea = row.find("textarea")
            if isinstance(textarea, Tag):
                return _control_name(textarea)

    target = _normalize_text(label_text)
    for row in form.find_all("tr"):
        if target not in _normalize_text(_text(row)):
            continue
        control = row.find(
            "input",
            attrs={"type": lambda value: (value or "text").lower() in {"text", "search"}},
        )
        if isinstance(control, Tag):
            return _control_name(control)
        textarea = row.find("textarea")
        if isinstance(textarea, Tag):
            return _control_name(textarea)
    return find_field_by_label(form, label_text)


def _select_semantic_option(form: Tag, field_suffix: str, option_text: str) -> tuple[str | None, str | None]:
    field_name = _find_control_by_name_suffix(form, field_suffix)
    control = _find_control(form, field_name)
    if control is None or control.name != "select":
        return field_name, None

    expected = _normalize_text(option_text)
    for option in control.find_all("option"):
        if _normalize_text(_text(option)) == expected:
            return field_name, option.get("value") or _text(option)
    return field_name, None


def _is_search_submit(control: Tag) -> bool:
    identifier = " ".join(
        part
        for part in [
            control.get("name") or "",
            control.get("id") or "",
            control.get("value") or "",
            _text(control),
        ]
        if part
    )
    normalized = _normalize_text(identifier)
    return "buscar" in normalized and "cancelar" not in normalized


def _collect_form_state(form: Tag) -> tuple[dict[str, str], dict[str, str], str | None, str | None]:
    field_values: dict[str, str] = {}
    hidden_fields: dict[str, str] = {}
    search_button: str | None = None
    search_button_value: str | None = None

    for control in form.find_all(["input", "select", "textarea"]):
        name = _control_name(control)
        if not name:
            continue

        if control.name == "input":
            input_type = (control.get("type") or "text").lower()
            if input_type in {"submit", "button", "image", "reset"}:
                if search_button is None and _is_search_submit(control):
                    search_button = name
                    search_button_value = control.get("value") or _text(control) or "Buscar"
                continue
            if input_type == "checkbox":
                if control.has_attr("checked"):
                    field_values[name] = control.get("value") or "on"
                continue
            if input_type == "radio":
                if control.has_attr("checked"):
                    field_values[name] = control.get("value") or "on"
                continue
            value = control.get("value", "")
            field_values[name] = value
            if input_type == "hidden":
                hidden_fields[name] = value
            continue

        if control.name == "select":
            field_values[name] = _control_value(control)
            continue

        if control.name == "textarea":
            field_values[name] = _control_value(control)

    return field_values, hidden_fields, search_button, search_button_value


def _find_form(html: str) -> tuple[BeautifulSoup, Tag]:
    soup = BeautifulSoup(html, "html.parser")
    forms = soup.find_all("form")
    if not forms:
        raise ValueError("Formulário JSF não encontrado na página do SIGAA.")

    for form in forms:
        action = form.get("action") or ""
        form_id = form.get("id") or ""
        form_name = form.get("name") or ""
        if "busca_componentes.jsf" in action or form_id == "form" or form_name == "form":
            return soup, form

    return soup, forms[0]


def extract_jsf_form(html: str, base_url: str) -> JsfSearchForm:
    soup, form = _find_form(html)
    action_url = urljoin(base_url, form.get("action") or base_url)
    field_values, hidden_fields, search_button, search_button_value = _collect_form_state(form)

    view_state_name = "javax.faces.ViewState"
    view_state_value = field_values.get(view_state_name) or hidden_fields.get(view_state_name) or ""
    if not view_state_value:
        raise ValueError("ViewState ausente no formulário do SIGAA.")

    type_field = _find_control_by_name_suffix(form, "tipo")
    unit_field = _find_control_by_name_suffix(form, "unidades")
    code_checkbox = _find_control_by_name_suffix(form, "checkCodigo")
    name_checkbox = _find_control_by_name_suffix(form, "checkNome")
    unit_checkbox = _find_control_by_name_suffix(form, "checkUnidade")
    code_field = _find_related_text_field(form, code_checkbox, "Código do Componente")
    name_field = _find_related_text_field(form, name_checkbox, "Nome do Componente")

    level_field, graduation_value = _select_semantic_option(form, "nivel", "Graduação")
    if not level_field or graduation_value is None:
        raise ValueError("Opção de nível Graduação não encontrada no formulário do SIGAA.")
    field_values[level_field] = graduation_value

    logger.info(
        "SIGAA form encontrado action=%s viewstate=%s",
        action_url,
        "present",
    )
    logger.info(
        "SIGAA campos descobertos code=%s name=%s tipo=%s unidades=%s checkCodigo=%s checkNome=%s checkUnidade=%s submit=%s",
        code_field or "missing",
        name_field or "missing",
        type_field or "missing",
        unit_field or "missing",
        code_checkbox or "missing",
        name_checkbox or "missing",
        unit_checkbox or "missing",
        search_button or "missing",
    )

    return JsfSearchForm(
        action_url=action_url,
        field_values=field_values,
        hidden_fields=hidden_fields,
        view_state_name=view_state_name,
        view_state_value=view_state_value,
        code_field=code_field,
        name_field=name_field,
        type_field=type_field,
        unit_field=unit_field,
        code_checkbox=code_checkbox,
        code_checkbox_value=_checkbox_value(form, code_checkbox),
        name_checkbox=name_checkbox,
        name_checkbox_value=_checkbox_value(form, name_checkbox),
        unit_checkbox=unit_checkbox,
        search_button=search_button,
        search_button_value=search_button_value,
    )


def _looks_like_component_code(query: str) -> bool:
    return bool(query) and " " not in query and any(char.isdigit() for char in query)


def build_search_payload(form_data: JsfSearchForm, search_type: str, value: str) -> dict[str, str]:
    payload = dict(form_data.field_values)
    value = value.strip()

    if search_type == "code":
        if form_data.code_field:
            payload[form_data.code_field] = value
        if form_data.name_field:
            payload[form_data.name_field] = ""
        if form_data.name_checkbox:
            payload.pop(form_data.name_checkbox, None)
        if form_data.code_checkbox:
            payload[form_data.code_checkbox] = form_data.code_checkbox_value or "on"
    elif search_type == "name":
        if form_data.name_field:
            payload[form_data.name_field] = value
        if form_data.code_field:
            payload[form_data.code_field] = ""
        if form_data.code_checkbox:
            payload.pop(form_data.code_checkbox, None)
        if form_data.name_checkbox:
            payload[form_data.name_checkbox] = form_data.name_checkbox_value or "on"
    else:
        raise ValueError(f"Tipo de busca inválido: {search_type!r}")

    if form_data.search_button:
        payload[form_data.search_button] = form_data.search_button_value or "Buscar"

    return payload


def fetch_search_form(session: requests.Session) -> str:
    logger.info("SIGAA sessão pública iniciada url=%s", SIGAA_PUBLIC_HOME_URL)
    home_response = session.get(
        SIGAA_PUBLIC_HOME_URL,
        headers={"User-Agent": USER_AGENT},
        timeout=TIMEOUT_SECONDS,
    )
    logger.info("SIGAA home status=%s final_url=%s", home_response.status_code, home_response.url)
    home_response.raise_for_status()

    logger.info("SIGAA GET iniciado url=%s", SIGAA_COMPONENTS_SEARCH_URL)
    response = session.get(
        SIGAA_COMPONENTS_SEARCH_URL,
        headers={"User-Agent": USER_AGENT},
        timeout=TIMEOUT_SECONDS,
    )
    logger.info("SIGAA GET status=%s", response.status_code)
    response.raise_for_status()
    return _response_text(response)


def submit_component_search(session: requests.Session, action_url: str, payload: dict[str, str]) -> str:
    action_url = _public_sigaa_url(action_url)
    logger.info("SIGAA POST iniciado action=%s", action_url)
    response = session.post(
        action_url,
        data=payload,
        headers={"User-Agent": USER_AGENT, "Referer": SIGAA_COMPONENTS_SEARCH_URL, "Origin": SIGAA_ORIGIN},
        timeout=TIMEOUT_SECONDS,
    )
    redirect_statuses = [item.status_code for item in response.history]
    logger.info(
        "SIGAA POST status=%s redirects=%s final_url=%s",
        response.status_code,
        redirect_statuses,
        response.url,
    )
    response.raise_for_status()
    _public_sigaa_url(response.url)
    if urlparse(response.url).path != urlparse(SIGAA_COMPONENTS_URL).path:
        raise SigaaSessionRedirectError("O SIGAA redirecionou a busca para fora da página de componentes.")
    return _response_text(response)


def fetch_component_details(session: requests.Session, detail_url: str, referer: str) -> str:
    url = _public_sigaa_url(detail_url)
    response = session.get(url, headers={"User-Agent": USER_AGENT, "Referer": referer}, timeout=TIMEOUT_SECONDS, allow_redirects=True)
    response.raise_for_status()
    _public_sigaa_url(response.url)
    return _response_text(response)


def _extract_viewstate_value(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    control = soup.find(attrs={"name": "javax.faces.ViewState"}) or soup.find(attrs={"id": "javax.faces.ViewState"})
    if isinstance(control, Tag):
        value = control.get("value", "")
        if value:
            return value
    raise ValueError("ViewState ausente no formulário do SIGAA.")


def _extract_turma_search_submit(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    candidates = soup.select(
        "form input[type='submit'], form button[type='submit'], form button:not([type])"
    )
    for control in candidates:
        name = control.get("name") or control.get("id")
        value = control.get("value") or _text(control)
        semantic = _normalize_text(
            " ".join(
                [
                    value,
                    control.get("title", ""),
                    control.get("aria-label", ""),
                ]
            )
        )
        if name and semantic in {"buscar", "pesquisar", "consultar"}:
            return name, value or "Buscar"
    raise ValueError("Botao de busca de turmas ausente no formulario publico do SIGAA.")


def build_turma_search_payload(
    view_state: str, search_control: tuple[str, str] | None = None
) -> dict[str, str]:
    payload = dict(SIGAA_TURMA_SEARCH_FIELDS)
    payload["javax.faces.ViewState"] = view_state
    if search_control:
        payload[search_control[0]] = search_control[1]
    return payload


def build_turma_detail_payload(search_payload: dict[str, str], view_state: str, turma_id: str) -> dict[str, str]:
    payload = {key: value for key, value in search_payload.items() if key in SIGAA_TURMA_SEARCH_FIELDS}
    payload.update(
        {
            "javax.faces.ViewState": view_state,
            "formTurma:aqui": "formTurma:aqui",
            "id": turma_id,
            "publico": "public",
        }
    )
    return payload


def fetch_turma_search_form(session: requests.Session) -> str:
    url = _public_sigaa_url(SIGAA_TURMAS_URL, SIGAA_TURMAS_URL)
    logger.info("SIGAA GET turmas iniciado url=%s", url)
    response = session.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_SECONDS)
    logger.info("SIGAA GET turmas status=%s", response.status_code)
    response.raise_for_status()
    return _response_text(response)


def submit_turma_search(session: requests.Session, payload: dict[str, str]) -> str:
    url = _public_sigaa_url(SIGAA_TURMAS_URL, SIGAA_TURMAS_URL)
    logger.info("SIGAA POST turmas busca iniciado action=%s", url)
    response = session.post(
        url,
        data=payload,
        headers={"User-Agent": USER_AGENT, "Referer": SIGAA_TURMAS_URL, "Origin": SIGAA_ORIGIN},
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    _public_sigaa_url(response.url, SIGAA_TURMAS_URL)
    return _response_text(response)


def submit_turma_detail(session: requests.Session, payload: dict[str, str]) -> str:
    url = _public_sigaa_url(SIGAA_TURMAS_URL, SIGAA_TURMAS_URL)
    logger.info("SIGAA POST turmas detalhe iniciado action=%s", url)
    response = session.post(
        url,
        data=payload,
        headers={"User-Agent": USER_AGENT, "Referer": SIGAA_TURMAS_URL, "Origin": SIGAA_ORIGIN},
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    _public_sigaa_url(response.url, SIGAA_TURMAS_URL)
    return _response_text(response)


def _extract_id_from_jsf_call(raw: str) -> str | None:
    patterns = [
        r"['\"]id['\"]\s*[:=]\s*['\"]?(\d+)",
        r"\bid=(\d+)\b",
        r"name=['\"]id['\"][^>]+value=['\"](\d+)",
        r"value=['\"](\d+)['\"][^>]+name=['\"]id['\"]",
    ]
    for pattern in patterns:
        match = re.search(pattern, raw)
        if match:
            return match.group(1)
    return None


def _candidate_detail_id(element: Tag) -> str | None:
    candidates: list[Tag] = [element]
    candidates.extend(element.find_all(["a", "button", "input"]))
    for candidate in candidates:
        raw = " ".join(str(value) for value in candidate.attrs.values())
        if "formTurma:aqui" not in raw and "publico" not in raw and "id" not in raw:
            continue
        found = _extract_id_from_jsf_call(raw)
        if found:
            return found
    return None


def extract_turma_detail_id(html: str, query: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    normalized_query = _normalize_text(query)
    rows = [row for row in soup.find_all("tr") if row.find_parent("thead") is None]
    matching_rows = [row for row in rows if not normalized_query or normalized_query in _normalize_text(_text(row))]
    for row in matching_rows + ([] if matching_rows else rows):
        found = _candidate_detail_id(row)
        if found:
            return found
    return None


def fetch_turma_component_details(session: requests.Session, query: str) -> tuple[str, str]:
    form_html = fetch_turma_search_form(session)
    initial_view_state = _extract_viewstate_value(form_html)
    search_control = _extract_turma_search_submit(form_html)
    search_payload = build_turma_search_payload(initial_view_state, search_control)
    result_html = submit_turma_search(session, search_payload)
    turma_id = extract_turma_detail_id(result_html, query)
    if not turma_id:
        raise ValueError("Não foi possível descobrir o identificador público da turma no SIGAA.")
    detail_view_state = _extract_viewstate_value(result_html)
    detail_payload = build_turma_detail_payload(search_payload, detail_view_state, turma_id)
    return submit_turma_detail(session, detail_payload), SIGAA_TURMAS_URL


def parse_sigaa_component_details(html: str, source_url: str) -> dict[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    return {
        "code": _find_labeled_value(soup, ["Código", "Codigo"]),
        "name": _find_labeled_value(soup, ["Nome", "Componente Curricular"]),
        "prerequisites": _find_labeled_value(soup, ["Pré-Requisitos", "Pre-Requisitos", "Pré Requisitos", "Pre Requisitos"]),
        "syllabus": _find_labeled_value(soup, ["Ementa/Descrição", "Ementa", "Descrição"]),
        "current_program": _find_labeled_value(soup, ["Programa atual", "Programa", "Conteúdo"]),
        "workload_hours": _find_labeled_value(soup, ["Carga Horária Total", "Carga horária total", "Carga horária", "Carga Horária"]),
        "theoretical_workload_hours": _find_labeled_value(soup, ["Carga Horária de Aula Teórica", "Carga horária teórica", "CH Teórica"]),
        "practical_workload_hours": _find_labeled_value(soup, ["Carga Horária de Aula Prática", "Carga horária prática", "CH Prática"]),
        "source_url": source_url,
    }


def _normalized_label(text: str) -> str:
    return _normalize_text(text).rstrip(":：-")


def _find_labeled_value(soup: BeautifulSoup, labels: list[str]) -> str:
    normalized_labels = [_normalized_label(label) for label in labels]
    for row in soup.find_all(["tr", "p", "li", "div"]):
        text = _text(row)
        text_normalized = _normalized_label(text)
        for label in normalized_labels:
            header = row.find(["th", "dt", "strong", "label"])
            value = row.find(["td", "dd"])
            if header is not None and value is not None and _normalized_label(_text(header)) == label:
                return _text(value)
            if text_normalized.startswith(label):
                return re.sub(r"^[^:：-]+[:：-]\s*", "", text, count=1).strip()
    return ""


def _parse_workload(value: str) -> int | None:
    match = re.search(r"\d+", value or "")
    return int(match.group(0)) if match else None


def _build_component_from_values(values: dict[str, str], source_url: str) -> SigaaComponent | None:
    code = values.get("code", "").strip()
    name = values.get("name", "").strip()
    if not code or not name:
        return None
    return SigaaComponent(
        code=code,
        name=name,
        type=values.get("type") or None,
        unit=values.get("unit") or None,
        workload_hours=_parse_workload(values.get("workload_hours", "")),
        syllabus=values.get("syllabus", ""),
        current_program=values.get("current_program", ""),
        prerequisites=values.get("prerequisites") or None,
        theoretical_workload_hours=_parse_workload(values.get("theoretical_workload_hours", "")),
        practical_workload_hours=_parse_workload(values.get("practical_workload_hours", "")),
        details_processed=values.get("details_processed") == "true",
        source_url=source_url,
    )


def _extract_component_values_from_row(row: Tag, query: str) -> tuple[dict[str, str], str]:
    source_url = SIGAA_COMPONENTS_URL
    values: dict[str, str] = {}

    attrs = getattr(row, "attrs", {})
    if attrs.get("data-component-code") or attrs.get("data-component-name"):
        values = {
            "code": attrs.get("data-component-code", ""),
            "name": attrs.get("data-component-name", ""),
            "type": attrs.get("data-component-type", ""),
            "unit": attrs.get("data-component-unit", ""),
            "workload_hours": attrs.get("data-component-workload", ""),
        }
    else:
        cells = [_text(cell) for cell in row.find_all(["td", "th"])]
        if len(cells) >= 2:
            row_text = _normalize_text(" ".join(cells))
            normalized_query = _normalize_text(query)
            if normalized_query not in row_text and not re.search(r"^[A-Z]{2,}\d", cells[0].strip().upper()):
                return values, source_url

            headers: list[str] = []
            table = row.find_parent("table")
            if isinstance(table, Tag):
                header_row = next((candidate for candidate in table.find_all("tr") if candidate.find("th")), None)
                if header_row is not None:
                    headers = [_normalize_text(_text(cell)) for cell in header_row.find_all(["th", "td"])]

            values = {"code": "", "name": "", "type": "", "unit": "", "workload_hours": ""}
            for index, cell in enumerate(cells):
                header = headers[index] if index < len(headers) else ""
                if header == "codigo":
                    values["code"] = cell
                elif header == "nome":
                    values["name"] = cell
                elif header == "tipo":
                    values["type"] = cell
                elif "unidade" in header:
                    values["unit"] = cell
                elif header in {"ch total", "carga horaria", "carga horaria total"}:
                    values["workload_hours"] = cell

            if not values["code"] or not values["name"]:
                values["code"] = cells[0]
                values["name"] = cells[1]
                values["type"] = cells[2] if len(cells) > 2 else ""
                values["workload_hours"] = cells[3] if len(cells) > 3 else ""

    link = None
    component_name = _normalize_text(values.get("name", ""))
    for candidate in row.find_all("a", href=lambda href: bool(href) and href != "#"):
        semantic = _normalize_text(" ".join([_text(candidate), candidate.get("title", ""), candidate.get("aria-label", "")]))
        if (component_name and component_name in semantic) or "detalh" in semantic or ("visualizar" in semantic and "componente" in semantic):
            link = candidate
            break
    if link is not None:
        source_url = urljoin(SIGAA_COMPONENTS_URL, link["href"])
    return values, source_url


def _extract_result_row(soup: BeautifulSoup, query: str) -> tuple[dict[str, str], str] | None:
    normalized_query = _normalize_text(query)
    candidate = soup.select_one("[data-component-code]")
    if candidate is not None:
        values, source_url = _extract_component_values_from_row(candidate, query)
        if values:
            return values, source_url

    for row in soup.find_all("tr"):
        if row.find_parent("thead") is not None:
            continue
        cells = [_text(cell) for cell in row.find_all(["td", "th"])]
        if len(cells) < 2:
            continue
        row_text = _normalize_text(" ".join(cells))
        if normalized_query and normalized_query not in row_text:
            continue
        values, source_url = _extract_component_values_from_row(row, query)
        if values:
            return values, source_url
    return None


def _extract_validation_message(soup: BeautifulSoup) -> str:
    selectors = [
        ".ui-message-error",
        ".error",
        ".erros",
        ".messages .error",
        ".alert-danger",
        "[data-validation-error]",
    ]
    for selector in selectors:
        for element in soup.select(selector):
            text = _text(element)
            if text:
                return text
    return ""


def _has_no_results_message(soup: BeautifulSoup) -> bool:
    if soup.select_one("[data-empty-results]") is not None:
        return True
    text = _normalize_text(soup.get_text(" ", strip=True))
    return any(
        phrase in text
        for phrase in [
            "nenhum componente curricular",
            "nenhum componente encontrado",
            "nenhum resultado",
            "nao foram encontrados",
            "não foram encontrados",
        ]
    )


def _has_search_form(soup: BeautifulSoup) -> bool:
    return soup.find("form") is not None


def parse_component_results(html: str, query: str, details_html: str | None = None, details_processed: bool = False) -> SigaaComponentSearchResponse:
    normalized_query = normalize_query(query)
    soup = BeautifulSoup(html, "html.parser")

    if _has_no_results_message(soup):
        logger.info("SIGAA resposta sem resultados para query=%s", normalized_query)
        return _empty_response(
            "not_found",
            normalized_query,
            "Não foi possível encontrar o componente na fonte pública consultada.",
        )

    validation_message = _extract_validation_message(soup)
    if validation_message:
        return _empty_response(
            "error",
            normalized_query,
            "O SIGAA retornou uma mensagem de validação: " + validation_message,
        )

    result_row = _extract_result_row(soup, normalized_query)
    if result_row is None:
        if _has_search_form(soup):
            return _empty_response(
                "error",
                normalized_query,
                "A resposta retornou apenas o formulário de busca. Verifique o fluxo JSF ou a estrutura HTML.",
            )
        return _empty_response(
            "error",
            normalized_query,
            "Não foi possível interpretar a resposta pública do SIGAA.",
        )

    values, source_url = result_row
    details = parse_sigaa_component_details(details_html or "", source_url)
    for key in ["code", "name"]:
        if details.get(key):
            values[key] = details[key]
    if not values.get("workload_hours"):
        values["workload_hours"] = details.get("workload_hours", "")
    values["syllabus"] = details.get("syllabus", "")
    values["current_program"] = details.get("current_program", "")
    values["prerequisites"] = details.get("prerequisites", "")
    values["theoretical_workload_hours"] = details.get("theoretical_workload_hours", "")
    values["practical_workload_hours"] = details.get("practical_workload_hours", "")
    if not values.get("workload_hours"):
        theoretical = _parse_workload(values.get("theoretical_workload_hours", ""))
        practical = _parse_workload(values.get("practical_workload_hours", ""))
        if theoretical is not None and practical is not None:
            values["workload_hours"] = str(theoretical + practical)
    has_detail_data = any(values.get(key) for key in ["syllabus", "current_program", "prerequisites", "theoretical_workload_hours", "practical_workload_hours"])
    values["details_processed"] = "true" if details_processed and has_detail_data else "false"
    component = _build_component_from_values(values, details.get("source_url") or source_url)
    if component is None:
        return _empty_response(
            "error",
            normalized_query,
            "Mudança inesperada na estrutura HTML do SIGAA.",
        )

    logger.info("SIGAA extraiu 1 resultado para query=%s", normalized_query)
    return SigaaComponentSearchResponse(
        status="found",
        source=SOURCE,
        query=normalized_query,
        component=component,
        cached=False,
        warnings=[],
    )


def parse_sigaa_search_results(html: str, query: str) -> SigaaComponentSearchResponse:
    return parse_component_results(html, query)


def _create_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    retry = Retry(total=1, connect=1, read=0, status=1, backoff_factor=0.25, status_forcelist=(429, 502, 503, 504), allowed_methods=frozenset({"GET", "POST"}))
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def _respect_public_rate_limit() -> None:
    global _last_public_request
    with _rate_lock:
        wait = MIN_REQUEST_INTERVAL_SECONDS - (time.monotonic() - _last_public_request)
        if wait > 0:
            time.sleep(wait)
        _last_public_request = time.monotonic()


def _search_once(session: requests.Session, normalized_query: str) -> SigaaComponentSearchResponse:
    html = fetch_search_form(session)
    form_data = extract_jsf_form(html, SIGAA_COMPONENTS_URL)
    search_type = "code" if _looks_like_component_code(normalized_query) else "name"
    payload = build_search_payload(form_data, search_type, normalized_query)
    response_html = submit_component_search(session, form_data.action_url, payload)
    basic = parse_component_results(response_html, normalized_query)
    if basic.status != "found" or basic.component is None:
        return basic
    try:
        details_html, detail_source_url = fetch_turma_component_details(session, normalized_query)
        enriched = parse_component_results(response_html, normalized_query, details_html, details_processed=True)
        if enriched.component is not None and enriched.component.details_processed:
            enriched.component.source_url = detail_source_url
            return enriched
        basic.warnings.append("Dados básicos encontrados; o detalhe público não trouxe ementa ou carga horária. Revise ou preencha manualmente.")
        return basic
    except (requests.RequestException, SigaaSessionRedirectError, SigaaResponseTooLargeError, ValueError) as exc:
        logger.warning(
            "SIGAA detalhe publico indisponivel query=%s category=%s",
            normalized_query,
            type(exc).__name__,
        )
        basic.warnings.append("Dados básicos encontrados; o detalhe público não pôde ser carregado. Revise ou preencha manualmente.")
        return basic


def search_sigaa_component(
    query: str,
    session: requests.Session | None = None,
    force_refresh: bool = False,
) -> SigaaComponentSearchResponse:
    normalized_query = normalize_query(query)
    if not normalized_query:
        return _empty_response("not_found", normalized_query, "Informe um código ou nome de componente.")

    cached = None if force_refresh else get_cached_component(normalized_query)
    if cached:
        return cached

    owns_session = session is None
    attempts = 2 if owns_session else 1

    for attempt in range(attempts):
        current_session = _create_session() if owns_session else session
        try:
            if owns_session:
                _respect_public_rate_limit()
            response = _search_once(current_session, normalized_query)
            break
        except SigaaSessionRedirectError:
            if attempt + 1 < attempts:
                logger.warning("SIGAA encerrou a sessão pública; repetindo query=%s", normalized_query)
                continue
            logger.warning("SIGAA encerrou repetidamente a sessão pública query=%s", normalized_query)
            return _empty_response(
                "error",
                normalized_query,
                "O SIGAA encerrou a sessão pública durante a busca. Tente novamente.",
            )
        except requests.Timeout:
            logger.warning("SIGAA timeout ao consultar query=%s", normalized_query)
            return _empty_response(
                "error",
                normalized_query,
                "A consulta ao SIGAA expirou. Você ainda pode manter os dados cadastrados manualmente.",
            )
        except requests.HTTPError:
            logger.warning("SIGAA retornou resposta HTTP inválida para query=%s", normalized_query)
            return _empty_response(
                "error",
                normalized_query,
                "O SIGAA retornou uma resposta HTTP inválida.",
            )
        except requests.RequestException:
            logger.warning("SIGAA indisponivel para query=%s", normalized_query)
            return _empty_response(
                "error",
                normalized_query,
                "A consulta ao SIGAA falhou. Você ainda pode manter os dados cadastrados manualmente.",
            )
        except ValueError as exc:
            logger.warning("SIGAA estrutura inesperada para query=%s motivo=%s", normalized_query, exc)
            return _empty_response("error", normalized_query, str(exc))
        except Exception:
            logger.exception("SIGAA falha inesperada para query=%s", normalized_query)
            return _empty_response(
                "error",
                normalized_query,
                "Não foi possível interpretar a resposta pública do SIGAA.",
            )
        finally:
            if owns_session:
                current_session.close()

    if response.status == "found":
        set_cached_component(normalized_query, response)
        if response.component is not None:
            from app import storage
            storage.upsert_catalog_component(response.component.model_dump())
    return response
