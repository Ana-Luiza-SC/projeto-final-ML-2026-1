from __future__ import annotations

import json
import logging
import os
import re
import time
import unicodedata
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from app import storage
from app.schemas import (
    ImportConfirmationItem,
    ImportPreviewItem,
    ImportPreviewSummary,
    MatriculaImportConfirmRequest,
    MatriculaImportConfirmResponse,
    MatriculaPdfPreviewResponse,
)

logger = logging.getLogger("estudaunb.matricula_import")

MAX_PDF_BYTES = int(os.getenv("MATRICULA_IMPORT_MAX_BYTES", str(10 * 1024 * 1024)))
MAX_PAGES = int(os.getenv("MATRICULA_IMPORT_MAX_PAGES", "30"))
PREVIEW_TTL_MINUTES = int(os.getenv("MATRICULA_IMPORT_TTL_MINUTES", "15"))
MAX_ITEMS = 50

# Padrão de código curricular da UnB: 2-5 letras + 4 dígitos
CODE_RE = re.compile(r"\b([A-Z]{2,5}\d{4})\b")
# Padrão de código de horário do SIGAA: dígitos de dias + M/T/N + dígitos de slots
SCHEDULE_RE = re.compile(r"\b([2-7]{1,6}[MTN]\d{1,6})\b", re.IGNORECASE)

# Marcadores que indicam que o item é uma atividade acadêmica, não uma disciplina
_ACTIVITY_MARKERS = (
    "ATIVIDADE DE ORIENTAÇÃO",
    "ORIENTAÇÃO INDIVIDUAL",
    "MONITORIA",
    "ORIENTACAO",
    "ESTAGIO",
    "ESTÁGIO",
    "EXTENSAO",
    "EXTENSÃO",
)

# Linhas de texto plano que são ruído (cabeçalho/rodapé)
_NOISE_PATTERNS = (
    r"^\s*Portal Discente\s*$",
    r"^\s*SIGAA\s*\|",
    r"sistema integrado de gest",
    r"para verificar a autenticidade",
    r"^\s*\d+\s+of\s+\d+",
    r"^\s*Horários\s+Dom\s+Seg",
    r"^\s*\d{2}:\d{2}\s*-\s*\d{2}:\d{2}",
    r"sigaa\.unb\.br",
    r"^\s*Copyright",
    r"atencao\b|atenção\b",
    r"código de verific",
)
_NOISE_RE = re.compile("|".join(_NOISE_PATTERNS), re.IGNORECASE)

# Palavras de status para ignorar no nome
_STATUS_WORDS = {"MATRICULADO", "DEFERIDO", "INDEFERIDO", "TRANCADO", "CANCELADO", "MATRICULADO(A)"}


SigaaLookup = Callable[[str], Any]


class ImportValidationError(ValueError):
    def __init__(self, message: str, category: str = "validation_error") -> None:
        super().__init__(message)
        self.category = category


class ImportPreviewNotFoundError(ValueError):
    pass


@dataclass(frozen=True)
class ExtractedCandidate:
    item_type: str
    code: str | None
    name: str | None
    class_code: str | None
    schedule_code: str | None
    local: str | None
    confidence: str
    warnings: tuple[str, ...]


def _now_ms() -> float:
    return time.perf_counter() * 1000


def _duration_ms(start: float) -> float:
    return round(_now_ms() - start, 2)


def _log_event(event: str, **fields: Any) -> None:
    safe = {key: value for key, value in fields.items() if key not in {"pdf_text", "file_name", "student_name", "matricula"}}
    logger.info(json.dumps({"event": event, **safe}, ensure_ascii=False))


def normalize_code(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = "".join(char for char in value.upper().strip() if char.isalnum())
    return normalized or None


def normalize_display_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.strip().split())
    return cleaned or None


def normalize_name_for_compare(value: str | None) -> str | None:
    cleaned = normalize_display_text(value)
    if not cleaned:
        return None
    decomposed = unicodedata.normalize("NFKD", cleaned)
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
    return without_accents.casefold()


def _remove_replacement_chars(value: str) -> str:
    """Remove caracteres de substituição Unicode (\ufffd) que surgem de fontes mapeadas do PDF.
    Não faz outras conversões arbitrárias de encode/decode."""
    return value.replace("\ufffd", "")


def _extract_schedule_code(cell: str | None) -> str | None:
    """Extrai o código de horário (ex: '24T45') da célula de horário, descartando datas."""
    if not cell:
        return None
    cell_clean = _remove_replacement_chars(cell)
    match = SCHEDULE_RE.search(cell_clean)
    return match.group(1).upper() if match else None


def _extract_discipline_name(component_cell: str) -> tuple[str | None, str | None]:
    """Extrai o nome da disciplina e o local da célula 'Componentes Curriculares/Docentes'.

    A célula tem formato multilinhas:
        NOME DA DISCIPLINA [pode continuar na linha seguinte se quebrado]
        NOME DO DOCENTE [ou DOCENTE A (linha) + e DOCENTE B (próxima linha)]
        Tipo: DISCIPLINA Local: FCTE - X9

    Estratégia de duas passadas:
    1. Localiza a linha 'Tipo:' ou 'ORIENTADOR' para determinar o tamanho do bloco.
    2. As linhas antes de 'Tipo:' formam [nome da disciplina...] + [docente(s)].
    3. A ÚLTIMA linha antes de 'Tipo:' é sempre o docente (ou continuação de docente conjunto).
    4. Se a última linha começa com 'e ' (ex: 'e ISAQUE ALVES'), as 2 últimas são o docente.
    5. 'Tipo:' carrega o local.

    Retorna (nome, local).
    """
    lines = [ln.strip() for ln in component_cell.splitlines() if ln.strip()]
    if not lines:
        return None, None

    # Passada 1: localiza 'Tipo:' ou 'ORIENTADOR'
    tipo_idx: int | None = None
    orientador_idx: int | None = None
    for idx, line in enumerate(lines):
        upper = line.upper()
        if upper.startswith("TIPO:"):
            tipo_idx = idx
            break
        if upper.startswith("ORIENTADOR") or upper.startswith("FORMA DE PARTICIP"):
            orientador_idx = idx
            break

    local: str | None = None

    if tipo_idx is not None:
        # Extrai local da linha 'Tipo:'
        tipo_line = lines[tipo_idx]
        local_match = re.search(r"Local:\s*(.+)", tipo_line, re.IGNORECASE)
        if local_match:
            local = local_match.group(1).strip()
        # Linhas antes de 'Tipo:' = [nome da disciplina...] + [docente(s)]
        before_tipo = lines[:tipo_idx]
    elif orientador_idx is not None:
        before_tipo = lines[:orientador_idx]
    else:
        # Sem marcador: todas as linhas pertencem ao nome (atividade sem Tipo:)
        before_tipo = lines

    # Passada 2: extrai nome descartando o(s) docente(s)
    if len(before_tipo) <= 1:
        # Só há 1 linha → é o nome (não há docente separado)
        name_lines = before_tipo
    else:
        last_line = before_tipo[-1]
        if last_line.lower().startswith("e "):
            # Última linha é "e DOCENTE_B" → as 2 últimas linhas são docente conjunto
            name_lines = before_tipo[:-2]
        else:
            # Última linha é o docente único
            name_lines = before_tipo[:-1]

    name = normalize_display_text(" ".join(name_lines))
    return name, local


def _is_activity_row(component_cell: str, class_cell: str | None, schedule_cell: str | None) -> bool:
    """Detecta se a linha da tabela é uma atividade acadêmica (monitoria, orientação, etc.)
    e não uma disciplina regular."""
    cell_upper = component_cell.upper()
    # Presença explícita de marcadores de atividade
    if any(marker in cell_upper for marker in _ACTIVITY_MARKERS):
        return True
    # Ausência de 'Tipo: DISCIPLINA' com turma e horário vazios ('--')
    has_tipo_disciplina = "TIPO: DISCIPLINA" in cell_upper
    turma_vazia = not class_cell or class_cell.strip() in ("", "--", "-")
    horario_vazio = not schedule_cell or schedule_cell.strip() in ("", "--", "-")
    if turma_vazia and horario_vazio and not has_tipo_disciplina:
        return True
    return False


def _parse_table_row(
    row: list[str | None],
    col_code: int,
    col_component: int,
    col_class: int,
    col_schedule: int,
) -> ExtractedCandidate | None:
    """Converte uma linha da tabela estruturada do SIGAA em ExtractedCandidate."""

    def cell(idx: int) -> str:
        val = row[idx] if idx < len(row) else None
        return (val or "").strip()

    code_raw = cell(col_code)
    component_raw = cell(col_component)
    class_raw = cell(col_class)
    schedule_raw = cell(col_schedule)

    # Ignora linhas completamente vazias
    if not code_raw and not component_raw:
        return None

    # Valida o código: deve corresponder ao padrão curricular
    if not CODE_RE.search(code_raw.upper()):
        return None

    code = normalize_code(code_raw)
    warnings: list[str] = []

    # Detecta se é atividade acadêmica
    is_activity = _is_activity_row(component_raw, class_raw, schedule_raw)

    # Extrai nome e local
    name, local = _extract_discipline_name(component_raw)

    # Extrai turma: remover traço que representa ausência
    class_code_raw = class_raw.strip()
    class_code = class_code_raw if class_code_raw and class_code_raw != "--" else None

    # Extrai código de horário
    schedule_code = _extract_schedule_code(schedule_raw)

    if not name:
        warnings.append("Nome da disciplina nao foi identificado com confianca.")

    item_type = "activity" if is_activity else "discipline"

    if item_type == "discipline":
        if not name:
            confidence = "low"
        elif not schedule_code or not class_code:
            confidence = "medium"
            if not schedule_code:
                warnings.append("Horario nao identificado.")
            if not class_code:
                warnings.append("Turma nao identificada.")
        else:
            confidence = "high"
    else:
        confidence = "medium"
        warnings.append("Atividade academica fora do cadastro de disciplinas.")

    return ExtractedCandidate(
        item_type=item_type,
        code=code,
        name=name,
        class_code=class_code,
        schedule_code=schedule_code,
        local=local,
        confidence=confidence,
        warnings=tuple(warnings),
    )


def _find_table_columns(headers: list[str | None]) -> tuple[int, int, int, int] | None:
    """Identifica os índices das colunas esperadas no cabeçalho da tabela.
    Retorna (col_code, col_component, col_class, col_schedule) ou None se não reconhecido."""
    normalized = [normalize_name_for_compare(h) or "" for h in headers]

    col_code = -1
    col_component = -1
    col_class = -1
    col_schedule = -1

    for i, h in enumerate(normalized):
        if "cod" in h and col_code == -1:
            col_code = i
        elif ("componente" in h or "docente" in h) and col_component == -1:
            col_component = i
        elif "turma" in h and col_class == -1:
            col_class = i
        elif ("horario" in h or "hor" in h) and col_schedule == -1:
            col_schedule = i

    if -1 in (col_code, col_component, col_class, col_schedule):
        return None
    return col_code, col_component, col_class, col_schedule


def extract_candidates_from_table(tables: list[list[list[str | None]]]) -> list[ExtractedCandidate]:
    """Extrai candidatos de tabelas estruturadas detectadas pelo pdfplumber.
    Prioriza a primeira tabela com o cabeçalho esperado do atestado de matrícula."""
    candidates: list[ExtractedCandidate] = []

    for table in tables:
        if not table:
            continue
        header_row = table[0]
        cols = _find_table_columns(header_row)
        if cols is None:
            continue  # não é a tabela de disciplinas
        col_code, col_component, col_class, col_schedule = cols
        for row in table[1:]:  # pula o cabeçalho
            candidate = _parse_table_row(row, col_code, col_component, col_class, col_schedule)
            if candidate is not None:
                candidates.append(candidate)
            if len(candidates) >= MAX_ITEMS:
                break
        if candidates:
            break  # encontrou a tabela certa

    return candidates


# ---- Fallback: extração a partir de texto plano ----

def _is_noise_line(line: str) -> bool:
    """Detecta linhas de ruído (cabeçalho, rodapé, tabela de horários semanal)."""
    if len(line.strip()) < 4:
        return True
    if _NOISE_RE.search(line):
        return True
    return False


def _candidate_from_text_line(line: str) -> ExtractedCandidate | None:
    """Fallback: tenta extrair um candidato de uma linha de texto plano."""
    line = normalize_display_text(line) or ""
    if _is_noise_line(line):
        return None
    upper = line.upper()
    code_matches = CODE_RE.findall(upper)
    if not code_matches:
        return None
    if len(set(code_matches)) > 1:
        return ExtractedCandidate("discipline", normalize_code(code_matches[0]), None, None, None, None, "low", ("Linha contem multiplos codigos plausiveis.",))
    code = normalize_code(code_matches[0])
    after = line[line.upper().index(code_matches[0]) + len(code_matches[0]):]
    tokens = [t.strip(" ;|,") for t in after.split() if t.strip(" ;|,")]
    name_tokens: list[str] = []
    class_code: str | None = None
    schedule_code: str | None = None
    for token in tokens:
        if schedule_code is None and SCHEDULE_RE.fullmatch(token):
            schedule_code = token.upper()
        elif class_code is None and re.fullmatch(r"[A-Z]?\d{2}[A-Z]?", token, re.IGNORECASE):
            class_code = token.upper()
        elif token.upper() in _STATUS_WORDS:
            pass
        else:
            name_tokens.append(token)
    name = normalize_display_text(" ".join(name_tokens))
    warnings = []
    if not name:
        warnings.append("Nome da disciplina nao foi identificado com confianca.")
        return ExtractedCandidate("discipline", code, None, class_code, schedule_code, None, "low", tuple(warnings))
    is_activity = any(m in upper for m in _ACTIVITY_MARKERS)
    return ExtractedCandidate(
        "activity" if is_activity else "discipline",
        code,
        name,
        class_code,
        schedule_code,
        None,
        "medium" if warnings else "high",
        tuple(warnings),
    )


def extract_candidates_from_text(text: str) -> list[ExtractedCandidate]:
    """Fallback: extrai candidatos de texto plano quando tabelas não estão disponíveis."""
    candidates: list[ExtractedCandidate] = []
    # Separa em blocos por código curricular
    blocks = re.split(r"(?=\b[A-Z]{2,5}\d{4}\b)", text)
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        candidate = _candidate_from_text_line(block)
        if candidate is not None:
            candidates.append(candidate)
        if len(candidates) >= MAX_ITEMS:
            break
    return candidates


# ---- Extração do PDF ----

def _page_count_naive(data: bytes) -> int:
    count = len(re.findall(rb"/Type\s*/Page\b", data))
    return max(1, count)


def extract_pdf_data(path: Path) -> tuple[list[ExtractedCandidate], int]:
    """Extrai candidatos de disciplinas de um PDF de atestado de matrícula.

    Estratégia:
    1. Valida o arquivo (tamanho, assinatura, criptografia).
    2. Tenta extrair tabelas estruturadas com pdfplumber (caminho principal).
    3. Fallback para texto plano com pypdf se nenhuma tabela reconhecida for encontrada.
    4. Se nenhum texto extraível, lança ImportValidationError para fallback manual.
    """
    data = path.read_bytes()
    if not data:
        raise ImportValidationError("Arquivo PDF vazio.", "invalid_file")
    if len(data) > MAX_PDF_BYTES:
        raise ImportValidationError("Arquivo PDF acima do limite permitido.", "invalid_file")
    if not data.startswith(b"%PDF-"):
        raise ImportValidationError("Arquivo enviado nao parece ser um PDF valido.", "invalid_file")
    if b"/Encrypt" in data:
        raise ImportValidationError("PDF criptografado nao e suportado neste MVP.", "invalid_file")

    # Tenta pdfplumber (extração de tabelas — caminho principal)
    try:
        import pdfplumber  # type: ignore

        with pdfplumber.open(str(path)) as pdf:
            page_count = len(pdf.pages)
            if page_count > MAX_PAGES:
                raise ImportValidationError("PDF possui paginas acima do limite permitido.", "invalid_file")
            tables: list[list[list[str | None]]] = []
            for page in pdf.pages:
                page_tables = page.extract_tables()
                if page_tables:
                    tables.extend(page_tables)
            if tables:
                candidates = extract_candidates_from_table(tables)
                if candidates:
                    _log_event("pdf_extraction_method", method="pdfplumber_tables", table_count=len(tables), candidate_count=len(candidates))
                    return candidates, page_count
            # Sem tabelas reconhecidas: tenta texto plano via pdfplumber
            full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
            if normalize_display_text(full_text):
                candidates = extract_candidates_from_text(full_text)
                _log_event("pdf_extraction_method", method="pdfplumber_text_fallback", candidate_count=len(candidates))
                return candidates, page_count
    except ImportValidationError:
        raise
    except Exception as exc:
        logger.warning(json.dumps({"event": "pdfplumber_error", "error_type": type(exc).__name__}))

    # Fallback pypdf
    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(str(path))
        if reader.is_encrypted:
            raise ImportValidationError("PDF criptografado nao e suportado neste MVP.", "invalid_file")
        page_count = len(reader.pages)
        if page_count > MAX_PAGES:
            raise ImportValidationError("PDF possui paginas acima do limite permitido.", "invalid_file")
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        if normalize_display_text(text):
            candidates = extract_candidates_from_text(text)
            _log_event("pdf_extraction_method", method="pypdf_text_fallback", candidate_count=len(candidates))
            return candidates, page_count
    except ImportValidationError:
        raise
    except Exception as exc:
        logger.warning(json.dumps({"event": "pypdf_error", "error_type": type(exc).__name__}))

    # Fallback final: conta páginas ingenuamente e informa que não há texto
    page_count_naive = _page_count_naive(data)
    if page_count_naive > MAX_PAGES:
        raise ImportValidationError("PDF possui paginas acima do limite permitido.", "invalid_file")
    raise ImportValidationError("PDF valido, mas sem texto extraivel. Use o cadastro manual.", "parse_error")


def _summary(items: list[ImportPreviewItem]) -> ImportPreviewSummary:
    return ImportPreviewSummary(
        recognized_count=sum(item.status == "recognized" for item in items),
        ambiguous_count=sum(item.status == "ambiguous" for item in items),
        not_found_count=sum(item.status == "not_found" for item in items),
        duplicate_count=sum(item.status == "duplicate" for item in items),
        activity_count=sum(item.status == "activity" for item in items),
        rejected_count=sum(item.status == "rejected" for item in items),
    )


def _status_for_candidate(candidate: ExtractedCandidate, seen_codes: set[str]) -> tuple[str, bool, list[str]]:
    warnings = list(candidate.warnings)
    code = normalize_code(candidate.code)
    if candidate.item_type == "activity":
        return "activity", False, warnings
    if code and code in seen_codes:
        return "duplicate", False, warnings + ["Disciplina repetida na pre-visualizacao."]
    if code and storage.find_discipline_by_code(code):
        return "duplicate", False, warnings + ["Disciplina ja cadastrada."]
    if not code or not candidate.name:
        return "ambiguous", False, warnings
    return "recognized", True, warnings


def build_preview_from_pdf(path: Path, sigaa_lookup: SigaaLookup | None = None) -> MatriculaPdfPreviewResponse:
    request_id = str(uuid4())
    preview_id = str(uuid4())
    start = _now_ms()
    storage.cleanup_expired_import_previews()

    candidates, page_count = extract_pdf_data(path)

    warnings: list[str] = []
    if not candidates:
        warnings.append("Nenhuma disciplina foi reconhecida no PDF. Use o cadastro manual.")

    items: list[ImportPreviewItem] = []
    seen_codes: set[str] = set()
    for candidate in candidates:
        code = normalize_code(candidate.code)
        status, selected, item_warnings = _status_for_candidate(candidate, seen_codes)
        if code and status != "duplicate":
            seen_codes.add(code)
        sigaa_status = "not_queried"
        source = "pdf_local"
        if sigaa_lookup and code and status in {"recognized", "not_found"}:
            try:
                result = sigaa_lookup(code)
                sigaa_status = getattr(result, "status", None) or result.get("status", "error")
                component = getattr(result, "component", None) or result.get("component")
                if sigaa_status == "found" and component:
                    source = "pdf_local_sigaa_enriched"
                elif sigaa_status == "not_found" and status == "recognized":
                    status = "not_found"
                    item_warnings.append("Componente nao encontrado na consulta publica do SIGAA.")
            except Exception:
                sigaa_status = "error"
                item_warnings.append("Consulta publica ao SIGAA indisponivel; dados locais preservados.")
        items.append(
            ImportPreviewItem.model_validate(
                {
                    "preview_item_id": str(uuid4()),
                    "item_type": candidate.item_type,
                    "status": status,
                    "selected": selected,
                    "code": code,
                    "name": candidate.name,
                    "class_code": candidate.class_code,
                    "schedule_code": candidate.schedule_code,
                    "local": candidate.local,
                    "source": source,
                    "sigaa_lookup": sigaa_status,
                    "confidence": candidate.confidence,
                    "warnings": item_warnings,
                }
            )
        )

    expires_at = storage.utc_now() + timedelta(minutes=PREVIEW_TTL_MINUTES)
    status_str = "success" if items else "no_items"
    response = MatriculaPdfPreviewResponse(
        status=status_str,
        preview_id=preview_id,
        expires_at=expires_at,
        items=items,
        summary=_summary(items),
        warnings=warnings,
        request_id=request_id,
    )
    storage.save_import_preview(
        {
            "preview_id": preview_id,
            "expires_at": expires_at,
            "items": [item.model_dump(mode="json") for item in items],
            "confirmed": False,
        }
    )
    _log_event(
        "matricula_import_preview_created",
        request_id=request_id,
        preview_id=preview_id,
        latency_ms=_duration_ms(start),
        page_count=page_count,
        item_count=len(items),
        recognized=response.summary.recognized_count,
        ambiguous=response.summary.ambiguous_count,
        duplicates=response.summary.duplicate_count,
        activities=response.summary.activity_count,
    )
    return response


def _minimum_valid(item: ImportConfirmationItem) -> bool:
    return bool(normalize_code(item.code) and normalize_display_text(item.name))


def _existing_preview_item_map(preview: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item["preview_item_id"]): item for item in preview.get("items", [])}


def confirm_import(payload: MatriculaImportConfirmRequest) -> MatriculaImportConfirmResponse:
    request_id = str(uuid4())
    preview_id = str(payload.preview_id)
    preview = storage.get_import_preview(preview_id)
    if preview is None:
        raise ImportPreviewNotFoundError("Pre-visualizacao expirada ou inexistente.")

    stored_items = _existing_preview_item_map(preview)
    created: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    warnings: list[str] = []
    seen_codes: set[str] = set()

    for item in payload.items:
        item_id = str(item.preview_item_id)
        original = stored_items.get(item_id)
        if original is None:
            rejected.append({"preview_item_id": item.preview_item_id, "code": item.code, "name": item.name, "reason": "Item nao pertence a pre-visualizacao."})
            continue
        code = normalize_code(item.code if item.code is not None else original.get("code"))
        name = normalize_display_text(item.name if item.name is not None else original.get("name"))
        class_code = normalize_display_text(item.class_code if item.class_code is not None else original.get("class_code"))
        schedule_code = normalize_display_text(item.schedule_code if item.schedule_code is not None else original.get("schedule_code"))
        local = normalize_display_text(item.local if item.local is not None else original.get("local"))

        if not item.selected:
            skipped.append({"preview_item_id": item.preview_item_id, "code": code, "name": name, "reason": "Item desmarcado pelo usuario."})
            continue
        if original.get("item_type") == "activity":
            rejected.append({"preview_item_id": item.preview_item_id, "code": code, "name": name, "reason": "Atividade academica nao e cadastrada como disciplina neste MVP."})
            continue
        if not _minimum_valid(ImportConfirmationItem(preview_item_id=item.preview_item_id, selected=True, code=code, name=name)):
            rejected.append({"preview_item_id": item.preview_item_id, "code": code, "name": name, "reason": "Codigo e nome sao obrigatorios para cadastro."})
            continue
        if code in seen_codes:
            duplicates.append({"preview_item_id": item.preview_item_id, "code": code, "name": name, "reason": "Duplicata interna na confirmacao."})
            continue
        seen_codes.add(code)
        existing = storage.find_discipline_by_code(code)
        if existing is not None:
            duplicates.append({"preview_item_id": item.preview_item_id, "code": code, "name": name, "reason": "Disciplina ja cadastrada."})
            continue
        try:
            discipline = storage.create_discipline(
                {
                    "code": code,
                    "name": name,
                    "professor": None,
                    "class_code": class_code,
                    "schedule_code": schedule_code,
                    "local": local,
                }
            )
            created.append({"preview_item_id": item.preview_item_id, "discipline_id": discipline["id"], "code": code, "name": name})
        except Exception:
            rejected.append({"preview_item_id": item.preview_item_id, "code": code, "name": name, "reason": "Falha ao cadastrar este item."})

    if not created and not duplicates and not rejected and skipped:
        status = "no_items"
    elif created and (duplicates or rejected or skipped):
        status = "partial_success"
    elif created:
        status = "success"
    elif duplicates or rejected:
        status = "partial_success"
    else:
        status = "no_items"
    if duplicates or rejected:
        warnings.append("Alguns itens nao foram cadastrados; revise o relatorio por item.")

    response = MatriculaImportConfirmResponse.model_validate(
        {
            "status": status,
            "preview_id": preview_id,
            "created": created,
            "duplicates": duplicates,
            "rejected": rejected,
            "skipped": skipped,
            "warnings": warnings,
            "summary": {
                "created_count": len(created),
                "duplicate_count": len(duplicates),
                "rejected_count": len(rejected),
                "skipped_count": len(skipped),
            },
            "request_id": request_id,
        }
    )
    storage.delete_import_preview(preview_id)
    _log_event(
        "matricula_import_confirmed",
        request_id=request_id,
        preview_id=preview_id,
        status=response.status,
        created_count=len(created),
        duplicate_count=len(duplicates),
        rejected_count=len(rejected),
        skipped_count=len(skipped),
    )
    return response
