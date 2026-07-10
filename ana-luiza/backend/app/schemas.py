from __future__ import annotations

from datetime import date as Date, datetime, time
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class DisciplineCreate(BaseModel):
    code: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    professor: str | None = None
    class_code: str | None = None
    schedule_code: str | None = None
    local: str | None = None
    total_classes: int | None = Field(default=None, ge=0)
    missed_classes: int | None = Field(default=None, ge=0)
    total_class_hours: int | None = Field(default=None, ge=0)
    missed_class_hours: int | None = Field(default=None, ge=0)
    sigaa_code: str | None = None
    sigaa_source_url: str | None = None
    syllabus: str | None = None
    current_program: str | None = None
    workload_hours: int | None = Field(default=None, ge=0)
    sigaa_cached_at: datetime | None = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "code": "FGA0000",
                "name": "Disciplina de Exemplo",
                "professor": "Docente",
                "class_code": "01",
                "schedule_code": "24M12",
                "local": "Sala 1",
                "total_classes": 30,
                "missed_classes": 2,
            }
        }
    }


class DisciplineRead(DisciplineCreate):
    id: UUID
    created_at: datetime
    updated_at: datetime


class AttendanceUpdate(BaseModel):
    total_classes: int | None = Field(default=None, ge=0)
    missed_classes: int | None = Field(default=None, ge=0)
    total_class_hours: int | None = Field(default=None, ge=0)
    missed_class_hours: int | None = Field(default=None, ge=0)
    model_config = {
        "json_schema_extra": {
            "example": {
                "total_classes": 30,
                "missed_classes": 4,
                "total_class_hours": None,
                "missed_class_hours": None,
            }
        }
    }


class AcademicActivity(BaseModel):
    id: UUID
    code: str
    name: str
    advisor: str | None = None
    participation_type: str | None = None
    status: str | None = None
    schedule_code: str | None = None


class AssessmentCreate(BaseModel):
    name: str = Field(..., min_length=1)
    weight: float = Field(..., gt=0)
    grade: float | None = Field(default=None, ge=0, le=10)
    date: Date | None = None
    topics: list[str] = Field(default_factory=list)

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Prova 1",
                "weight": 30,
                "grade": 8.0,
                "date": "2026-07-20",
                "topics": ["Introdução", "Exercícios"],
            }
        }
    }


class AssessmentRead(AssessmentCreate):
    id: UUID
    discipline_id: UUID


class AttendanceResult(BaseModel):
    status: str
    source: str | None
    frequency: float | None
    absence_percentage: float | None
    risk_level: str
    warnings: list[str]


class AcademicStatus(BaseModel):
    status: str
    message: str
    warnings: list[str]


class AcademicSimulation(BaseModel):
    current_contribution: float
    partial_average: float | None
    completed_weight: float
    remaining_weight: float
    target_average: float
    required_average_on_remaining: float | None
    current_mention: str | None
    projected_mention: str | None
    grade_risk_level: str
    attendance: AttendanceResult
    academic_status: AcademicStatus
    warnings: list[str]

    model_config = {
        "json_schema_extra": {
            "example": {
                "current_contribution": 2.4,
                "partial_average": 8.0,
                "completed_weight": 0.3,
                "remaining_weight": 0.7,
                "target_average": 5.0,
                "required_average_on_remaining": 3.72,
                "current_mention": "MS",
                "projected_mention": "MM",
                "grade_risk_level": "low",
                "attendance": {
                    "status": "ok",
                    "source": "classes",
                    "frequency": 0.9,
                    "absence_percentage": 0.1,
                    "risk_level": "low",
                    "warnings": [],
                },
                "academic_status": {
                    "status": "passing_simulation",
                    "message": "A simulação indica menção de aprovação, mas ainda há avaliações pendentes.",
                    "warnings": [],
                },
                "warnings": [],
            }
        }
    }


TopicDifficulty = Literal["low", "medium", "high"]
TopicStatus = Literal["not_started", "in_progress", "reviewed"]
DedicationLevel = Literal["low", "medium", "high"]
RecommendationProvider = Literal["google", "rules"]
SigaaSearchStatus = Literal["found", "not_found", "error"]
SigaaSource = Literal["sigaa_public_components"]
StudyPlanDay = Literal[
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]
StudyPlanSource = Literal["llm_assisted", "deterministic_fallback"]
ImportItemType = Literal["discipline", "activity"]
ImportPreviewStatus = Literal[
    "recognized",
    "ambiguous",
    "not_found",
    "duplicate",
    "activity",
    "rejected",
]
ImportSource = Literal["pdf_local", "pdf_local_sigaa_enriched"]
SigaaLookupStatus = Literal["not_queried", "found", "not_found", "error"]
ImportConfirmStatus = Literal["success", "partial_success", "no_items", "error"]


def _parse_hhmm(value: str) -> time:
    try:
        return time.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("Horário deve estar no formato HH:MM.") from exc


def _minutes(value: str) -> int:
    parsed = _parse_hhmm(value)
    return parsed.hour * 60 + parsed.minute


class StudyTopicInput(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)
    difficulty: TopicDifficulty
    status: TopicStatus


class StudyRecommendationRequest(BaseModel):
    discipline_id: UUID
    target_average: float = Field(default=5.0, ge=0, le=10)
    pending_topics: list[StudyTopicInput] = Field(default_factory=list, max_length=30)
    user_goal: str | None = Field(default=None, max_length=500)

    model_config = {
        "json_schema_extra": {
            "example": {
                "discipline_id": "00000000-0000-0000-0000-000000000000",
                "target_average": 5.0,
                "pending_topics": [
                    {
                        "title": "GQM",
                        "difficulty": "medium",
                        "status": "not_started",
                    }
                ],
                "user_goal": "quero me organizar para a próxima semana",
            }
        }
    }


class StudyRecommendationResponse(BaseModel):
    dedication_level: DedicationLevel
    confidence: float = Field(..., ge=0, le=1)
    academic_situation_summary: str
    grade_status: str
    attendance_status: str
    recommended_actions: list[str] = Field(..., min_length=1)
    reasons: list[str] = Field(..., min_length=1)
    missing_information: list[str] = Field(default_factory=list)
    used_fallback: bool
    provider: RecommendationProvider
    latency_ms: float = Field(..., ge=0)

    model_config = {
        "json_schema_extra": {
            "example": {
                "dedication_level": "medium",
                "confidence": 0.76,
                "academic_situation_summary": "Situação simulada com menção projetada MM e frequência informada acima do mínimo.",
                "grade_status": "A menção projetada é MM, uma menção de aprovação na UnB, mas ainda há avaliações pendentes.",
                "attendance_status": "Frequência acima de 75%, sem risco imediato por falta.",
                "recommended_actions": [
                    "Revise os conteúdos ligados à próxima avaliação antes de avançar para novos tópicos."
                ],
                "reasons": ["A simulação indica risco por nota baixo, mas ainda há peso restante."],
                "missing_information": [],
                "used_fallback": True,
                "provider": "rules",
                "latency_ms": 12,
            }
        }
    }


class StudyPlanTimeWindow(BaseModel):
    day: StudyPlanDay
    start_time: str = Field(..., pattern=r"^\d{2}:\d{2}$")
    end_time: str = Field(..., pattern=r"^\d{2}:\d{2}$")

    model_config = {"extra": "forbid"}

    @field_validator("start_time", "end_time")
    @classmethod
    def validate_time_format(cls, value: str) -> str:
        _parse_hhmm(value)
        return value

    @model_validator(mode="after")
    def validate_time_order(self) -> "StudyPlanTimeWindow":
        if _minutes(self.start_time) >= _minutes(self.end_time):
            raise ValueError("Início da janela deve ser menor que o fim.")
        return self


class StudyPlanAvailability(BaseModel):
    available_hours_per_week: float = Field(..., gt=0, le=80)
    days_available: list[StudyPlanDay] = Field(..., min_length=1, max_length=7)
    time_windows: list[StudyPlanTimeWindow] = Field(default_factory=list)

    model_config = {"extra": "forbid"}

    @field_validator("days_available")
    @classmethod
    def validate_unique_days(cls, value: list[StudyPlanDay]) -> list[StudyPlanDay]:
        if len(value) != len(set(value)):
            raise ValueError("Dias disponíveis não podem se repetir.")
        return value

    @model_validator(mode="after")
    def validate_windows(self) -> "StudyPlanAvailability":
        allowed_days = set(self.days_available)
        windows_by_day: dict[str, list[StudyPlanTimeWindow]] = {}
        for window in self.time_windows:
            if window.day not in allowed_days:
                raise ValueError("Janelas devem pertencer aos dias disponíveis.")
            windows_by_day.setdefault(window.day, []).append(window)

        for windows in windows_by_day.values():
            ordered = sorted(windows, key=lambda item: _minutes(item.start_time))
            for previous, current in zip(ordered, ordered[1:]):
                if _minutes(current.start_time) < _minutes(previous.end_time):
                    raise ValueError("Janelas de disponibilidade não podem se sobrepor.")
        return self


class StudyPlanPriority(BaseModel):
    discipline_id: UUID
    priority: int = Field(..., ge=1, le=5)

    model_config = {"extra": "forbid"}


class StudyPlanRequest(BaseModel):
    discipline_ids: list[UUID] = Field(..., min_length=1, max_length=20)
    availability: StudyPlanAvailability
    max_session_minutes: int = Field(..., ge=30, le=240)
    priorities: list[StudyPlanPriority] = Field(default_factory=list, max_length=20)
    objective_text: str | None = Field(default=None, max_length=500)

    model_config = {
        "extra": "forbid",
        "json_schema_extra": {
            "example": {
                "discipline_ids": [
                    "00000000-0000-0000-0000-000000000001",
                    "00000000-0000-0000-0000-000000000002",
                ],
                "availability": {
                    "available_hours_per_week": 6,
                    "days_available": ["monday", "wednesday", "friday"],
                },
                "max_session_minutes": 90,
                "priorities": [
                    {
                        "discipline_id": "00000000-0000-0000-0000-000000000001",
                        "priority": 5,
                    }
                ],
                "objective_text": "quero revisar para a prova da próxima semana",
            }
        },
    }

    @model_validator(mode="after")
    def validate_request(self) -> "StudyPlanRequest":
        ids = [str(item) for item in self.discipline_ids]
        if len(ids) != len(set(ids)):
            raise ValueError("Disciplinas selecionadas não podem se repetir.")
        priority_ids = [str(item.discipline_id) for item in self.priorities]
        if len(priority_ids) != len(set(priority_ids)):
            raise ValueError("Prioridades não podem repetir disciplina.")
        selected = set(ids)
        if any(item not in selected for item in priority_ids):
            raise ValueError("Prioridades devem referenciar apenas disciplinas selecionadas.")
        if self.max_session_minutes % 30 != 0:
            raise ValueError("Duração máxima deve ser múltipla de 30 minutos.")
        return self


class StudyPlanSession(BaseModel):
    day: StudyPlanDay
    sequence: int = Field(..., ge=1)
    discipline_id: UUID
    discipline_code: str
    discipline_name: str
    duration_minutes: int = Field(..., gt=0)
    activity: str
    start_time: str | None = None
    end_time: str | None = None


class StudyPlanMetrics(BaseModel):
    requested_minutes: int
    allocated_minutes: int
    unallocated_minutes: int
    session_count: int
    discipline_count: int


class StudyPlanResponse(BaseModel):
    status: Literal["success"]
    source: StudyPlanSource
    plan: list[StudyPlanSession] = Field(..., min_length=1)
    summary: str
    warnings: list[str] = Field(default_factory=list)
    metrics: StudyPlanMetrics
    request_id: str


class SigaaComponent(BaseModel):
    code: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    type: str | None = None
    unit: str | None = None
    workload_hours: int | None = Field(default=None, ge=0)
    syllabus: str | None = None
    current_program: str | None = None
    source_url: str

    model_config = {
        "json_schema_extra": {
            "example": {
                "code": "FGA0315",
                "name": "QUALIDADE DE SOFTWARE 1",
                "type": "DISCIPLINA",
                "unit": "FCTE",
                "workload_hours": 60,
                "syllabus": "",
                "current_program": "",
                "source_url": "https://sigaa.unb.br/sigaa/public/componentes/busca_componentes.jsf",
            }
        }
    }


class SigaaComponentSearchResponse(BaseModel):
    status: SigaaSearchStatus
    source: SigaaSource = "sigaa_public_components"
    query: str
    component: SigaaComponent | None = None
    cached: bool = False
    warnings: list[str] = Field(default_factory=list)

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "found",
                "source": "sigaa_public_components",
                "query": "FGA0315",
                "component": {
                    "code": "FGA0315",
                    "name": "QUALIDADE DE SOFTWARE 1",
                    "type": "DISCIPLINA",
                    "unit": "FCTE",
                    "workload_hours": 60,
                    "syllabus": "",
                    "current_program": "",
                    "source_url": "https://sigaa.unb.br/sigaa/public/componentes/busca_componentes.jsf",
                },
                "cached": False,
                "warnings": [],
            }
        }
    }


class SigaaComponentAttachRequest(BaseModel):
    component: SigaaComponent

    model_config = {
        "json_schema_extra": {
            "example": {
                "component": {
                    "code": "FGA0315",
                    "name": "QUALIDADE DE SOFTWARE 1",
                    "type": "DISCIPLINA",
                    "unit": "FCTE",
                    "workload_hours": 60,
                    "syllabus": "",
                    "current_program": "",
                    "source_url": "https://sigaa.unb.br/sigaa/public/componentes/busca_componentes.jsf",
                }
            }
        }
    }


def _clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.strip().split())
    return cleaned or None


class ImportPreviewItem(BaseModel):
    preview_item_id: UUID
    item_type: ImportItemType
    status: ImportPreviewStatus
    selected: bool
    code: str | None = Field(default=None, max_length=30)
    name: str | None = Field(default=None, max_length=160)
    class_code: str | None = Field(default=None, max_length=30)
    schedule_code: str | None = Field(default=None, max_length=60)
    local: str | None = Field(default=None, max_length=120)
    source: ImportSource = "pdf_local"
    sigaa_lookup: SigaaLookupStatus = "not_queried"
    confidence: Literal["low", "medium", "high"]
    warnings: list[str] = Field(default_factory=list, max_length=10)

    model_config = {"extra": "forbid"}

    @field_validator("code", "name", "class_code", "schedule_code", "local", mode="before")
    @classmethod
    def clean_optional_fields(cls, value: Any) -> Any:
        if isinstance(value, str):
            return _clean_optional_text(value)
        return value


class ImportPreviewSummary(BaseModel):
    recognized_count: int = Field(..., ge=0)
    ambiguous_count: int = Field(..., ge=0)
    not_found_count: int = Field(..., ge=0)
    duplicate_count: int = Field(..., ge=0)
    activity_count: int = Field(..., ge=0)
    rejected_count: int = Field(..., ge=0)


class MatriculaPdfPreviewResponse(BaseModel):
    status: Literal["success", "no_items", "extraction_failed"]
    preview_id: UUID
    expires_at: datetime
    items: list[ImportPreviewItem]
    summary: ImportPreviewSummary
    warnings: list[str] = Field(default_factory=list)
    request_id: str


class ImportConfirmationItem(BaseModel):
    preview_item_id: UUID
    selected: bool = True
    code: str | None = Field(default=None, max_length=30)
    name: str | None = Field(default=None, max_length=160)
    class_code: str | None = Field(default=None, max_length=30)
    schedule_code: str | None = Field(default=None, max_length=60)
    local: str | None = Field(default=None, max_length=120)

    model_config = {"extra": "forbid"}

    @field_validator("code", "name", "class_code", "schedule_code", "local", mode="before")
    @classmethod
    def clean_fields(cls, value: Any) -> Any:
        if isinstance(value, str):
            return _clean_optional_text(value)
        return value


class MatriculaImportConfirmRequest(BaseModel):
    preview_id: UUID
    items: list[ImportConfirmationItem] = Field(..., max_length=50)

    model_config = {"extra": "forbid"}

    @field_validator("items")
    @classmethod
    def validate_unique_preview_items(
        cls, value: list[ImportConfirmationItem]
    ) -> list[ImportConfirmationItem]:
        ids = [str(item.preview_item_id) for item in value]
        if len(ids) != len(set(ids)):
            raise ValueError("Itens de pre-visualizacao nao podem se repetir.")
        return value


class ImportCreatedItem(BaseModel):
    preview_item_id: UUID
    discipline_id: UUID
    code: str
    name: str


class ImportRejectedItem(BaseModel):
    preview_item_id: UUID
    code: str | None = None
    name: str | None = None
    reason: str


class ImportSkippedItem(BaseModel):
    preview_item_id: UUID
    code: str | None = None
    name: str | None = None
    reason: str


class ImportConfirmSummary(BaseModel):
    created_count: int = Field(..., ge=0)
    duplicate_count: int = Field(..., ge=0)
    rejected_count: int = Field(..., ge=0)
    skipped_count: int = Field(..., ge=0)


class MatriculaImportConfirmResponse(BaseModel):
    status: ImportConfirmStatus
    preview_id: UUID
    created: list[ImportCreatedItem]
    duplicates: list[ImportRejectedItem]
    rejected: list[ImportRejectedItem]
    skipped: list[ImportSkippedItem]
    warnings: list[str] = Field(default_factory=list)
    summary: ImportConfirmSummary
    request_id: str

