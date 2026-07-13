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
    schedule_slots: list[dict[str, str]] = Field(default_factory=list)
    schedule_display: str | None = None
    schedule_source: Literal["receipt_table", "sigaa_tooltip", "decoded_code", "unresolved"] = "unresolved"
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
    schedule_slots: list[dict[str, str]] = Field(default_factory=list)
    schedule_display: str | None = None
    schedule_source: Literal["receipt_table", "sigaa_tooltip", "decoded_code", "unresolved"] = "unresolved"


class AssessmentCreate(BaseModel):
    name: str = Field(..., min_length=1)
    weight: float | None = Field(default=None, gt=0, le=100)
    grade: float | None = Field(default=None, ge=0, le=10)
    date: Date | None = None
    topics: list[str] = Field(default_factory=list)
    notes: str | None = Field(default=None, max_length=500)
    source: Literal["manual", "course_plan"] = "manual"
    status: Literal["planned", "completed", "cancelled"] = "planned"
    code: str | None = None
    evaluation_group_code: str | None = None
    evaluation_group_name: str | None = None
    group_final_weight: float | None = Field(default=None, gt=0, le=100)
    group_weight: float | None = Field(default=None, gt=0, le=100)
    requires_date: bool = False
    description: str | None = Field(default=None, max_length=500)
    source_page: int | None = Field(default=None, ge=1)

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


    @model_validator(mode="after")
    def validate_status_grade(self) -> "AssessmentCreate":
        if "status" not in self.model_fields_set and self.grade is not None:
            self.status = "completed"
        if self.status == "planned" and self.grade is not None:
            raise ValueError("Avaliação planejada não pode ter nota.")
        if self.status == "completed" and self.grade is None:
            raise ValueError("Avaliação realizada exige nota.")
        return self

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
    group_results: list[dict[str, Any]] = Field(default_factory=list)

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


class StudyAction(BaseModel):
    strategy_id: Literal["retrieval_practice", "spaced_practice", "interleaving", "concrete_examples", "self_explanation"]
    action: str = Field(..., min_length=1)
    topic: str | None = None
    estimated_minutes: int | None = Field(default=None, gt=0)
    reason: str = Field(..., min_length=1)
    evidence: str = Field(..., min_length=1)
    reference_ids: list[str] = Field(default_factory=list)


class StudyStrategyReference(BaseModel):
    id: str
    short_citation: str
    title: str
    url: str


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
    execution_mode: Literal["llm", "deterministic_fallback"]
    fallback_reason: str | None = None
    model: str | None = None
    latency_ms: float = Field(..., ge=0)
    warnings: list[str] = Field(default_factory=list)
    used_evidence: list[str] = Field(default_factory=list)
    influencing_assessments: list[str] = Field(default_factory=list)
    study_actions: list[StudyAction] = Field(default_factory=list)
    strategy_references: list[StudyStrategyReference] = Field(default_factory=list)

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


class AssistantRecentMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=1000)


class DisciplineAssistantRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    recent_messages: list[AssistantRecentMessage] = Field(default_factory=list, max_length=8)
    user_goal: str | None = Field(default=None, max_length=500)


class DisciplineAssistantResponse(BaseModel):
    status: Literal["success"] = "success"
    source: Literal["gemini", "fallback"]
    execution_mode: Literal["llm", "deterministic_fallback"]
    fallback_reason: str | None = None
    model: str | None = None
    answer: str = Field(..., min_length=1)
    evidence: list[str] = Field(default_factory=list)
    suggested_actions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


ContextualAssistantIntent = Literal[
    "general",
    "explain_priority",
    "recommend_window",
    "recommend_methods",
    "propose_study_block",
    "explain_capacity_shortage",
]
ContextualAssistantActionType = Literal[
    "navigate_to_discipline",
    "navigate_to_planning",
    "navigate_to_calendar_date",
    "explain_priority",
    "explain_capacity_shortage",
    "recommend_study_methods",
    "create_study_block",
    "modify_unconfirmed_plan",
]


class ContextualAssistantRequest(BaseModel):
    route: Literal[
        "home",
        "disciplines",
        "discipline",
        "study-plan",
        "calendar",
        "matricula-import",
    ]
    message: str = Field(..., min_length=1, max_length=1000)
    intent: ContextualAssistantIntent = "general"
    selected_discipline_id: UUID | None = None
    selected_week_start: Date | None = None
    selected_event_id: str | None = Field(default=None, max_length=160)
    selected_priority_id: str | None = Field(default=None, max_length=160)

    model_config = {"extra": "forbid"}

    @field_validator("message")
    @classmethod
    def clean_message(cls, value: str) -> str:
        cleaned = " ".join(value.strip().split())
        if "<" in cleaned or ">" in cleaned:
            raise ValueError("HTML ou conteúdo executável não é permitido.")
        return cleaned


class ContextualAssistantEvidence(BaseModel):
    source_type: Literal[
        "assessment",
        "calendar",
        "discipline",
        "priority",
        "capacity",
        "study_method_catalog",
    ]
    source_id: str | None = None
    summary: str


class ContextualAssistantAction(BaseModel):
    action_id: UUID | None = None
    type: ContextualAssistantActionType
    label: str
    payload: dict[str, Any] = Field(default_factory=dict)
    requires_confirmation: bool


class ContextualAssistantResponse(BaseModel):
    message: str
    execution_mode: Literal["deterministic_fallback", "llm"] = (
        "deterministic_fallback"
    )
    evidence: list[ContextualAssistantEvidence] = Field(default_factory=list)
    suggested_actions: list[ContextualAssistantAction] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    study_method_catalog_version: str | None = None


class ContextualActionConfirmationResponse(BaseModel):
    action_id: UUID
    action_type: ContextualAssistantActionType
    status: Literal["executed", "already_executed"]
    result: dict[str, Any]


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


class WeeklyAvailabilityWindow(BaseModel):
    weekday: StudyPlanDay
    start_time: str = Field(..., pattern=r"^\d{2}:\d{2}$")
    end_time: str = Field(..., pattern=r"^\d{2}:\d{2}$")
    available: bool = True

    model_config = {"extra": "forbid"}

    @field_validator("start_time", "end_time")
    @classmethod
    def validate_time_format(cls, value: str) -> str:
        _parse_hhmm(value)
        return value

    @model_validator(mode="after")
    def validate_time_order(self) -> "WeeklyAvailabilityWindow":
        if _minutes(self.start_time) >= _minutes(self.end_time):
            raise ValueError("Inicio da janela deve ser menor que o fim.")
        return self


class WeeklyAvailabilityRequest(BaseModel):
    week_start: Date
    timezone: Literal["America/Sao_Paulo"] = "America/Sao_Paulo"
    windows: list[WeeklyAvailabilityWindow] = Field(..., min_length=1, max_length=28)

    model_config = {"extra": "forbid"}


class AvailabilitySummaryResponse(BaseModel):
    timezone: Literal["America/Sao_Paulo"] = "America/Sao_Paulo"
    daily_totals: dict[StudyPlanDay, int]
    weekly_total_minutes: int
    normalized_windows: list[WeeklyAvailabilityWindow]
    warnings: list[str] = Field(default_factory=list)


class WeeklyPlanPreviewRequest(WeeklyAvailabilityRequest):
    excluded_discipline_ids: list[UUID] = Field(default_factory=list, max_length=20)
    objective_text: str | None = Field(default=None, max_length=500)


class WeeklyPriorityEvidence(BaseModel):
    source_type: Literal["assessment", "content", "discipline", "calendar", "simulation"]
    source_id: str | None = None
    summary: str


class WeeklyPriorityResult(BaseModel):
    priority_item_id: str
    discipline_id: UUID
    discipline_code: str | None = None
    discipline_name: str
    content_id: UUID | None = None
    assessment_id: UUID | None = None
    assessment_name: str | None = None
    deadline_at: datetime | None = None
    priority_score: int = Field(..., ge=0, le=100)
    priority_band: Literal["low", "medium", "high"]
    evidence_used: list[WeeklyPriorityEvidence] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    reason: str
    estimated_demand_minutes: int | None = Field(default=None, ge=0)
    demand_confidence: float = Field(default=0, ge=0, le=1)
    demand_reason: str


class PlannedStudyBlockPreview(BaseModel):
    temporary_id: str
    discipline_id: UUID
    discipline_code: str | None = None
    discipline_name: str
    content_id: UUID | None = None
    assessment_id: UUID | None = None
    title: str
    reason: str
    priority_score: int = Field(..., ge=0, le=100)
    priority_band: Literal["low", "medium", "high"]
    start_at: datetime
    end_at: datetime
    state: Literal["planned"] = "planned"


CapacityReason = Literal[
    "fully_allocated",
    "partially_allocated",
    "insufficient_conflict_free_capacity",
    "no_window_before_deadline",
    "fragments_below_minimum",
    "deadline_expired",
    "demand_unknown",
    "excluded_by_user",
    "conflict_introduced_after_preview",
]


class CapacityBlockingEvent(BaseModel):
    event_id: UUID
    title: str
    blocked_minutes: int = Field(..., ge=0)


class PriorityCapacityAnalysis(BaseModel):
    priority_item_id: str
    discipline_id: UUID
    discipline_name: str
    requested_minutes: int | None = Field(default=None, ge=0)
    allocated_minutes: int = Field(..., ge=0)
    remaining_minutes: int | None = Field(default=None, ge=0)
    available_minutes_before_deadline: int = Field(..., ge=0)
    usable_minutes_before_deadline: int = Field(..., ge=0)
    blocked_minutes: int = Field(..., ge=0)
    allocated_to_higher_priorities_minutes: int = Field(..., ge=0)
    minimum_useful_block_minutes: int = Field(..., gt=0)
    deadline_at: datetime | None = None
    reason_code: CapacityReason
    reason: str
    blocking_events: list[CapacityBlockingEvent] = Field(default_factory=list)


class WeeklyPlanPreviewResponse(BaseModel):
    study_plan_id: UUID
    week_start: Date
    timezone: Literal["America/Sao_Paulo"]
    availability: AvailabilitySummaryResponse
    ranked_priorities: list[WeeklyPriorityResult]
    planned_blocks: list[PlannedStudyBlockPreview]
    unallocated_priorities: list[WeeklyPriorityResult] = Field(default_factory=list)
    capacity_analysis: list[PriorityCapacityAnalysis] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    algorithm_version: str
    generated_at: datetime


class WeeklyPlanConfirmResponse(BaseModel):
    study_plan_id: UUID
    created_events: list["AcademicEventRead"]
    skipped_blocks: list[dict[str, str]] = Field(default_factory=list)
    created_count: int = Field(..., ge=0)


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
    scheduled_date: Date | None = None
    content_node_id: UUID | None = None
    assessment_id: UUID | None = None
    assessment_name: str | None = None
    assessment_date: Date | None = None
    association_origin: Literal["direct", "inherited"] | None = None
    evidence: str | None = None


class StudyPlanMetrics(BaseModel):
    requested_minutes: int
    allocated_minutes: int
    unallocated_minutes: int
    session_count: int
    discipline_count: int


class StudyPlanPriorityInfluence(BaseModel):
    discipline_id: UUID
    assessment_id: UUID | None = None
    assessment_name: str
    assessment_date: Date
    weight: float | None = None
    bonus: int = Field(..., ge=1, le=2)
    reason: str


class StudyPlanResponse(BaseModel):
    status: Literal["success"]
    source: StudyPlanSource
    plan: list[StudyPlanSession] = Field(..., min_length=1)
    summary: str
    warnings: list[str] = Field(default_factory=list)
    metrics: StudyPlanMetrics
    priority_influences: list[StudyPlanPriorityInfluence] = Field(default_factory=list)
    request_id: str
    fallback_reason: str | None = None


class SigaaComponent(BaseModel):
    code: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    type: str | None = None
    unit: str | None = None
    workload_hours: int | None = Field(default=None, ge=0)
    syllabus: str | None = None
    current_program: str | None = None
    prerequisites: str | None = None
    theoretical_workload_hours: int | None = Field(default=None, ge=0)
    practical_workload_hours: int | None = Field(default=None, ge=0)
    details_processed: bool = False
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
                "prerequisites": None,
                "theoretical_workload_hours": 30,
                "practical_workload_hours": 30,
                "details_processed": True,
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
    schedule_slots: list[dict[str, str]] = Field(default_factory=list)
    schedule_display: str | None = Field(default=None, max_length=500)
    schedule_source: Literal["receipt_table", "sigaa_tooltip", "decoded_code", "unresolved"] = "unresolved"
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
    schedule_slots: list[dict[str, str]] = Field(default_factory=list)
    schedule_display: str | None = Field(default=None, max_length=500)
    schedule_source: Literal["receipt_table", "sigaa_tooltip", "decoded_code", "unresolved"] = "unresolved"
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


CalendarEventType = Literal["exam", "assignment", "presentation", "activity", "deadline", "study_block", "other"]
CalendarEventSource = Literal["manual", "assessment", "course_plan", "study_plan", "system"]
CalendarEventStatus = Literal["draft", "confirmed", "cancelled", "completed"]
RecurrenceFrequency = Literal["none", "daily", "weekly", "biweekly", "monthly", "yearly", "custom_weekly"]
RecurrenceEndMode = Literal["never", "on_date", "after_count"]


class RecurrenceEnd(BaseModel):
    mode: RecurrenceEndMode = "never"
    until: Date | None = None
    count: int | None = Field(default=None, ge=1, le=500)

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def validate_end(self) -> "RecurrenceEnd":
        if self.mode == "on_date" and self.until is None:
            raise ValueError("Data final e obrigatoria para recorrencia com termino por data.")
        if self.mode == "after_count" and self.count is None:
            raise ValueError("Quantidade de ocorrencias e obrigatoria para recorrencia por contagem.")
        return self


class RecurrenceRule(BaseModel):
    frequency: RecurrenceFrequency = "none"
    interval: int = Field(default=1, ge=1, le=12)
    weekdays: list[StudyPlanDay] = Field(default_factory=list, max_length=7)
    ends: RecurrenceEnd = Field(default_factory=RecurrenceEnd)
    rrule: str | None = None

    model_config = {"extra": "forbid"}

    @field_validator("weekdays")
    @classmethod
    def validate_unique_weekdays(cls, value: list[StudyPlanDay]) -> list[StudyPlanDay]:
        if len(value) != len(set(value)):
            raise ValueError("Dias da recorrencia nao podem se repetir.")
        return value

    @model_validator(mode="after")
    def validate_rule(self) -> "RecurrenceRule":
        if self.frequency in {"weekly", "biweekly", "custom_weekly"} and not self.weekdays:
            raise ValueError("Recorrencia semanal exige ao menos um dia da semana.")
        if self.frequency == "biweekly":
            self.interval = 2
        if self.frequency == "none":
            self.weekdays = []
            self.interval = 1
        return self


def _sanitize_calendar_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.strip().split())
    if not cleaned:
        return None
    if "<" in cleaned or ">" in cleaned:
        raise ValueError("HTML ou conteúdo executável não é permitido.")
    return cleaned


class AcademicEventBase(BaseModel):
    discipline_id: UUID | None = None
    assessment_id: UUID | None = None
    title: str = Field(..., min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    event_type: CalendarEventType = "other"
    start_at: datetime
    end_at: datetime | None = None
    all_day: bool = False
    timezone: str = "America/Sao_Paulo"
    weight: float | None = Field(default=None, gt=0, le=100)
    status: CalendarEventStatus = "confirmed"
    source: CalendarEventSource = "manual"
    source_evidence: str | None = Field(default=None, max_length=500)
    extraction_confidence: float | None = Field(default=None, ge=0, le=1)
    source_fingerprint: str | None = Field(default=None, max_length=180)
    recurrence: RecurrenceRule | None = None
    study_plan_id: UUID | None = None
    content_id: UUID | None = None
    priority_score: int | None = Field(default=None, ge=0, le=100)
    priority_band: Literal["low", "medium", "high"] | None = None
    priority_reason: str | None = Field(default=None, max_length=500)
    algorithm_version: str | None = Field(default=None, max_length=80)
    generated_at: datetime | None = None

    model_config = {"extra": "forbid"}

    @field_validator("title", "description", "source_evidence", "source_fingerprint")
    @classmethod
    def sanitize_text(cls, value):
        return _sanitize_calendar_text(value)

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        if value != "America/Sao_Paulo":
            raise ValueError("Timezone suportado neste MVP: America/Sao_Paulo.")
        return value

    @model_validator(mode="after")
    def validate_interval(self) -> "AcademicEventBase":
        if self.end_at is not None and self.end_at <= self.start_at:
            raise ValueError("Fim do evento deve ser posterior ao início.")
        return self


class AcademicEventCreate(AcademicEventBase):
    discipline_id: UUID | None = None
    assessment_id: UUID | None = None
    status: CalendarEventStatus = "confirmed"
    source: Literal["manual"] = "manual"


class AcademicEventUpdate(BaseModel):
    discipline_id: UUID | None = None
    title: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    event_type: CalendarEventType | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    all_day: bool | None = None
    timezone: str | None = None
    weight: float | None = Field(default=None, gt=0, le=100)
    status: CalendarEventStatus | None = None
    recurrence: RecurrenceRule | None = None

    model_config = {"extra": "forbid"}

    @field_validator("title", "description")
    @classmethod
    def sanitize_update_text(cls, value):
        return _sanitize_calendar_text(value)


class AcademicEventRead(AcademicEventBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    discipline_code: str | None = None
    discipline_name: str | None = None
    recurrence_series_id: UUID | None = None
    occurrence_id: str | None = None
    occurrence_date: Date | None = None


class CalendarDraftEvent(BaseModel):
    temporary_id: str = Field(..., min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    title: str = Field(..., min_length=1, max_length=160)
    event_type: CalendarEventType
    start_at: datetime | None = None
    end_at: datetime | None = None
    all_day: bool = True
    timezone: str = "America/Sao_Paulo"
    weight: float | None = Field(default=None, gt=0, le=100)
    description: str | None = Field(default=None, max_length=1000)
    source_evidence: str = Field(..., min_length=1, max_length=500)
    confidence: float = Field(..., ge=0, le=1)
    warnings: list[str] = Field(default_factory=list, max_length=10)
    ambiguous: bool = False
    source_fingerprint: str | None = Field(default=None, max_length=180)

    model_config = {"extra": "forbid"}

    @field_validator("title", "description", "source_evidence", "source_fingerprint")
    @classmethod
    def sanitize_draft_text(cls, value):
        return _sanitize_calendar_text(value)

    @field_validator("warnings")
    @classmethod
    def sanitize_draft_warnings(cls, values: list[str]) -> list[str]:
        clean = []
        for item in values:
            value = _sanitize_calendar_text(str(item))
            if value:
                clean.append(value[:200])
        return clean


class CalendarExtractionPreviewResponse(BaseModel):
    preview_id: UUID
    expires_at: datetime
    draft_events: list[CalendarDraftEvent]
    warnings: list[str] = Field(default_factory=list)
    source: Literal["course_plan", "fallback"]
    used_fallback: bool = False
    fallback_reason: Literal["missing_course_plan", "missing_llm", "invalid_response", "timeout", "provider_unavailable", "no_explicit_events"] | None = None
    latency_ms: float = Field(..., ge=0)


class CalendarPreviewConfirmRequest(BaseModel):
    preview_id: UUID
    draft_events: list[CalendarDraftEvent] = Field(..., max_length=100)

    model_config = {"extra": "forbid"}


class CalendarPreviewConfirmResponse(BaseModel):
    created_events: list[AcademicEventRead]
    skipped_events: list[dict[str, str]] = Field(default_factory=list)
    created_count: int = Field(..., ge=0)



class AssessmentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    weight: float | None = Field(default=None, gt=0, le=100)
    grade: float | None = Field(default=None, ge=0, le=10)
    date: Date | None = None
    topics: list[str] | None = None
    notes: str | None = Field(default=None, max_length=500)
    status: Literal["planned", "completed", "cancelled"] | None = None
    code: str | None = None
    evaluation_group_code: str | None = None
    evaluation_group_name: str | None = None
    group_final_weight: float | None = Field(default=None, gt=0, le=100)
    group_weight: float | None = Field(default=None, gt=0, le=100)
    requires_date: bool | None = None
    description: str | None = Field(default=None, max_length=500)
    source_page: int | None = Field(default=None, ge=1)


class AssessmentCompleteRequest(BaseModel):
    grade: float = Field(..., ge=0, le=10)
    date: Date | None = None
    topics: list[str] | None = None
    notes: str | None = Field(default=None, max_length=500)


class AbsenceCreate(BaseModel):
    date: Date
    class_hours: float = Field(..., gt=0)
    notes: str | None = Field(default=None, max_length=300)


class AbsenceRead(AbsenceCreate):
    id: UUID
    discipline_id: UUID


class AttendanceSummary(BaseModel):
    workload_class_hours: float | None
    missed_class_hours: float
    absence_limit_class_hours: float | None
    remaining_class_hours: float | None
    frequency: float | None
    absence_percentage: float | None
    risk_level: Literal["low", "medium", "high", "unknown"]
    warnings: list[str]


class CoursePlanEvaluationItem(BaseModel):
    code: str | None = None
    name: str
    group_weight: float | None = Field(default=None, gt=0, le=100)
    date: Date | None = None
    requires_date: bool = True
    description: str | None = None
    topics: list[str] = Field(default_factory=list)
    source_page: int | None = Field(default=None, ge=1)
    status: Literal["recognized", "requires_review"] = "recognized"


class CoursePlanEvaluationGroup(BaseModel):
    code: str
    name: str
    final_weight: float = Field(..., gt=0, le=100)
    items: list[CoursePlanEvaluationItem] = Field(default_factory=list)


class CoursePlanAssessment(BaseModel):
    name: str
    code: str | None = None
    date: Date | None = None
    weight: float | None = Field(default=None, gt=0, le=100)
    group_code: str | None = None
    group_name: str | None = None
    group_final_weight: float | None = Field(default=None, gt=0, le=100)
    group_weight: float | None = Field(default=None, gt=0, le=100)
    requires_date: bool = False
    description: str | None = None
    associated_content: str | None = None
    source_page: int | None = Field(default=None, ge=1)
    topics: list[str] = Field(default_factory=list)
    status: Literal["recognized", "requires_review"] = "recognized"


class CoursePlanData(BaseModel):
    code: str | None = None
    name: str | None = None
    semester: str | None = None
    workload_hours: float | None = Field(default=None, gt=0)
    term_weeks: int | None = Field(default=None, gt=0, le=30)
    objectives: list[str] = Field(default_factory=list)
    contents: list[str] = Field(default_factory=list)
    schedule: list[str] = Field(default_factory=list)
    evaluation_groups: list[CoursePlanEvaluationGroup] = Field(default_factory=list)
    assessments: list[CoursePlanAssessment] = Field(default_factory=list)
    bibliography: list[str] = Field(default_factory=list)


class CoursePlanPreviewResponse(BaseModel):
    preview_id: UUID
    expires_at: datetime
    data: CoursePlanData
    warnings: list[str]
    source: Literal["gemini", "local_parser"] = "local_parser"
    model: str | None = None
    fallback_reason: Literal["missing_api_key", "provider_timeout", "provider_error", "unsupported_model", "invalid_json", "invalid_structured_response", "schema_validation_error", "empty_extracted_text", "internal_error"] | None = None
    evaluation_group_count: int = 0
    evaluation_component_count: int = 0


class CoursePlanConfirmRequest(BaseModel):
    preview_id: UUID
    data: CoursePlanData

ContentDifficulty = Literal["low", "medium", "high"]
ContentStatus = Literal["not_started", "in_progress", "studied", "reviewed"]

class ContentNodeCreate(BaseModel):
    parent_id: UUID | None = None
    title: str = Field(..., min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    difficulty: ContentDifficulty | None = None
    status: ContentStatus = "not_started"
    model_config = {"extra": "forbid"}
    @field_validator("title", "description")
    @classmethod
    def reject_executable_text(cls, value):
        if value is not None and ("<" in value or ">" in value): raise ValueError("HTML ou conteúdo executável não é permitido.")
        if isinstance(value, str) and not value.strip(): raise ValueError("O texto não pode ser vazio.")
        return value.strip() if isinstance(value, str) else value

class ContentNodeUpdate(BaseModel):
    parent_id: UUID | None = None
    title: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    difficulty: ContentDifficulty | None = None
    status: ContentStatus | None = None
    model_config = {"extra": "forbid"}
    @field_validator("title", "description")
    @classmethod
    def reject_executable_text(cls, value):
        if value is not None and ("<" in value or ">" in value): raise ValueError("HTML ou conteúdo executável não é permitido.")
        if isinstance(value, str) and not value.strip(): raise ValueError("O texto não pode ser vazio.")
        return value.strip() if isinstance(value, str) else value

class ContentNodeRead(BaseModel):
    id: UUID
    discipline_id: UUID
    parent_id: UUID | None = None
    title: str
    description: str | None = None
    difficulty: ContentDifficulty | None = None
    status: ContentStatus
    created_at: datetime
    children: list["ContentNodeRead"] = Field(default_factory=list)

class ContentMoveRequest(BaseModel):
    parent_id: UUID | None = None

class AssessmentContentSelection(BaseModel):
    content_node_id: UUID
    include_descendants: bool = False

class AssessmentContentAssociationRequest(BaseModel):
    selections: list[AssessmentContentSelection] = Field(default_factory=list, max_length=100)

class ResolvedContentNode(BaseModel):
    id: UUID
    discipline_id: UUID
    parent_id: UUID | None = None
    title: str
    description: str | None = None
    difficulty: ContentDifficulty | None = None
    status: ContentStatus
    created_at: datetime
    association_origin: Literal["direct", "inherited"]
    selected_ancestor_id: UUID | None = None

class AssessmentContentAssociationResponse(BaseModel):
    assessment_id: UUID
    selections: list[AssessmentContentSelection]
    resolved_nodes: list[ResolvedContentNode]


class ContentDraftNode(BaseModel):
    temporary_id: str = Field(..., min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    parent_temporary_id: str | None = Field(default=None, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    title: str = Field(..., min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    source_evidence: str = Field(..., min_length=1, max_length=300)
    confidence: float = Field(..., ge=0, le=1)
    warnings: list[str] = Field(default_factory=list, max_length=10)
    model_config = {"extra": "forbid"}

    @field_validator("title", "description", "source_evidence")
    @classmethod
    def sanitize_text(cls, value):
        if value is None:
            return value
        clean = " ".join(value.split())
        if not clean:
            raise ValueError("O texto não pode ser vazio.")
        if "<" in clean or ">" in clean:
            raise ValueError("HTML ou conteúdo executável não é permitido.")
        return clean

    @field_validator("warnings")
    @classmethod
    def sanitize_warnings(cls, values):
        clean = []
        for value in values:
            normalized = " ".join(value.split())[:200]
            if normalized and "<" not in normalized and ">" not in normalized:
                clean.append(normalized)
        return clean


class ContentExtractionPreviewResponse(BaseModel):
    preview_id: UUID
    expires_at: datetime
    draft_nodes: list[ContentDraftNode]
    warnings: list[str]
    source: Literal["gemini", "local_fallback"]
    model: str | None = None
    used_fallback: bool
    fallback_reason: Literal["missing_api_key", "timeout", "unavailable", "invalid_response", "no_explicit_content"] | None = None
    latency_ms: float = Field(..., ge=0)


class ContentExtractionConfirmRequest(BaseModel):
    preview_id: UUID
    draft_nodes: list[ContentDraftNode] = Field(..., max_length=100)


class ContentExtractionConfirmResponse(BaseModel):
    created_nodes: list[ContentNodeRead]
    created_count: int = Field(..., ge=0)
