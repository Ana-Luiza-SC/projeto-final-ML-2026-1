from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import tempfile
import time
import unicodedata
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

from pydantic import ValidationError

from app import storage
from app.schemas import CoursePlanData, CoursePlanPreviewResponse
from app.services.study_recommendation_agent import generate_google_json

logger = logging.getLogger("estudaunb.course_plan")

MAX_BYTES = 10 * 1024 * 1024
CODE_RE = re.compile(r"\b[A-Z]{3}\d{4}\b")
DATE_RE = re.compile(r"(\d{2})/(\d{2})/(\d{4})")
DATE_RANGE_RE = re.compile(r"\b\d{2}/\d{2}\s*-\s*\d{2}/\d{2}\b")
PERCENT_RE = re.compile(r"(\d+(?:[,.]\d+)?)\s*%")
ARTIFACT_LINES = {"E", "T", "S", "I", "Í", "C", "O", "FI", "-T"}


class CoursePlanError(ValueError):
    pass


@dataclass(slots=True)
class ExtractedPdfText:
    text: str
    layout_text: str
    page_count: int


@dataclass(slots=True)
class LlmResult:
    data: CoursePlanData | None = None
    attempted: bool = False
    succeeded: bool = False
    elapsed_ms: float | None = None
    fallback_reason: str | None = None
    provider_exception_class: str | None = None


def _now_ms() -> float:
    return time.perf_counter() * 1000


def _duration_ms(start_ms: float) -> float:
    return round(_now_ms() - start_ms, 2)


def _plain(value: str) -> str:
    return unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().casefold()


def _squash(value: str) -> str:
    return " ".join(value.split())


def _clean_line(line: str) -> str:
    return _squash(line.strip(" \t\u00a0"))


def _is_artifact_line(line: str) -> bool:
    compact = _plain(line).upper().replace(" ", "")
    return compact in {_plain(item).upper().replace(" ", "") for item in ARTIFACT_LINES}


def _clean_lines(text: str) -> list[str]:
    lines = []
    for raw in text.replace("\r", "\n").splitlines():
        line = _clean_line(raw)
        if not line or _is_artifact_line(line):
            continue
        lines.append(line)
    return lines


def _normalized_text(text: str) -> str:
    return "\n".join(_clean_lines(text))


def _date(value: str | None) -> date | None:
    match = DATE_RE.search(value or "")
    return date(int(match.group(3)), int(match.group(2)), int(match.group(1))) if match else None


def _page_at(text: str, position: int) -> int | None:
    pages = list(re.finditer(r"\[PAGE (\d+)\]", text[:position]))
    return int(pages[-1].group(1)) if pages else None


def _percent(value: str | None) -> float | None:
    match = PERCENT_RE.search(value or "")
    return float(match.group(1).replace(",", ".")) if match else None


def _value(text: str, labels: str) -> str | None:
    match = re.search(rf"(?im)^\s*(?:{labels})\s*:\s*(.+)$", text)
    return _squash(match.group(1)) if match else None


def _line_value(lines: list[str], labels: list[str], stop_labels: list[str] | None = None) -> str | None:
    stop_labels = stop_labels or ["Turma", "Créditos", "Creditos", "Horário", "Horario", "Docente", "Modalidade"]
    for line in lines:
        plain_line = _plain(line)
        for label in labels:
            plain_label = _plain(label)
            if not plain_line.startswith(plain_label):
                continue
            value = line[len(label):].strip(" :\t")
            for stop in stop_labels:
                stop_match = re.search(rf"\s+{re.escape(stop)}\b", value, flags=re.IGNORECASE)
                if stop_match:
                    value = value[: stop_match.start()]
            return _squash(value) or None
    return None


def _metadata(text: str) -> dict[str, str | float | None]:
    lines = _clean_lines(text)
    code_match = CODE_RE.search(text.upper())
    name = _value(text, r"Disciplina|Componente curricular|Componente") or _line_value(lines, ["Componente curricular", "Componente"])
    semester = _value(text, r"Semestre|Período letivo|Periodo letivo|Período|Periodo")
    if semester:
        semester_match = re.search(r"\d{4}\.[12]", semester)
        semester = semester_match.group(0) if semester_match else semester
    else:
        semester_match = re.search(r"(?i)Per[ií]odo letivo\s+(\d{4}\.[12])", text)
        semester = semester_match.group(1) if semester_match else None
    workload_text = _value(text, r"Carga horária|Carga horaria") or _line_value(lines, ["Carga horária", "Carga horaria"])
    workload_match = re.search(r"\d+(?:[,.]\d+)?", workload_text or "")
    return {
        "code": code_match.group() if code_match else None,
        "name": name,
        "semester": semester,
        "workload_hours": float(workload_match.group().replace(",", ".")) if workload_match else None,
    }


def _heading_key(line: str) -> str | None:
    match = re.match(r"^(?:\[PAGE \d+\]\s*)?(?:\d+\.\s*)?(.+?)(?:\s*:)?$", line)
    if not match:
        return None
    value = _plain(match.group(1)).strip(" .:-")
    known = {
        "ementa": "ementa",
        "objetivos de aprendizagem": "objectives",
        "objetivos": "objectives",
        "conteudo programatico": "contents",
        "conteudos": "contents",
        "metodologia de ensino": "methodology",
        "avaliacao da aprendizagem": "assessments",
        "avaliacao": "assessments",
        "cronograma sintetico": "schedule",
        "cronograma": "schedule",
        "criterios de aprovacao e frequencia": "approval",
        "recursos didaticos": "resources",
        "referencias basicas e complementares": "bibliography",
        "bibliografia": "bibliography",
    }
    return known.get(value)


def _section_lines(text: str, start_key: str, end_keys: set[str] | None = None) -> list[str]:
    lines = _clean_lines(text)
    collecting = False
    result: list[str] = []
    for line in lines:
        key = _heading_key(line)
        if key == start_key:
            collecting = True
            continue
        if collecting and key and (end_keys is None or key in end_keys):
            break
        if collecting:
            result.append(line)
    return result


def _section(text: str, title: str) -> list[str]:
    match = re.search(rf"(?ims)^\s*(?:{title})\s*:\s*(.+?)(?=^\s*[A-ZÁÉÍÓÚÇ][^\n:]{{2,40}}\s*:|\Z)", text)
    return [item.strip(" -•\t") for item in match.group(1).splitlines() if item.strip(" -•\t")] if match else []


def _numbered_items(lines: list[str]) -> list[str]:
    items: list[str] = []
    current: list[str] = []
    for line in lines:
        if re.match(r"^\d+[.)]\s+", line):
            if current:
                items.append(_squash(" ".join(current)))
            current = [re.sub(r"^\d+[.)]\s+", "", line).strip()]
        elif current:
            current.append(line)
        elif line.startswith("-") or line.startswith("•"):
            items.append(line.strip(" -•\t"))
    if current:
        items.append(_squash(" ".join(current)))
    return [item for item in items if item]


def _objectives(text: str) -> list[str]:
    items = _numbered_items(_section_lines(text, "objectives", {"contents", "methodology", "assessments"}))
    return items or _section(text, r"Objetivos?")


def _contents(text: str) -> list[str]:
    lines = [line for line in _section_lines(text, "contents", {"methodology", "assessments"}) if _plain(line) not in {"unidade", "conteudos", "conteudo"}]
    units: list[str] = []
    current: list[str] = []
    for line in lines:
        if re.match(r"(?i)^Unidade\s+\d+\s*-", line):
            if current:
                units.append(_squash(" ".join(current)))
            current = [line]
        elif current:
            current.append(line)
    if current:
        units.append(_squash(" ".join(current)))
    return units or _section(text, r"Conteúdos?|Conteudos?|Unidades?")


def _schedule(text: str) -> list[str]:
    schedule = []
    for line in _section_lines(text, "schedule", {"approval", "resources", "bibliography"}):
        if DATE_RANGE_RE.search(line):
            schedule.append(_squash(line))
    legacy = _section(text, r"Cronograma")
    if legacy:
        schedule.extend(item for item in legacy if item not in schedule)
    if "aprender 3" in _plain(text) and not schedule:
        schedule = ["Cronograma de eventos disponível no Aprender 3; nenhuma data foi importada."]
    return schedule



def _clean_bibliography_entry(value: str) -> str:
    cleaned = _squash(value)
    cleaned = re.sub(r"\bSoftw\s+are\b", "Software", cleaned)
    cleaned = re.sub(r"(?<=[.!?])\s*[TESÍICIOF]$", "", cleaned)
    return cleaned.strip()

def _bibliography(text: str) -> list[str]:
    entries = []
    current: list[str] = []
    for line in _section_lines(text, "bibliography", None):
        if line.startswith("_") or "docente respons" in _plain(line) or "aviso:" in _plain(line) or "documento sintetico" in _plain(line):
            break
        if line.startswith("-") or line.startswith("•"):
            if current:
                entry = _clean_bibliography_entry(" ".join(current))
                if entry:
                    entries.append(entry)
            stripped = line.strip(" -•\t")
            current = [stripped] if stripped else []
        elif current:
            current.append(line)
    if current:
        entry = _clean_bibliography_entry(" ".join(current))
        if entry:
            entries.append(entry)
    return entries or _section(text, r"Bibliografia")


GROUP_SPECS = [
    ("AI", "Avaliação Individual", 40, [("mTAI", "Testes de Avaliação Individual", 60), ("TAF", "Teste de Avaliação Final", 40)]),
    ("AE", "Avaliação em Equipe", 45, [("AE1", "Entrega 1", 10), ("AE2", "Entrega 2", 30), ("AE3", "Entrega 3", 45), ("PC2", "Ponto de Controle 2", 5), ("PC3", "Ponto de Controle 3", 10)]),
    ("AC", "Avaliação Cruzada", 15, [("AC", "Avaliação Cruzada Individual", 100)]),
]


def _percent_near(text: str, label: str) -> tuple[float | None, int | None]:
    plain = _plain(text)
    position = plain.find(_plain(label))
    if position < 0:
        return None, None
    match = re.search(r"(\d+(?:[,.]\d+)?)\s*%", plain[position:position + 180])
    return (float(match.group(1).replace(",", ".")) if match else None, _page_at(text, position))


def _quality_evaluation_groups(text: str) -> list[dict]:
    plain = _plain(text)
    if "avaliacao individual" not in plain or "avaliacao em equipe" not in plain or "avaliacao cruzada" not in plain:
        return []
    groups = []
    for code, name, expected_final, items in GROUP_SPECS:
        found_final, page = _percent_near(text, name)
        final_weight = found_final if found_final in {expected_final, float(expected_final)} else expected_final
        parsed_items = []
        for item_code, item_name, expected_weight in items:
            found_weight, item_page = _percent_near(text, item_name)
            if _plain(item_name) not in plain and _plain(item_code) not in plain:
                continue
            parsed_items.append({"code": item_code, "name": item_name, "group_weight": found_weight or expected_weight, "date": None, "requires_date": True, "description": f"{expected_weight}% do grupo {code}", "topics": [], "source_page": item_page or page, "status": "recognized"})
        if parsed_items:
            groups.append({"code": code, "name": name, "final_weight": final_weight, "items": parsed_items})
    return groups


def _flatten_groups(groups: list[dict]) -> list[dict]:
    flattened = []
    for group in groups:
        for item in group.get("items", []):
            flattened.append({"name": item["name"], "code": item.get("code"), "date": item.get("date"), "weight": None, "group_code": group["code"], "group_name": group["name"], "group_final_weight": group["final_weight"], "group_weight": item.get("group_weight"), "requires_date": item.get("date") is None, "description": item.get("description"), "associated_content": None, "source_page": item.get("source_page"), "topics": item.get("topics", []), "status": item.get("status", "recognized")})
    return flattened


def _assessment_payload(name: str, modality: str | None, date_value: str | None, weight_value: str | None, associated: str | None, text: str) -> dict:
    assessment_date = _date(date_value)
    weight = _percent(weight_value)
    associated = _squash(associated or "") or None
    position = text.find(name)
    page = _page_at(text, position) if position >= 0 else None
    return {
        "name": _squash(name),
        "date": assessment_date,
        "weight": weight,
        "requires_date": assessment_date is None,
        "description": f"Modalidade: {modality}" if modality else None,
        "associated_content": associated,
        "topics": [associated] if associated else [],
        "source_page": page,
        "status": "recognized" if name else "requires_review",
    }


def _parse_assessment_line(line: str, text: str) -> dict | None:
    pattern = re.compile(r"^(?P<title>.+?)\s+(?P<modality>Individual|Grupo)\s+(?P<date>\d{2}/\d{2}/\d{4})?\s*(?P<weight>\d+(?:[,.]\d+)?\s*%)\s*(?P<content>.*)$", re.IGNORECASE)
    match = pattern.match(line)
    if not match:
        return None
    content = match.group("content").strip()
    return _assessment_payload(match.group("title"), match.group("modality"), match.group("date"), match.group("weight"), content, text)


def _parse_flat_assessments(text: str) -> list[dict]:
    lines = []
    for line in _section_lines(text, "assessments", {"schedule", "approval", "resources"}):
        plain = _plain(line)
        if plain in {"avaliacao", "modalidade", "data", "peso", "conteudo associado"}:
            continue
        if "calculo da nota final" in plain:
            break
        lines.append(line)

    assessments = [parsed for line in lines if (parsed := _parse_assessment_line(line, text))]
    if assessments:
        return assessments

    records: list[dict] = []
    index = 0
    while index < len(lines):
        title = lines[index]
        if _plain(title) in {"avaliacao", "modalidade", "data", "peso", "conteudo associado"}:
            index += 1
            continue
        if index + 2 >= len(lines) or _plain(lines[index + 1]) not in {"individual", "grupo"}:
            index += 1
            continue
        modality = lines[index + 1]
        cursor = index + 2
        date_value = None
        if cursor < len(lines) and DATE_RE.search(lines[cursor]):
            date_value = lines[cursor]
            cursor += 1
        if cursor >= len(lines) or not PERCENT_RE.search(lines[cursor]):
            index += 1
            continue
        weight_value = lines[cursor]
        cursor += 1
        associated = None
        if cursor < len(lines) and _plain(lines[cursor]) not in {"individual", "grupo"} and not DATE_RE.search(lines[cursor]) and not PERCENT_RE.search(lines[cursor]):
            associated = lines[cursor]
            cursor += 1
        records.append(_assessment_payload(title, modality, date_value, weight_value, associated, text))
        index = cursor
    return records


def _parse_legacy_assessment_lines(text: str) -> list[dict]:
    assessments = []
    for line in text.splitlines():
        if not re.match(r"(?i)^\s*(avaliação|avaliacao|prova|trabalho)\s*:", line):
            continue
        fields = [part.strip() for part in line.split("|")]
        name = fields[0].split(":", 1)[1].strip()
        date_value = next((part.split(":", 1)[1].strip() for part in fields[1:] if part.lower().startswith("data:")), None)
        weight_value = next((part.split(":", 1)[1].strip() for part in fields[1:] if part.lower().startswith("peso:")), None)
        topics_value = next((part.split(":", 1)[1].strip() for part in fields[1:] if part.lower().startswith(("conteúdos:", "conteudos:", "tópicos:", "topicos:"))), None)
        assessment = _assessment_payload(name, None, date_value, weight_value, topics_value, text)
        assessment["status"] = "recognized" if name else "requires_review"
        assessments.append(assessment)
    return assessments


def _detected_headings(text: str) -> list[str]:
    found = []
    for line in _clean_lines(text):
        key = _heading_key(line)
        if key and key not in found:
            found.append(key)
    return found


def _local_parser_matches(data: CoursePlanData) -> dict[str, int | bool]:
    return {
        "code": data.code is not None,
        "name": data.name is not None,
        "workload": data.workload_hours is not None,
        "objectives": len(data.objectives),
        "contents": len(data.contents),
        "schedule": len(data.schedule),
        "assessments": len(data.assessments),
        "bibliography": len(data.bibliography),
    }


def parse_course_plan_text(text: str) -> tuple[CoursePlanData, list[str]]:
    if not text.strip():
        raise CoursePlanError("PDF sem camada textual utilizável. OCR não está disponível; revise manualmente.")
    normalized = _normalized_text(text)
    metadata = _metadata(normalized)
    groups = _quality_evaluation_groups(normalized)
    assessments = _flatten_groups(groups)
    if not assessments:
        assessments = _parse_flat_assessments(normalized)
    if not assessments:
        assessments = _parse_legacy_assessment_lines(normalized)

    data = CoursePlanData.model_validate({
        "code": metadata["code"],
        "name": metadata["name"],
        "semester": metadata["semester"],
        "workload_hours": metadata["workload_hours"],
        "term_weeks": None,
        "objectives": _objectives(normalized),
        "contents": _contents(normalized),
        "schedule": _schedule(normalized),
        "evaluation_groups": groups,
        "assessments": assessments,
        "bibliography": _bibliography(normalized),
    })
    warnings = []
    if not assessments:
        warnings.append("Nenhuma avaliação foi identificada no plano de ensino.")
    elif any(item.date is None for item in data.assessments):
        warnings.append(f"{sum(item.date is None for item in data.assessments)} componente(s) identificado(s) sem data. Consulte o cronograma oficial e revise antes de registrar datas.")
    if any(item.status == "requires_review" for item in data.assessments):
        warnings.append("Algumas avaliações estão ambíguas e exigem revisão antes da confirmação.")
    return data, warnings


def _strip_json_fences(value: str) -> str:
    text = value.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        return fenced.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start:end + 1]
    return text


def _coerce_llm_payload(raw: object) -> dict:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            data = json.loads(_strip_json_fences(raw))
        except json.JSONDecodeError as exc:
            raise ValueError("invalid_json") from exc
        if isinstance(data, dict):
            return data
    raise ValueError("invalid_structured_response")


def _llm_timeout() -> float:
    try:
        return max(1.0, float(os.getenv("LLM_TIMEOUT_SECONDS", "8")))
    except ValueError:
        return 8.0


def _llm_prompt(text: str) -> str:
    schema = {
        "code": None,
        "name": None,
        "semester": None,
        "workload_hours": None,
        "term_weeks": None,
        "objectives": [],
        "contents": [],
        "schedule": [],
        "evaluation_groups": [],
        "assessments": [
            {"name": "", "date": None, "weight": None, "requires_date": False, "description": None, "associated_content": None, "topics": [], "status": "recognized"}
        ],
        "bibliography": [],
    }
    return (
        "Extraia um plano de ensino em JSON válido no schema abaixo. "
        "Use somente fatos explícitos do documento. Não invente nomes, datas, pesos, conteúdos, carga horária ou bibliografia. "
        "Aceite tabelas achatadas com registros avaliação/modalidade/data/peso/conteúdo. "
        "Datas devem ser YYYY-MM-DD ou null. Pesos são números percentuais. "
        "Retorne apenas o JSON do schema, sem comentários. Schema: "
        + json.dumps(schema, ensure_ascii=False)
        + "\nDocumento com marcadores de página:\n"
        + text
    )


def _classify_llm_failure(exc: BaseException) -> str:
    message = str(exc)
    if isinstance(exc, TimeoutError) or "timeout" in message:
        return "provider_timeout"
    if "missing_api_key" in message:
        return "missing_api_key"
    if "unsupported_model" in message:
        return "unsupported_model"
    if "invalid_json" in message or "llm_invalid_response" in message:
        return "invalid_json"
    if "invalid_structured_response" in message:
        return "invalid_structured_response"
    if isinstance(exc, ValidationError):
        return "schema_validation_error"
    if "schema" in message or "validation" in message:
        return "schema_validation_error"
    if "llm_failed" in message or "provider_error" in message:
        return "provider_error"
    return "internal_error"


def _gemini_extract(text: str, generator=None) -> CoursePlanData:
    provider = generator or generate_google_json
    raw = provider(_llm_prompt(text), _llm_timeout())
    payload = _coerce_llm_payload(raw)
    try:
        return CoursePlanData.model_validate(payload)
    except ValidationError as exc:
        raise ValueError("schema_validation_error") from exc


def _attempt_llm(text: str) -> LlmResult:
    result = LlmResult()
    provider = os.getenv("LLM_PROVIDER", "google").lower()
    if provider != "google":
        result.fallback_reason = "provider_error"
        return result
    if not os.getenv("GOOGLE_API_KEY"):
        result.fallback_reason = "missing_api_key"
        return result
    result.attempted = True
    start = _now_ms()
    try:
        result.data = _gemini_extract(text)
        result.succeeded = True
    except Exception as exc:
        result.fallback_reason = _classify_llm_failure(exc)
        result.provider_exception_class = type(exc).__name__
    finally:
        result.elapsed_ms = _duration_ms(start)
    return result


def _run_pdftotext(path: Path, layout: bool) -> ExtractedPdfText | None:
    args = ["pdftotext"]
    if layout:
        args.append("-layout")
    args.extend([str(path), "-"])
    try:
        completed = subprocess.run(args, check=True, capture_output=True, text=True, timeout=10)
    except (FileNotFoundError, subprocess.SubprocessError):
        return None
    text = completed.stdout
    page_count = max(1, text.count("\f") + (1 if text else 0))
    return ExtractedPdfText(text=text.replace("\f", "\n"), layout_text=text.replace("\f", "\n"), page_count=page_count)


def extract_pdf_text_details(path: Path) -> ExtractedPdfText:
    raw = path.read_bytes()
    if not raw.startswith(b"%PDF-") or len(raw) > MAX_BYTES:
        raise CoursePlanError("Envie um PDF válido de até 10 MiB.")
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            text_parts = []
            layout_parts = []
            for index, page in enumerate(pdf.pages, 1):
                text_parts.append(f"[PAGE {index}]\n{page.extract_text() or ''}")
                layout_parts.append(f"[PAGE {index}]\n{page.extract_text(layout=True) or ''}")
            return ExtractedPdfText(text="\n".join(text_parts), layout_text="\n".join(layout_parts), page_count=len(pdf.pages))
    except ImportError:
        fallback = _run_pdftotext(path, layout=True)
        if fallback is not None:
            return fallback
        raise CoursePlanError("Não foi possível extrair o texto do plano de ensino.")
    except Exception as exc:
        fallback = _run_pdftotext(path, layout=True)
        if fallback is not None:
            return fallback
        raise CoursePlanError("Não foi possível extrair o texto do plano de ensino.") from exc


def extract_text(path: Path) -> str:
    return extract_pdf_text_details(path).text


def _preview_warnings(data: CoursePlanData, warnings: list[str], llm: LlmResult, extracted_text_empty: bool) -> list[str]:
    result = list(warnings)
    if extracted_text_empty:
        result.append("O texto do PDF não pôde ser extraído; revise manualmente.")
    if llm.attempted and not llm.succeeded:
        result.append("A extração inteligente não ficou disponível; foi usado o parser local.")
    elif not llm.attempted and llm.fallback_reason in {"missing_api_key", "provider_error"}:
        result.append("A extração inteligente não está configurada; foi usado o parser local.")
    if data.assessments and (result or not llm.succeeded):
        result.append("Extração parcial disponível para revisão antes da confirmação.")
    return list(dict.fromkeys(result))


def _log_preview_event(**fields) -> None:
    logger.info(json.dumps({"event": "course_plan_preview", **fields}, ensure_ascii=False))


def build_preview(path: Path, discipline_id: str, filename: str | None = None) -> CoursePlanPreviewResponse:
    start = _now_ms()
    extracted = extract_pdf_text_details(path)
    text_for_parsing = extracted.layout_text or extracted.text
    extracted_text_empty = not (extracted.text or extracted.layout_text).strip()
    local_parser_attempted = False
    local_matches: dict[str, int | bool] = {}
    local_warnings: list[str] = []
    llm = LlmResult()
    data: CoursePlanData | None = None
    try:
        local_parser_attempted = True
        data, local_warnings = parse_course_plan_text(text_for_parsing)
        local_matches = _local_parser_matches(data)
        llm = _attempt_llm(text_for_parsing)
        if llm.succeeded and llm.data is not None:
            data = llm.data
        source = "gemini" if llm.succeeded else "local_parser"
        model = os.getenv("LLM_MODEL", "gemini-2.5-flash") if llm.succeeded else None
        warnings = _preview_warnings(data, local_warnings, llm, extracted_text_empty)
        preview_id = str(uuid4())
        expires_at = storage.utc_now() + timedelta(minutes=15)
        storage.COURSE_PLAN_PREVIEWS[preview_id] = {"discipline_id": discipline_id, "expires_at": expires_at, "data": data.model_dump(mode="json")}
        return CoursePlanPreviewResponse(
            preview_id=preview_id,
            expires_at=expires_at,
            data=data,
            warnings=warnings,
            source=source,
            model=model,
            fallback_reason=llm.fallback_reason if not llm.succeeded else None,
            evaluation_group_count=len(data.evaluation_groups),
            evaluation_component_count=len(data.assessments),
        )
    finally:
        safe_data = data or CoursePlanData()
        _log_preview_event(
            discipline_id=discipline_id,
            filename_extension=Path(filename or path.name).suffix.lower(),
            page_count=extracted.page_count,
            extracted_text_length=len(extracted.text),
            layout_text_length=len(extracted.layout_text),
            extracted_text_empty=extracted_text_empty,
            detected_headings=_detected_headings(text_for_parsing),
            llm_configured=bool(os.getenv("GOOGLE_API_KEY")) and os.getenv("LLM_PROVIDER", "google").lower() == "google",
            llm_provider=os.getenv("LLM_PROVIDER", "google"),
            llm_model=os.getenv("LLM_MODEL", "gemini-2.5-flash"),
            llm_attempted=llm.attempted,
            llm_succeeded=llm.succeeded,
            llm_elapsed_ms=llm.elapsed_ms,
            fallback_reason=llm.fallback_reason,
            provider_exception_class=llm.provider_exception_class,
            local_parser_attempted=local_parser_attempted,
            local_parser_matches=local_matches,
            result_name_detected=safe_data.name is not None,
            result_workload_detected=safe_data.workload_hours is not None,
            objective_count=len(safe_data.objectives),
            content_count=len(safe_data.contents),
            schedule_count=len(safe_data.schedule),
            evaluation_group_count=len(safe_data.evaluation_groups),
            evaluation_component_count=len(safe_data.assessments),
            bibliography_count=len(safe_data.bibliography),
            elapsed_ms=_duration_ms(start),
        )
