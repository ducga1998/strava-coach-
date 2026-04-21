from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base

if TYPE_CHECKING:
    from app.models.athlete import Athlete


WORKOUT_TYPES = frozenset({
    "recovery", "easy", "long", "tempo", "interval",
    "hill", "race", "rest", "cross", "strength",
})


class TrainingPlanEntry(Base):
    __tablename__ = "training_plan_entries"
    __table_args__ = (
        UniqueConstraint(
            "athlete_id", "date", name="uq_training_plan_athlete_date"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    athlete_id: Mapped[int] = mapped_column(
        ForeignKey("athletes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    workout_type: Mapped[str] = mapped_column(String(20), nullable=False)
    planned_tss: Mapped[float | None] = mapped_column(Float)
    planned_duration_min: Mapped[int | None] = mapped_column(Integer)
    planned_distance_km: Mapped[float | None] = mapped_column(Float)
    planned_elevation_m: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(20), default="sheet_csv", nullable=False)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    athlete: Mapped["Athlete"] = relationship(back_populates="plan_entries")
