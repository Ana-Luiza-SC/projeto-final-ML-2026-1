from __future__ import annotations

import json
import logging
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag

from app.schemas import SigaaComponent, SigaaComponentSearchResponse

logger = logging.getLogger(__name__)

SIGAA_COMPONENTS_URL = "https://sigaa.unb.br/sigaa/public/componentes/busca_componentes.jsf"
SIGAA_COMPONENTS_SEARCH_URL = SIGAA_COMPONENTS_URL + "?nivel=G&aba=p-graduacao"
SIGAA_PUBLIC_HOME_URL = "https://sigaa.unb.br/sigaa/public/home.jsf"
SIGAA_ORIGIN = "https://sigaa.unb.br"
SOURCE = "sigaa_public_components"
USER_AGENT = "EstudaUnB/0.1 public-components-lookup"
TIMEOUT_SECONDS = 6
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


def normalize_query(query: str) -> str:
    return " ".join(query.strip().upper().split())


def _strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _normalize_text(text: str) -> str:
    return " ".join(_strip_accents(text).casefold().split())


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


def get_cached_component(query: str) -> SigaaComponentSearchResponse | None:
    cache_key = normalize_query(query)
    cached = _read_cache().get(cache_key)
    if not cached:
        return None
    response = SigaaComponentSearchResponse.model_validate(cached)
    response.cached = True
    return response


def set_cached_component(query: str, response: SigaaComponentSearchResponse) -> None:
    cache_key = normalize_query(query)
    cache = _read_cache()
    payload = response.model_dump(mode="json")
    payload["cached"] = False
    cache[cache_key] = payload
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
    return response.text


def submit_component_search(session: requests.Session, action_url: str, payload: dict[str, str]) -> str:
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
    if urlparse(response.url).path != urlparse(SIGAA_COMPONENTS_URL).path:
        raise SigaaSessionRedirectError("O SIGAA redirecionou a busca para fora da página de componentes.")
    return response.text


def parse_sigaa_component_details(html: str, source_url: str) -> dict[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    return {
        "syllabus": _find_labeled_value(soup, ["Ementa", "Ementa:", "Descrição"]),
        "current_program": _find_labeled_value(soup, ["Programa atual", "Programa", "Conteúdo"]),
        "workload_hours": _find_labeled_value(soup, ["Carga horária", "Carga Horária"]),
        "source_url": source_url,
    }


def _find_labeled_value(soup: BeautifulSoup, labels: list[str]) -> str:
    normalized_labels = [_normalize_text(label) for label in labels]
    for row in soup.find_all(["tr", "p", "li", "div"]):
        text = _text(row)
        text_normalized = _normalize_text(text)
        for label in normalized_labels:
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

    link = row.find("a", href=lambda href: bool(href) and href != "#")
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


def parse_component_results(html: str, query: str) -> SigaaComponentSearchResponse:
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
    details = parse_sigaa_component_details(html, source_url)
    if not values.get("workload_hours"):
        values["workload_hours"] = details.get("workload_hours", "")
    values["syllabus"] = details.get("syllabus", "")
    values["current_program"] = details.get("current_program", "")
    component = _build_component_from_values(values, source_url)
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
    return session


def _search_once(session: requests.Session, normalized_query: str) -> SigaaComponentSearchResponse:
    html = fetch_search_form(session)
    form_data = extract_jsf_form(html, SIGAA_COMPONENTS_URL)
    search_type = "code" if _looks_like_component_code(normalized_query) else "name"
    payload = build_search_payload(form_data, search_type, normalized_query)
    response_html = submit_component_search(session, form_data.action_url, payload)
    return parse_component_results(response_html, normalized_query)


def search_sigaa_component(
    query: str,
    session: requests.Session | None = None,
) -> SigaaComponentSearchResponse:
    normalized_query = normalize_query(query)
    if not normalized_query:
        return _empty_response("not_found", normalized_query, "Informe um código ou nome de componente.")

    cached = get_cached_component(normalized_query)
    if cached:
        return cached

    owns_session = session is None
    attempts = 2 if owns_session else 1

    for attempt in range(attempts):
        current_session = _create_session() if owns_session else session
        try:
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
    return response
