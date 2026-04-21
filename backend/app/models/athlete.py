import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base

if TYPE_CHECKING:
    from app.models.activity import Activity
    from app.models.credentials import StravaCredential
    from app.models.metrics import ActivityMetrics, LoadHistory
    from app.models.target import RaceTarget
    from app.models.training_plan import TrainingPlanEntry


class Units(str, enum.Enum):
    metric = "metric"
    imperial = "imperial"


class Athlete(Base):
    __tablename__ = "athletes"

    id: Mapped[int] = mapped_column(primary_key=True)
    strava_athlete_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, nullable=False, index=True
    )
    firstname: Mapped[str | None] = mapped_column(String(100))
    lastname: Mapped[str | None] = mapped_column(String(100))
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    city: Mapped[str | None] = mapped_column(String(100))
    country: Mapped[str | None] = mapped_column(String(100))
    plan_sheet_url: Mapped[str | None] = mapped_column(Text)
    plan_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    backfilled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    profile: Mapped["AthleteProfile | None"] = relationship(
        back_populates="athlete", cascade="all, delete-orphan"
    )
    credential: Mapped["StravaCredential | None"] = relationship(
        back_populates="athlete", cascade="all, delete-orphan"
    )
    activities: Mapped[list["Activity"]] = relationship(back_populates="athlete")
    targets: Mapped[list["RaceTarget"]] = relationship(back_populates="athlete")
    metrics: Mapped[list["ActivityMetrics"]] = relationship(back_populates="athlete")
    load_history: Mapped[list["LoadHistory"]] = relationship(back_populates="athlete")
    plan_entries: Mapped[list["TrainingPlanEntry"]] = relationship(
        back_populates="athlete", cascade="all, delete-orphan"
    )


class AthleteProfile(Base):
    __tablename__ = "athlete_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    athlete_id: Mapped[int] = mapped_column(
        ForeignKey("athletes.id"), nullable=False, unique=True, index=True
    )
    lthr: Mapped[int | None] = mapped_column()
    max_hr: Mapped[int | None] = mapped_column()
    threshold_pace_sec_km: Mapped[int | None] = mapped_column()
    weight_kg: Mapped[float | None] = mapped_column(Float)
    vo2max_estimate: Mapped[float | None] = mapped_column(Float)
    units: Mapped[Units] = mapped_column(Enum(Units), default=Units.metric)
    language: Mapped[str] = mapped_column(String(10), default="en")
    onboarding_complete: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    athlete: Mapped[Athlete] = relationship(back_populates="profile")
