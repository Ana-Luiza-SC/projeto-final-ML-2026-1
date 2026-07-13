from __future__ import annotations
import json, os
from contextvars import ContextVar
from datetime import date, datetime, timezone
from pathlib import Path
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def utc_now():
    return datetime.now(timezone.utc)


BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE_URL = f"sqlite:///{BACKEND_DIR / 'data' / 'estudaunb.db'}"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class Owned:
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    payload: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class DisciplineRecord(Owned, Base):
    __tablename__ = "disciplines"


class AssessmentRecord(Owned, Base):
    __tablename__ = "assessments"
    discipline_id: Mapped[str] = mapped_column(String(64), index=True)


class AcademicEventRecord(Owned, Base):
    __tablename__ = "academic_events"
    discipline_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    assessment_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)


class AbsenceRecord(Owned, Base):
    __tablename__ = "absences"
    discipline_id: Mapped[str] = mapped_column(String(64), index=True)


class CoursePlanRecord(Owned, Base):
    __tablename__ = "course_plans"


class ContentNodeRecord(Owned, Base):
    __tablename__ = "content_nodes"
    discipline_id: Mapped[str] = mapped_column(String(64), index=True)


class AssessmentContentLinkRecord(Owned, Base):
    __tablename__ = "assessment_content_links"


class CatalogComponent(Base):
    __tablename__ = "catalog_components"
    code: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(300))
    workload_hours: Mapped[int | None] = mapped_column(Integer)
    academic_unit: Mapped[str | None] = mapped_column(String(300))
    syllabus: Mapped[str] = mapped_column(Text, default="")
    current_program: Mapped[str] = mapped_column(Text, default="")
    source_url: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(80), default="sigaa_public_components")
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class ComplexityAnalysisRecord(Owned, Base):
    __tablename__ = "complexity_analyses"


_opts = (
    {"connect_args": {"check_same_thread": False}}
    if DATABASE_URL.startswith("sqlite")
    else {}
)
engine = create_engine(DATABASE_URL, pool_pre_ping=True, **_opts)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
current_user_id = ContextVar("current_user_id", default="local-test-user")


def init_database():
    if DATABASE_URL.startswith("sqlite:///") and not DATABASE_URL.endswith(":memory:"):
        Path(DATABASE_URL.removeprefix("sqlite:///")).expanduser().parent.mkdir(
            parents=True, exist_ok=True
        )
    Base.metadata.create_all(engine)


def encode_payload(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        default=lambda x: x.isoformat() if isinstance(x, (date, datetime)) else str(x),
    )


def decode_payload(value):
    return json.loads(value)
