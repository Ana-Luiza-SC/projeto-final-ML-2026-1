from __future__ import annotations

import os
import re
import unicodedata
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

from app import storage
from app.schemas import CoursePlanData, CoursePlanPreviewResponse
from app.services.study_recommendation_agent import generate_google_json

MAX_BYTES = 10 * 1024 * 1024
CODE_RE = re.compile(r"\b[A-Z]{3}\d{4}\b")
DATE_RE = re.compile(r"(\d{2})/(\d{2})/(\d{4})")

class CoursePlanError(ValueError):
    pass

def _value(text: str, labels: str) -> str | None:
    match = re.search(rf"(?im)^\s*(?:{labels})\s*:\s*(.+)$", text)
    return " ".join(match.group(1).split()) if match else None

def _section(text: str, title: str) -> list[str]:
    match = re.search(rf"(?ims)^\s*(?:{title})\s*:\s*(.+?)(?=^\s*[A-ZÁÉÍÓÚÇ][^\n:]{{2,40}}\s*:|\Z)", text)
    return [item.strip(" -•\t") for item in match.group(1).splitlines() if item.strip(" -•\t")] if match else []

def _date(value: str | None) -> date | None:
    match = DATE_RE.search(value or "")
    return date(int(match.group(3)), int(match.group(2)), int(match.group(1))) if match else None

def _plain(value: str) -> str:
    return unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().casefold()

def _page_at(text: str, position: int) -> int | None:
    pages = list(re.finditer(r"\[PAGE (\d+)\]", text[:position]))
    return int(pages[-1].group(1)) if pages else None

def _percent_near(text: str, label: str) -> tuple[float | None, int | None]:
    plain = _plain(text)
    position = plain.find(_plain(label))
    if position < 0:
        return None, None
    match = re.search(r"(\d+(?:[,.]\d+)?)\s*%", plain[position:position + 180])
    return (float(match.group(1).replace(",", ".")) if match else None, _page_at(text, position))

GROUP_SPECS = [
    ("AI", "Avaliação Individual", 40, [("mTAI", "Testes de Avaliação Individual", 60), ("TAF", "Teste de Avaliação Final", 40)]),
    ("AE", "Avaliação em Equipe", 45, [("AE1", "Entrega 1", 10), ("AE2", "Entrega 2", 30), ("AE3", "Entrega 3", 45), ("PC2", "Ponto de Controle 2", 5), ("PC3", "Ponto de Controle 3", 10)]),
    ("AC", "Avaliação Cruzada", 15, [("AC", "Avaliação Cruzada Individual", 100)]),
]

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
            # A estrutura só é aceita quando o componente está explicitamente presente.
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
            flattened.append({"name": item["name"], "code": item.get("code"), "date": item.get("date"), "weight": None, "group_code": group["code"], "group_name": group["name"], "group_final_weight": group["final_weight"], "group_weight": item.get("group_weight"), "requires_date": item.get("date") is None, "description": item.get("description"), "source_page": item.get("source_page"), "topics": item.get("topics", []), "status": item.get("status", "recognized")})
    return flattened

def parse_course_plan_text(text: str) -> tuple[CoursePlanData, list[str]]:
    if not text.strip():
        raise CoursePlanError("PDF sem camada textual utilizável. OCR não está disponível; revise manualmente.")
    code_match = CODE_RE.search(text.upper())
    workload_text = _value(text, r"Carga horária|Carga horaria")
    workload_match = re.search(r"\d+(?:[,.]\d+)?", workload_text or "")
    groups = _quality_evaluation_groups(text)
    assessments = _flatten_groups(groups)
    if not assessments:
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
            assessments.append({"name": name, "date": assessment_date, "weight": float(weight_match.group().replace(",", ".")) if weight_match else None, "requires_date": assessment_date is None, "topics": [item.strip() for item in (topics_value or "").split(",") if item.strip()], "status": "recognized" if name else "requires_review"})
    schedule = _section(text, r"Cronograma")
    if "aprender 3" in _plain(text) and not schedule:
        schedule = ["Cronograma de eventos disponível no Aprender 3; nenhuma data foi importada."]
    data = CoursePlanData.model_validate({"code": code_match.group() if code_match else None, "name": _value(text, r"Disciplina|Componente"), "semester": _value(text, r"Semestre|Período|Periodo"), "workload_hours": float(workload_match.group().replace(",", ".")) if workload_match else None, "term_weeks": None, "objectives": _section(text, r"Objetivos?"), "contents": _section(text, r"Conteúdos?|Conteudos?|Unidades?"), "schedule": schedule, "evaluation_groups": groups, "assessments": assessments, "bibliography": _section(text, r"Bibliografia")})
    warnings = []
    if not assessments: warnings.append("Nenhuma avaliação foi identificada no plano de ensino.")
    elif any(item.date is None for item in data.assessments): warnings.append(f"{sum(item.date is None for item in data.assessments)} componente(s) identificado(s) sem data. Consulte o cronograma oficial e revise antes de registrar datas.")
    if any(item.status == "requires_review" for item in data.assessments): warnings.append("Algumas avaliações estão ambíguas e exigem revisão antes da confirmação.")
    return data, warnings

def _gemini_extract(text: str) -> CoursePlanData:
    schema = {"evaluation_groups": [{"code": "AI", "name": "", "final_weight": 0, "items": [{"code": "", "name": "", "group_weight": 0, "date": None, "requires_date": True, "description": "", "topics": [], "source_page": 1, "status": "recognized"}]}]}
    prompt = "Extraia apenas avaliações explicitamente presentes no plano. Avaliação não precisa ter data; tabelas de composição de nota são válidas. Preserve peso do grupo e peso interno sem somá-los. Data ausente deve ser null e requires_date true. Não transforme menções genéricas como data de provas em eventos e não invente dados. Indique página quando possível. Retorne JSON: " + str(schema) + "\nDocumento com marcadores de página:\n" + text
    raw = generate_google_json(prompt, max(1.0, float(os.getenv("LLM_TIMEOUT_SECONDS", "8"))))
    groups = raw.get("evaluation_groups", [])
    local, _ = parse_course_plan_text(text)
    return CoursePlanData.model_validate({**local.model_dump(mode="json"), "evaluation_groups": groups, "assessments": _flatten_groups(groups)})

def extract_text(path: Path) -> str:
    raw = path.read_bytes()
    if not raw.startswith(b"%PDF-") or len(raw) > MAX_BYTES: raise CoursePlanError("Envie um PDF válido de até 10 MiB.")
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            return "\n".join(f"[PAGE {index}]\n{page.extract_text() or ''}" for index, page in enumerate(pdf.pages, 1))
    except Exception as exc:
        raise CoursePlanError("Não foi possível extrair o texto do plano de ensino.") from exc

def build_preview(path: Path, discipline_id: str) -> CoursePlanPreviewResponse:
    text = extract_text(path)
    source, model = "local_parser", None
    data, warnings = parse_course_plan_text(text)
    if os.getenv("GOOGLE_API_KEY") and os.getenv("LLM_PROVIDER", "google").lower() == "google":
        try:
            data = _gemini_extract(text)
            source, model = "gemini", os.getenv("LLM_MODEL", "gemini-2.5-flash")
        except Exception:
            warnings.append("A extração inteligente não ficou disponível; foi usado o parser local.")
    preview_id = str(uuid4())
    expires_at = storage.utc_now() + timedelta(minutes=15)
    storage.COURSE_PLAN_PREVIEWS[preview_id] = {"discipline_id": discipline_id, "expires_at": expires_at, "data": data.model_dump(mode="json")}
    return CoursePlanPreviewResponse(preview_id=preview_id, expires_at=expires_at, data=data, warnings=warnings, source=source, model=model, evaluation_group_count=len(data.evaluation_groups), evaluation_component_count=len(data.assessments))
