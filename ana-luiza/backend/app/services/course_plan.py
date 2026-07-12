from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from app import storage
from app.schemas import CoursePlanData, CoursePlanPreviewResponse

MAX_BYTES = 10 * 1024 * 1024
CODE_RE = re.compile(r"\b[A-Z]{3}\d{4}\b")
DATE_RE = re.compile(r"(\d{2})/(\d{2})/(\d{4})")


class CoursePlanError(ValueError):
    pass


def _value(text: str, labels: str) -> str | None:
    match = re.search(rf"(?im)^\s*(?:{labels})\s*:\s*(.+)$", text)
    return " ".join(match.group(1).split()) if match else None


def _section(text: str, title: str) -> list[str]:
    match = re.search(rf"(?ims)^\s*{title}\s*:\s*(.+?)(?=^\s*[A-ZÁÉÍÓÚÇ][^\n:]{{2,40}}\s*:|\Z)", text)
    if not match:
        return []
    return [item.strip(" -•\t") for item in match.group(1).splitlines() if item.strip(" -•\t")]


def _date(value: str | None) -> date | None:
    if not value:
        return None
    match = DATE_RE.search(value)
    return date(int(match.group(3)), int(match.group(2)), int(match.group(1))) if match else None


def parse_course_plan_text(text: str) -> tuple[CoursePlanData, list[str]]:
    if not text.strip():
        raise CoursePlanError("PDF sem camada textual utilizável. OCR não está disponível; revise manualmente.")
    code_match = CODE_RE.search(text.upper())
    workload_text = _value(text, r"Carga horária|Carga horaria")
    workload_match = re.search(r"\d+(?:[,.]\d+)?", workload_text or "")
    assessments = []
    for line in text.splitlines():
        if not re.match(r"(?i)^\s*(avaliação|avaliacao|prova|trabalho)\s*:", line):
            continue
        fields = [part.strip() for part in line.split("|")]
        name = fields[0].split(":", 1)[1].strip()
        date_value = next((part.split(":", 1)[1].strip() for part in fields[1:] if part.lower().startswith("data:")), None)
        weight_value = next((part.split(":", 1)[1].strip() for part in fields[1:] if part.lower().startswith("peso:")), None)
        topics_value = next((part.split(":", 1)[1].strip() for part in fields[1:] if part.lower().startswith(("conteúdos:", "conteudos:", "tópicos:", "topicos:"))), None)
        weight_match = re.search(r"\d+(?:[,.]\d+)?", weight_value or "")
        assessment_date = _date(date_value)
        weight = float(weight_match.group().replace(",", ".")) if weight_match else None
        assessments.append({
            "name": name, "date": assessment_date, "weight": weight,
            "topics": [item.strip() for item in (topics_value or "").split(",") if item.strip()],
            "status": "recognized" if assessment_date and weight is not None else "requires_review",
        })
    data = CoursePlanData.model_validate({
        "code": code_match.group() if code_match else None,
        "name": _value(text, r"Disciplina|Componente"),
        "semester": _value(text, r"Semestre|Período|Periodo"),
        "workload_hours": float(workload_match.group().replace(",", ".")) if workload_match else None,
        "term_weeks": None,
        "objectives": _section(text, r"Objetivos?"),
        "contents": _section(text, r"Conteúdos?|Conteudos?|Unidades?"),
        "schedule": _section(text, r"Cronograma"),
        "assessments": assessments,
        "bibliography": _section(text, r"Bibliografia"),
    })
    warnings = []
    if not assessments:
        warnings.append("Não foi encontrada uma avaliação com data confirmada no plano de ensino.")
    if any(item.status == "requires_review" for item in data.assessments):
        warnings.append("Algumas avaliações requerem revisão de data ou peso.")
    return data, warnings


def extract_text(path: Path) -> str:
    raw = path.read_bytes()
    if not raw.startswith(b"%PDF-") or len(raw) > MAX_BYTES:
        raise CoursePlanError("Envie um PDF válido de até 10 MiB.")
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception as exc:
        raise CoursePlanError("Não foi possível extrair o texto do plano de ensino.") from exc


def build_preview(path: Path, discipline_id: str) -> CoursePlanPreviewResponse:
    data, warnings = parse_course_plan_text(extract_text(path))
    preview_id = str(uuid4())
    expires_at = storage.utc_now() + timedelta(minutes=15)
    storage.COURSE_PLAN_PREVIEWS[preview_id] = {
        "discipline_id": discipline_id, "expires_at": expires_at, "data": data.model_dump(mode="json")
    }
    return CoursePlanPreviewResponse(preview_id=preview_id, expires_at=expires_at, data=data, warnings=warnings)
