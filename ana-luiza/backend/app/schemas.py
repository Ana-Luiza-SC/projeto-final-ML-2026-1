from __future__ import annotations

from datetime import date as Date, datetime
from typing import Any
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


class DisciplineRead(DisciplineCreate):
    id: UUID
    created_at: datetime
    updated_at: datetime


class AttendanceUpdate(BaseModel):
    total_classes: int | None = Field(default=None, ge=0)
    missed_classes: int | None = Field(default=None, ge=0)
    total_class_hours: int | None = Field(default=None, ge=0)
    missed_class_hours: int | None = Field(default=None, ge=0)


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
