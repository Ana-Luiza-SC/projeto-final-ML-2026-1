from __future__ import annotations

from datetime import date as Date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


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
