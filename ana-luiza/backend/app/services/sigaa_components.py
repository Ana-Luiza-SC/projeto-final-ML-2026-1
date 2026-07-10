from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from app.schemas import SigaaComponent, SigaaComponentSearchResponse

SIGAA_COMPONENTS_URL = "https://sigaa.unb.br/sigaa/public/componentes/busca_componentes.jsf"
SOURCE = "sigaa_public_components"
USER_AGENT = "EstudaUnB/0.1 public-components-lookup"
TIMEOUT_SECONDS = 6
CACHE_FILE = Path(__file__).resolve().parents[1] / "cache" / "sigaa_components_cache.json"


def normalize_query(query: str) -> str:
    return " ".join(query.strip().upper().split())


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


def _parse_workload(value: str) -> int | None:
    match = re.search(r"\d+", value or "")
    return int(match.group(0)) if match else None


def _find_labeled_value(soup: BeautifulSoup, labels: list[str]) -> str:
    normalized_labels = [label.lower() for label in labels]
    for row in soup.find_all(["tr", "p", "li", "div"]):
        text = _text(row)
        text_lower = text.lower()
        for label in normalized_labels:
            if text_lower.startswith(label):
                return re.sub(r"^[^:：-]+[:：-]\s*", "", text, count=1).strip()
    return ""


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


def parse_sigaa_component_details(html: str, source_url: str) -> dict[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    return {
        "syllabus": _find_labeled_value(soup, ["Ementa", "Ementa:", "Descrição"]),
        "current_program": _find_labeled_value(soup, ["Programa atual", "Programa", "Conteúdo"]),
        "workload_hours": _find_labeled_value(soup, ["Carga horária", "Carga Horária"]),
        "source_url": source_url,
    }


def parse_sigaa_search_results(html: str, query: str) -> SigaaComponentSearchResponse:
    normalized_query = normalize_query(query)
    soup = BeautifulSoup(html, "html.parser")
    if soup.select_one("[data-empty-results]") or "nenhum componente" in soup.get_text(" ", strip=True).lower():
        return _empty_response(
            "not_found",
            normalized_query,
            "Não foi possível encontrar o componente na fonte pública consultada.",
        )

    source_url = SIGAA_COMPONENTS_URL
    result = soup.select_one("[data-component-code]")
    values: dict[str, str] = {}
    if result:
        values = {
            "code": result.get("data-component-code", ""),
            "name": result.get("data-component-name", ""),
            "type": result.get("data-component-type", ""),
            "unit": result.get("data-component-unit", ""),
            "workload_hours": result.get("data-component-workload", ""),
        }
        link = result.find("a", href=True)
        if link:
            source_url = urljoin(SIGAA_COMPONENTS_URL, link["href"])
    else:
        for row in soup.find_all("tr"):
            cells = [_text(cell) for cell in row.find_all(["td", "th"])]
            row_text = " ".join(cells).upper()
            if len(cells) >= 2 and normalized_query in row_text:
                values = {
                    "code": cells[0],
                    "name": cells[1],
                    "type": cells[2] if len(cells) > 2 else "",
                    "unit": cells[3] if len(cells) > 3 else "",
                    "workload_hours": cells[4] if len(cells) > 4 else "",
                }
                link = row.find("a", href=True)
                if link:
                    source_url = urljoin(SIGAA_COMPONENTS_URL, link["href"])
                break

    if not values:
        return _empty_response(
            "not_found",
            normalized_query,
            "Não foi possível encontrar o componente na fonte pública consultada.",
        )

    details = parse_sigaa_component_details(html, source_url)
    for key in ("syllabus", "current_program"):
        values[key] = details.get(key, "")
    if not values.get("workload_hours"):
        values["workload_hours"] = details.get("workload_hours", "")
    component = _build_component_from_values(values, source_url)
    if component is None:
        return _empty_response(
            "not_found",
            normalized_query,
            "Não foi possível encontrar o componente na fonte pública consultada.",
        )

    return SigaaComponentSearchResponse(
        status="found",
        source=SOURCE,
        query=normalized_query,
        component=component,
        cached=False,
        warnings=[],
    )


def _fetch_public_search_html(query: str) -> str:
    response = requests.get(
        SIGAA_COMPONENTS_URL,
        params={"query": query},
        headers={"User-Agent": USER_AGENT},
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.text


def search_sigaa_component(query: str) -> SigaaComponentSearchResponse:
    normalized_query = normalize_query(query)
    if not normalized_query:
        return _empty_response("not_found", normalized_query, "Informe um código ou nome de componente.")

    cached = get_cached_component(normalized_query)
    if cached:
        return cached

    try:
        html = _fetch_public_search_html(normalized_query)
        response = parse_sigaa_search_results(html, normalized_query)
    except requests.RequestException:
        return _empty_response(
            "error",
            normalized_query,
            "A consulta ao SIGAA falhou. Você ainda pode manter os dados cadastrados manualmente.",
        )
    except Exception:
        return _empty_response(
            "error",
            normalized_query,
            "Não foi possível interpretar a resposta pública do SIGAA.",
        )

    if response.status == "found":
        set_cached_component(normalized_query, response)
    return response
