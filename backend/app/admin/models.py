import enum
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    TypeDecorator,
)
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base

if TYPE_CHECKING:
    from app.models.activity import Activity
    from app.models.athlete import Athlete


class _UTCDateTime(TypeDecorator):
    """DateTime that guarantees tz-aware UTC values on both bind and result.

    Postgres' ``TIMESTAMPTZ`` already returns tz-aware datetimes, but SQLite's
    ``DATETIME`` column strips ``tzinfo``. This decorator makes
    ``DateTime(timezone=True)`` behave the same on both dialects — critical for
    the admin-session expiry comparisons which rely on
    ``value > datetime.now(timezone.utc)``.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):  # noqa: ANN001
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value

    def process_result_value(self, value, dialect):  # noqa: ANN001
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value


# Shared alias used by every admin-module TIMESTAMPTZ column so the sqlite test
# harness gets tz-aware values identical to Postgres at runtime.
_TZ = _UTCDateTime(timezone=True)


class Thumb(str, enum.Enum):
    up = "up"
    down = "down"


class Admin(Base):
    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str | None] = mapped_column(String(100))
    disabled_at: Mapped[datetime | None] = mapped_column(_TZ)
    created_at: Mapped[datetime] = mapped_column(
        _TZ, server_default=func.now(), nullable=False
    )
    last_login_at: Mapped[datetime | None] = mapped_column(_TZ)

    sessions: Mapped[list["AdminSession"]] = relationship(
        back_populates="admin", cascade="all, delete-orphan"
    )


class AdminSession(Base):
    __tablename__ = "admin_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    admin_id: Mapped[int] = mapped_column(
        ForeignKey("admins.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(_TZ, nullable=False, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(_TZ)
    user_agent: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        _TZ, server_default=func.now(), nullable=False
    )

    admin: Mapped[Admin] = relationship(back_populates="sessions")


class PromptVersion(Base):
    __tablename__ = "prompt_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    version_number: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(String(50), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("admins.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(
        _TZ, server_default=func.now(), nullable=False
    )
    activated_at: Mapped[datetime | None] = mapped_column(_TZ)
    deactivated_at: Mapped[datetime | None] = mapped_column(_TZ)

    __table_args__ = (
        # PostgreSQL partial unique index: at most one active version.
        # Enforced in the Alembic migration (Task 3). Declared here for docs.
        Index(
            "ix_prompt_versions_unique_active",
            "is_active",
            unique=True,
            postgresql_where="is_active",
        ),
    )


class DebriefRun(Base):
    __tablename__ = "debrief_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    activity_id: Mapped[int] = mapped_column(
        ForeignKey("activities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    athlete_id: Mapped[int] = mapped_column(
        ForeignKey("athletes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    prompt_version_id: Mapped[int] = mapped_column(
        ForeignKey("prompt_versions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    model: Mapped[str] = mapped_column(String(50), nullable=False)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    tool_use_ok: Mapped[bool] = mapped_column(Boolean, nullable=False)
    fallback_used: Mapped[bool] = mapped_column(Boolean, nullable=False)
    # JSONB in Postgres, JSON in sqlite (for in-memory tests in conftest).
    raw_output: Mapped[dict | None] = mapped_column(JSONB().with_variant(JSON(), "sqlite"))
    created_at: Mapped[datetime] = mapped_column(
        _TZ, server_default=func.now(), nullable=False, index=True
    )


class DebriefRating(Base):
    __tablename__ = "debrief_ratings"

    debrief_run_id: Mapped[int] = mapped_column(
        ForeignKey("debrief_runs.id", ondelete="CASCADE"), primary_key=True
    )
    admin_id: Mapped[int | None] = mapped_column(
        ForeignKey("admins.id", ondelete="SET NULL"), nullable=True
    )
    thumb: Mapped[Thumb] = mapped_column(Enum(Thumb, name="thumb"), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        _TZ, server_default=func.now(), nullable=False
    )


class DebriefAutoFlag(Base):
    __tablename__ = "debrief_auto_flags"

    id: Mapped[int] = mapped_column(primary_key=True)
    debrief_run_id: Mapped[int] = mapped_column(
        ForeignKey("debrief_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rule_name: Mapped[str] = mapped_column(String(50), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        _TZ, server_default=func.now(), nullable=False
    )
