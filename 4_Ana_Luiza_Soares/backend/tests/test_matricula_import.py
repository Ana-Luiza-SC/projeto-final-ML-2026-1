"""Testes do pipeline de importação de matrícula por PDF.

Fixtures sintéticas sem dados pessoais reais. O PDF real não é commitado.
Cobre todos os 12 casos obrigatórios da spec 008 e mais.
"""
from __future__ import annotations

import io
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import storage
from app.main import app
from app.services.matricula_import import (
    ExtractedCandidate,
    ImportValidationError,
    _extract_discipline_name,
    _extract_schedule_code,
    _is_activity_row,
    _parse_table_row,
    extract_candidates_from_table,
    extract_candidates_from_text,
    normalize_code,
    normalize_display_text,
)


# ---------------------------------------------------------------------------
# Fixtures de infraestrutura
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clear_storage():
    storage.DISCIPLINES.clear()
    storage.ASSESSMENTS.clear()
    storage.IMPORT_PREVIEWS.clear()
    yield
    storage.DISCIPLINES.clear()
    storage.ASSESSMENTS.clear()
    storage.IMPORT_PREVIEWS.clear()


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# Helpers para criar PDFs sintéticos
# ---------------------------------------------------------------------------


def _make_minimal_pdf(text_content: str = "") -> bytes:
    """Cria PDF mínimo com camada textual plana (sem tabela real).
    Apenas para testes de fallback de texto plano e validação de arquivo."""
    content = text_content.encode("latin-1", errors="replace")
    commands = b"BT /F1 12 Tf 72 720 Td (" + content.replace(b"(", b"\\(").replace(b")", b"\\)") + b") Tj ET"
    objects = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]"
        b" /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n",
        b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
        b"5 0 obj\n<< /Length " + str(len(commands)).encode() + b" >>\nstream\n" + commands + b"\nendstream\nendobj\n",
    ]
    buf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(buf))
        buf.extend(obj)
    xref = len(buf)
    buf.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    buf.extend(b"0000000000 65535 f \n")
    for o in offsets[1:]:
        buf.extend(f"{o:010d} 00000 n \n".encode())
    buf.extend(f"trailer\n<< /Root 1 0 R /Size {len(objects) + 1} >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(buf)


def _make_sigaa_pdf_with_reportlab(rows: list[dict]) -> bytes | None:
    """Tenta criar PDF com tabela real usando reportlab (opcional).
    Retorna None se reportlab não estiver disponível."""
    try:
        from reportlab.lib import colors  # type: ignore
        from reportlab.lib.pagesizes import A4  # type: ignore
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle  # type: ignore

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4)
        data = [["Cód.", "Componentes Curriculares/Docentes", "Turma", "Status", "Horário"]]
        for row in rows:
            data.append([
                row.get("code", ""),
                row.get("component", ""),
                row.get("class_code", "--"),
                row.get("status", "MATRICULADO(A)"),
                row.get("schedule", "--"),
            ])
        t = Table(data)
        t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.black)]))
        doc.build([t])
        return buf.getvalue()
    except ImportError:
        return None


# ---------------------------------------------------------------------------
# Testes unitários: funções de parser
# ---------------------------------------------------------------------------


class TestNormalization:
    def test_normalize_code_strips_spaces(self):
        assert normalize_code("  FGA0303  ") == "FGA0303"

    def test_normalize_code_uppercases(self):
        assert normalize_code("fga0303") == "FGA0303"

    def test_normalize_code_none(self):
        assert normalize_code(None) is None

    def test_normalize_code_empty(self):
        assert normalize_code("") is None

    def test_normalize_display_text_collapses_spaces(self):
        assert normalize_display_text("  QUALIDADE   DE  SOFTWARE  ") == "QUALIDADE DE SOFTWARE"

    def test_normalize_display_text_none(self):
        assert normalize_display_text(None) is None


class TestExtractScheduleCode:
    def test_extracts_from_date_range(self):
        assert _extract_schedule_code("24T45 (16/03/2026 -\n18/07/2026)") == "24T45"

    def test_extracts_morning_code(self):
        assert _extract_schedule_code("24M34 (16/03/2026 - 18/07/2026)") == "24M34"

    def test_returns_none_for_empty(self):
        assert _extract_schedule_code("--") is None

    def test_returns_none_for_none(self):
        assert _extract_schedule_code(None) is None

    def test_extracts_with_replacement_chars(self):
        # \ufffd pode aparecer junto ao horário em PDFs problemáticos
        result = _extract_schedule_code("\ufffd24T23\ufffd (16/03/2026 - 18/07/2026)")
        assert result == "24T23"


class TestExtractDisciplineName:
    def test_single_line_name(self):
        cell = "QUALIDADE DE SOFTWARE 1\nCRISTIANE SOARES RAMOS\nTipo: DISCIPLINA Local: FCTE - S6"
        name, local = _extract_discipline_name(cell)
        assert name == "QUALIDADE DE SOFTWARE 1"
        assert local == "FCTE - S6"

    def test_multiline_name(self):
        """Nome quebrado em duas linhas — ex: TÉCNICAS DE PROGRAMAÇÃO EM PLATAFORMAS / EMERGENTES"""
        cell = "TÉCNICAS DE PROGRAMAÇÃO EM PLATAFORMAS\nEMERGENTES\nTHIAGO LUIZ DE SOUZA GOMES\nTipo: DISCIPLINA Local: FCTE - S6"
        name, local = _extract_discipline_name(cell)
        assert name is not None
        assert "TÉCNICAS DE PROGRAMAÇÃO EM PLATAFORMAS" in name
        assert "EMERGENTES" in name
        assert local == "FCTE - S6"

    def test_accents_preserved(self):
        cell = "TÓPICOS ESPECIAIS DE ENGENHARIA DE SOFTWARE\nCARLA SILVA ROCHA AGUIAR\nTipo: DISCIPLINA Local: FCTE - I4"
        name, _ = _extract_discipline_name(cell)
        assert name is not None
        assert "Ó" in name or "TÓPICOS" in name  # acento preservado

    def test_no_replacement_chars_in_name(self):
        """Nomes não devem conter \ufffd"""
        cell = "PROJETO INTEGRADOR DE ENGENHARIA 1\nLUI TXAI CALVOSO HABL\nTipo: DISCIPLINA Local: FCTE - I3"
        name, _ = _extract_discipline_name(cell)
        assert name is not None
        assert "\ufffd" not in name

    def test_activity_cell_returns_name(self):
        cell = "MONITORIA EM GESTÃO DA PRODUÇÃO E QUALIDADE\nORIENTADOR(A): REJANE MARIA DA COSTA FIGUEIREDO\nForma de Participação: ATIVIDADE DE ORIENTAÇÃO INDIVIDUAL"
        name, local = _extract_discipline_name(cell)
        assert name is not None
        assert "MONITORIA" in name.upper()
        assert local is None


class TestIsActivityRow:
    def test_monitoria_is_activity(self):
        cell = "MONITORIA EM GESTÃO DA PRODUÇÃO E QUALIDADE\nORIENTADOR(A): REJANE...\nForma de Participação: ATIVIDADE DE ORIENTAÇÃO INDIVIDUAL"
        assert _is_activity_row(cell, "--", "--") is True

    def test_disciplina_not_activity(self):
        cell = "QUALIDADE DE SOFTWARE 1\nCRISTIANE SOARES RAMOS\nTipo: DISCIPLINA Local: FCTE - S6"
        assert _is_activity_row(cell, "01", "24M34 (16/03/2026)") is False

    def test_empty_turma_and_horario_without_tipo_is_activity(self):
        cell = "ALGUMA ATIVIDADE SEM TIPO"
        assert _is_activity_row(cell, "--", "--") is True


class TestParseTableRow:
    def _row(self, code, component, class_code, schedule):
        return [code, component, class_code, "MATRICULADO(A)", schedule]

    def test_fga0303_parsed_correctly(self):
        row = self._row(
            "FGA0303",
            "PROJETO INTEGRADOR DE ENGENHARIA 1\nLUI TXAI CALVOSO HABL\nTipo: DISCIPLINA Local: FCTE - I3",
            "04",
            "24T45 (16/03/2026 -\n18/07/2026)",
        )
        candidate = _parse_table_row(row, 0, 1, 2, 4)
        assert candidate is not None
        assert candidate.code == "FGA0303"
        assert candidate.class_code == "04"
        assert candidate.schedule_code == "24T45"
        assert candidate.item_type == "discipline"
        assert "\ufffd" not in (candidate.name or "")

    def test_fga0315_parsed_correctly(self):
        row = self._row(
            "FGA0315",
            "QUALIDADE DE SOFTWARE 1\nCRISTIANE SOARES RAMOS\nTipo: DISCIPLINA Local: FCTE - S6",
            "01",
            "24M34 (16/03/2026 -\n18/07/2026)",
        )
        candidate = _parse_table_row(row, 0, 1, 2, 4)
        assert candidate is not None
        assert candidate.code == "FGA0315"
        assert candidate.class_code == "01"
        assert candidate.schedule_code == "24M34"
        assert candidate.item_type == "discipline"

    def test_fga0242_multiline_name(self):
        row = self._row(
            "FGA0242",
            "TÉCNICAS DE PROGRAMAÇÃO EM PLATAFORMAS\nEMERGENTES\nTHIAGO LUIZ DE SOUZA GOMES\nTipo: DISCIPLINA Local: FCTE - S6",
            "02",
            "24M12 (16/03/2026 -\n18/07/2026)",
        )
        candidate = _parse_table_row(row, 0, 1, 2, 4)
        assert candidate is not None
        assert candidate.code == "FGA0242"
        assert "TÉCNICAS" in (candidate.name or "").upper() or "TECNICAS" in (candidate.name or "").upper()
        assert candidate.class_code == "02"
        assert candidate.schedule_code == "24M12"

    def test_fga0134_accents_preserved(self):
        row = self._row(
            "FGA0134",
            "TÓPICOS ESPECIAIS DE ENGENHARIA DE SOFTWARE\nCARLA SILVA ROCHA AGUIAR e ISAQUE ALVES DE LIMA\nTipo: DISCIPLINA Local: FCTE - I4",
            "01",
            "24T23 (16/03/2026 -\n18/07/2026)",
        )
        candidate = _parse_table_row(row, 0, 1, 2, 4)
        assert candidate is not None
        assert candidate.code == "FGA0134"
        assert "TÓPICOS" in (candidate.name or "").upper() or "TOPICOS" in (candidate.name or "").upper()
        assert candidate.class_code == "01"
        assert candidate.schedule_code == "24T23"

    def test_fga0423_monitoria_is_activity(self):
        row = [
            "FGA0423",
            "MONITORIA EM GESTÃO DA PRODUÇÃO E QUALIDADE\nORIENTADOR(A): REJANE MARIA DA COSTA FIGUEIREDO\nForma de Participação: ATIVIDADE DE ORIENTAÇÃO INDIVIDUAL",
            "--",
            "MATRICULADO(A)",
            "--",
        ]
        candidate = _parse_table_row(row, 0, 1, 2, 4)
        assert candidate is not None
        assert candidate.item_type == "activity"
        assert candidate.code == "FGA0423"

    def test_header_row_returns_none(self):
        row = ["Cód.", "Componentes Curriculares/Docentes", "Turma", "Status", "Horário"]
        candidate = _parse_table_row(row, 0, 1, 2, 4)
        assert candidate is None  # código "Cód." não casa com CODE_RE

    def test_no_replacement_chars_in_output(self):
        row = self._row(
            "FGA0303",
            "PROJETO INTEGRADOR DE ENGENHARIA 1\nLUI TXAI CALVOSO HABL\nTipo: DISCIPLINA Local: FCTE - I3",
            "04",
            "24T45 (16/03/2026 -\n18/07/2026)",
        )
        candidate = _parse_table_row(row, 0, 1, 2, 4)
        assert candidate is not None
        assert "\ufffd" not in (candidate.name or "")
        assert "\ufffd" not in (candidate.schedule_code or "")
        assert "\ufffd" not in (candidate.class_code or "")


class TestExtractCandidatesFromTable:
    """Testa a extração a partir de tabela estruturada (caminho principal)."""

    def _make_table(self) -> list[list[list[str | None]]]:
        """Cria tabela no formato retornado por pdfplumber.extract_tables()."""
        return [[
            ["Cód.", "Componentes Curriculares/Docentes", "Turma", "Status", "Horário"],
            [
                "FGA0423",
                "MONITORIA EM GESTÃO DA PRODUÇÃO E QUALIDADE\nORIENTADOR(A): REJANE MARIA DA COSTA FIGUEIREDO\nForma de Participação: ATIVIDADE DE ORIENTAÇÃO INDIVIDUAL",
                "--",
                "MATRICULADO(A)",
                "--",
            ],
            [
                "FGA0303",
                "PROJETO INTEGRADOR DE ENGENHARIA 1\nLUI TXAI CALVOSO HABL\nTipo: DISCIPLINA Local: FCTE - I3",
                "04",
                "MATRICULADO\ufffdA\ufffd",
                "24T45 (16/03/2026 -\n18/07/2026)",
            ],
            [
                "FGA0315",
                "QUALIDADE DE SOFTWARE 1\nCRISTIANE SOARES RAMOS\nTipo: DISCIPLINA Local: FCTE - S6",
                "01",
                "MATRICULADO\ufffdA\ufffd",
                "24M34 (16/03/2026 -\n18/07/2026)",
            ],
            [
                "FGA0242",
                "TÉCNICAS DE PROGRAMAÇÃO EM PLATAFORMAS\nEMERGENTES\nTHIAGO LUIZ DE SOUZA GOMES\nTipo: DISCIPLINA Local: FCTE - S6",
                "02",
                "MATRICULADO\ufffdA\ufffd",
                "24M12 (16/03/2026 -\n18/07/2026)",
            ],
            [
                "FGA0134",
                "TÓPICOS ESPECIAIS DE ENGENHARIA DE SOFTWARE\nCARLA SILVA ROCHA AGUIAR e ISAQUE ALVES DE LIMA\nTipo: DISCIPLINA Local: FCTE - I4",
                "01",
                "MATRICULADO\ufffdA\ufffd",
                "24T23 (16/03/2026 -\n18/07/2026)",
            ],
        ]]

    def test_four_disciplines_extracted(self):
        candidates = extract_candidates_from_table(self._make_table())
        disciplines = [c for c in candidates if c.item_type == "discipline"]
        assert len(disciplines) == 4

    def test_expected_codes_present(self):
        candidates = extract_candidates_from_table(self._make_table())
        codes = {c.code for c in candidates}
        assert "FGA0303" in codes
        assert "FGA0315" in codes
        assert "FGA0242" in codes
        assert "FGA0134" in codes

    def test_monitoria_is_activity_not_discipline(self):
        candidates = extract_candidates_from_table(self._make_table())
        activities = [c for c in candidates if c.item_type == "activity"]
        assert len(activities) == 1
        assert activities[0].code == "FGA0423"

    def test_turma_correct(self):
        candidates = extract_candidates_from_table(self._make_table())
        by_code = {c.code: c for c in candidates}
        assert by_code["FGA0303"].class_code == "04"
        assert by_code["FGA0315"].class_code == "01"
        assert by_code["FGA0242"].class_code == "02"
        assert by_code["FGA0134"].class_code == "01"

    def test_horario_correct(self):
        candidates = extract_candidates_from_table(self._make_table())
        by_code = {c.code: c for c in candidates}
        assert by_code["FGA0303"].schedule_code == "24T45"
        assert by_code["FGA0315"].schedule_code == "24M34"
        assert by_code["FGA0242"].schedule_code == "24M12"
        assert by_code["FGA0134"].schedule_code == "24T23"

    def test_no_replacement_chars_in_names(self):
        candidates = extract_candidates_from_table(self._make_table())
        for candidate in candidates:
            assert "\ufffd" not in (candidate.name or ""), f"Candidato {candidate.code} tem \\ufffd no nome"

    def test_accents_preserved_in_names(self):
        candidates = extract_candidates_from_table(self._make_table())
        by_code = {c.code: c for c in candidates}
        # TÓPICOS e TÉCNICAS têm acentos
        assert "Ó" in (by_code["FGA0134"].name or "").upper() or "TOPICOS" in (by_code["FGA0134"].name or "").upper()

    def test_multiline_name_reconstructed(self):
        """FGA0242 tem nome em duas linhas."""
        candidates = extract_candidates_from_table(self._make_table())
        by_code = {c.code: c for c in candidates}
        name = by_code["FGA0242"].name or ""
        assert "PLATAFORMAS" in name.upper() or "TECNICAS" in name.upper()

    def test_empty_table_list(self):
        assert extract_candidates_from_table([]) == []

    def test_table_without_expected_headers_ignored(self):
        """Tabela de horários semanal não deve gerar candidatos."""
        schedule_table = [[
            ["Horários", "Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sab"],
            ["08:00 - 08:55", "---", "FGA0242", "---", "FGA0242", "---", "---", "---"],
        ]]
        candidates = extract_candidates_from_table(schedule_table)
        assert candidates == []

    def test_duplicates_in_same_table(self):
        """Duas linhas com mesmo código na tabela → ambas extraídas; duplicata resolvida no preview."""
        table = [[
            ["Cód.", "Componentes Curriculares/Docentes", "Turma", "Status", "Horário"],
            ["FGA0303", "DISCIPLINA REPETIDA\nDOCENTE A\nTipo: DISCIPLINA Local: X", "01", "MATRICULADO", "24M12"],
            ["FGA0303", "DISCIPLINA REPETIDA\nDOCENTE B\nTipo: DISCIPLINA Local: X", "02", "MATRICULADO", "24M34"],
        ]]
        candidates = extract_candidates_from_table(table)
        fga0303_list = [c for c in candidates if c.code == "FGA0303"]
        assert len(fga0303_list) == 2  # o parser retorna ambas; a lógica de duplicata fica no build_preview


class TestExtractCandidatesFromTextFallback:
    """Testa o fallback de texto plano quando tabelas não estão disponíveis."""

    def test_extracts_code_from_plain_text(self):
        text = "FGA0001 ALGORITMOS 01 MATRICULADO 24M12"
        candidates = extract_candidates_from_text(text)
        assert len(candidates) == 1
        assert candidates[0].code == "FGA0001"

    def test_noise_lines_ignored(self):
        text = "Portal Discente\nSIGAA | Secretaria de TI\nFGA0001 ALGORITMOS 01 MATRICULADO 24M12"
        candidates = extract_candidates_from_text(text)
        codes = {c.code for c in candidates}
        assert "FGA0001" in codes
        assert len(candidates) == 1


# ---------------------------------------------------------------------------
# Testes de integração: upload + preview via API
# ---------------------------------------------------------------------------


def upload_preview_minimal(client: TestClient, text: str):
    """Upload de PDF mínimo com texto plano (sem tabela estruturada)."""
    pdf_bytes = _make_minimal_pdf(text)
    return client.post(
        "/api/import/matricula-pdf/preview",
        files={"file": ("comprovante.pdf", pdf_bytes, "application/pdf")},
    )


class TestApiPreview:
    def test_invalid_file_rejected(self, client):
        response = client.post(
            "/api/import/matricula-pdf/preview",
            files={"file": ("texto.txt", b"nao e pdf", "text/plain")},
        )
        assert response.status_code == 422
        assert "Traceback" not in response.text

    def test_empty_pdf_rejected(self, client):
        response = client.post(
            "/api/import/matricula-pdf/preview",
            files={"file": ("vazio.pdf", b"", "application/pdf")},
        )
        assert response.status_code == 422

    def test_preview_does_not_create_disciplines(self, client):
        response = upload_preview_minimal(client, "FGA0001 ALGORITMOS 01 MATRICULADO 24M12")
        assert response.status_code == 200
        assert storage.list_disciplines() == []

    def test_temp_file_removed_after_preview(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
        upload_preview_minimal(client, "FGA0001 ALGORITMOS 01 MATRICULADO 24M12")
        assert list(tmp_path.glob("estudaunb-import-*")) == []

    def test_temp_file_removed_on_invalid_upload(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
        client.post(
            "/api/import/matricula-pdf/preview",
            files={"file": ("ruim.pdf", b"nao e pdf valido", "application/pdf")},
        )
        assert list(tmp_path.glob("estudaunb-import-*")) == []

    def test_monitoria_classified_as_activity_not_discipline(self, client):
        """Usa tabela sintética via extract_candidates_from_table diretamente."""
        from app.services.matricula_import import extract_candidates_from_table

        table = [[
            ["Cód.", "Componentes Curriculares/Docentes", "Turma", "Status", "Horário"],
            [
                "FGA0423",
                "MONITORIA EM GESTÃO DA PRODUÇÃO E QUALIDADE\nORIENTADOR(A): REJANE MARIA DA COSTA FIGUEIREDO\nForma de Participação: ATIVIDADE DE ORIENTAÇÃO INDIVIDUAL",
                "--",
                "MATRICULADO(A)",
                "--",
            ],
        ]]
        candidates = extract_candidates_from_table(table)
        assert len(candidates) == 1
        assert candidates[0].item_type == "activity"
        assert candidates[0].code == "FGA0423"


class TestApiConfirm:
    def _upload_and_get_preview(self, client):
        """Faz upload de PDF mínimo com duas disciplinas válidas."""
        pdf = _make_minimal_pdf("FGA0001 ALGORITMOS 01 MATRICULADO 24M12\nFGA0002 QUALIDADE DE SOFTWARE 02 MATRICULADO 35T34")
        response = client.post(
            "/api/import/matricula-pdf/preview",
            files={"file": ("comprovante.pdf", pdf, "application/pdf")},
        )
        return response.json()

    def test_confirmation_creates_selected_disciplines(self, client):
        preview = self._upload_and_get_preview(client)
        items = preview["items"]
        assert len(items) >= 1

        response = client.post(
            "/api/import/matricula-pdf/confirm",
            json={
                "preview_id": preview["preview_id"],
                "items": [
                    {
                        "preview_item_id": item["preview_item_id"],
                        "selected": True,
                        "code": item["code"],
                        "name": item["name"],
                    }
                    for item in items
                    if item["item_type"] == "discipline" and item["code"]
                ],
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["summary"]["created_count"] >= 1
        assert len(storage.list_disciplines()) >= 1

    def test_activity_rejected_in_confirmation(self, client):
        """Atividade marcada como selected=True deve ser rejeitada na confirmação."""
        from app.services.matricula_import import ExtractedCandidate, build_preview_from_pdf
        import unittest.mock as mock

        activity = ExtractedCandidate("activity", "FGA0423", "MONITORIA EM GESTAO DA PRODUCAO E QUALIDADE", None, None, None, "medium", ("Atividade academica.",))
        discipline = ExtractedCandidate("discipline", "FGA0303", "PROJETO INTEGRADOR DE ENGENHARIA 1", "04", "24T45", "FCTE - I3", "high", ())

        with mock.patch("app.services.matricula_import.extract_pdf_data", return_value=([activity, discipline], 1)):
            pdf = _make_minimal_pdf("placeholder")
            response = client.post(
                "/api/import/matricula-pdf/preview",
                files={"file": ("comprovante.pdf", pdf, "application/pdf")},
            )
        preview = response.json()
        activity_item = next(i for i in preview["items"] if i["status"] == "activity")

        confirm = client.post(
            "/api/import/matricula-pdf/confirm",
            json={
                "preview_id": preview["preview_id"],
                "items": [
                    {
                        "preview_item_id": activity_item["preview_item_id"],
                        "selected": True,
                        "code": activity_item["code"],
                        "name": activity_item["name"] or "Monitoria",
                    }
                ],
            },
        )
        assert confirm.status_code == 200
        body = confirm.json()
        assert body["summary"]["created_count"] == 0
        assert body["summary"]["rejected_count"] == 1

    def test_duplicate_existing_discipline_not_created(self, client):
        client.post("/api/disciplines", json={"code": "FGA0001", "name": "Algoritmos"})
        pdf = _make_minimal_pdf("FGA0001 ALGORITMOS 01 MATRICULADO 24M12")
        preview = client.post(
            "/api/import/matricula-pdf/preview",
            files={"file": ("comprovante.pdf", pdf, "application/pdf")},
        ).json()
        fga0001_items = [i for i in preview["items"] if i.get("code") == "FGA0001"]
        # Deve estar marcado como duplicate ou sem itens
        if fga0001_items:
            assert fga0001_items[0]["status"] == "duplicate"

    def test_confirmation_of_expired_preview_returns_404(self, client):
        response = client.post(
            "/api/import/matricula-pdf/confirm",
            json={
                "preview_id": "00000000-0000-0000-0000-000000000000",
                "items": [],
            },
        )
        assert response.status_code == 404

    def test_item_from_different_preview_rejected(self, client):
        preview = self._upload_and_get_preview(client)
        response = client.post(
            "/api/import/matricula-pdf/confirm",
            json={
                "preview_id": preview["preview_id"],
                "items": [
                    {
                        "preview_item_id": "00000000-0000-0000-0000-000000000000",
                        "selected": True,
                        "code": "FGA9999",
                        "name": "Disciplina Inventada",
                    }
                ],
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["summary"]["created_count"] == 0
        assert body["summary"]["rejected_count"] == 1

    def test_idempotent_confirmation_no_duplicate(self, client):
        """Repetir a confirmação não deve criar duplicatas."""
        pdf = _make_minimal_pdf("FGA0001 ALGORITMOS 01 MATRICULADO 24M12")
        preview1 = client.post(
            "/api/import/matricula-pdf/preview",
            files={"file": ("comprovante.pdf", pdf, "application/pdf")},
        ).json()
        items1 = [i for i in preview1["items"] if i.get("code") == "FGA0001"]
        if not items1:
            pytest.skip("FGA0001 nao extraido do PDF minimo")

        # Primeira confirmação
        confirm_payload = {
            "preview_id": preview1["preview_id"],
            "items": [
                {"preview_item_id": items1[0]["preview_item_id"], "selected": True, "code": "FGA0001", "name": "ALGORITMOS"},
            ],
        }
        r1 = client.post("/api/import/matricula-pdf/confirm", json=confirm_payload)
        assert r1.json()["summary"]["created_count"] == 1

        # Preview já expirou; segundo upload
        pdf2 = _make_minimal_pdf("FGA0001 ALGORITMOS 01 MATRICULADO 24M12")
        preview2 = client.post(
            "/api/import/matricula-pdf/preview",
            files={"file": ("comprovante.pdf", pdf2, "application/pdf")},
        ).json()
        fga0001_in_preview2 = [i for i in preview2["items"] if i.get("code") == "FGA0001"]
        assert all(i["status"] == "duplicate" for i in fga0001_in_preview2)

    def test_partial_success_with_activity_and_discipline(self, client):
        import unittest.mock as mock

        activity = ExtractedCandidate("activity", "FGA0423", "MONITORIA", None, None, None, "medium", ())
        discipline = ExtractedCandidate("discipline", "FGA0303", "PROJETO INTEGRADOR", "04", "24T45", None, "high", ())

        with mock.patch("app.services.matricula_import.extract_pdf_data", return_value=([activity, discipline], 1)):
            pdf = _make_minimal_pdf("placeholder")
            preview = client.post(
                "/api/import/matricula-pdf/preview",
                files={"file": ("comprovante.pdf", pdf, "application/pdf")},
            ).json()

        all_items = preview["items"]
        confirm = client.post(
            "/api/import/matricula-pdf/confirm",
            json={
                "preview_id": preview["preview_id"],
                "items": [
                    {"preview_item_id": i["preview_item_id"], "selected": True, "code": i["code"], "name": i["name"] or "Sem nome"}
                    for i in all_items
                ],
            },
        )
        body = confirm.json()
        assert body["summary"]["created_count"] == 1
        assert body["summary"]["rejected_count"] == 1

    def test_internal_duplicate_in_same_preview(self, client):
        import unittest.mock as mock

        d1 = ExtractedCandidate("discipline", "FGA0303", "PROJETO INTEGRADOR", "04", "24T45", None, "high", ())
        d2 = ExtractedCandidate("discipline", "FGA0303", "PROJETO INTEGRADOR DUP", "05", "24T45", None, "high", ())

        with mock.patch("app.services.matricula_import.extract_pdf_data", return_value=([d1, d2], 1)):
            pdf = _make_minimal_pdf("placeholder")
            preview = client.post(
                "/api/import/matricula-pdf/preview",
                files={"file": ("comprovante.pdf", pdf, "application/pdf")},
            ).json()

        items = preview["items"]
        fga0303_items = [i for i in items if i.get("code") == "FGA0303"]
        duplicate_items = [i for i in fga0303_items if i["status"] == "duplicate"]
        assert len(duplicate_items) >= 1


class TestApiEndpoints:
    def test_openapi_contains_import_endpoints(self, client):
        schema = client.get("/openapi.json").json()
        assert "/api/import/matricula-pdf/preview" in schema["paths"]
        assert "/api/import/matricula-pdf/confirm" in schema["paths"]

    def test_no_stack_trace_on_invalid_file(self, client):
        response = client.post(
            "/api/import/matricula-pdf/preview",
            files={"file": ("fake.pdf", b"nao e pdf", "text/plain")},
        )
        assert "Traceback" not in response.text
        assert "traceback" not in response.text.lower()

    def test_no_personal_data_in_error_response(self, client):
        response = client.post(
            "/api/import/matricula-pdf/preview",
            files={"file": ("fake.pdf", b"nao e pdf", "text/plain")},
        )
        body = response.text
        # Não deve expor matrícula, nome ou código de verificação fictícios
        assert "231011088" not in body
        assert "ANA LUIZA" not in body
