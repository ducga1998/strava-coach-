import enum
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base
from app.models.athlete import Athlete


class Priority(str, enum.Enum):
    A = "A"
    B = "B"
    C = "C"


class RaceTarget(Base):
    __tablename__ = "race_targets"

    id: Mapped[int] = mapped_column(primary_key=True)
    athlete_id: Mapped[int] = mapped_column(
        ForeignKey("athletes.id"), nullable=False, index=True
    )
    race_name: Mapped[str] = mapped_column(String(255), nullable=False)
    race_date: Mapped[date] = mapped_column(Date, nullable=False)
    distance_km: Mapped[float] = mapped_column(Float, nullable=False)
    elevation_gain_m: Mapped[float | None] = mapped_column(Float)
    goal_time_sec: Mapped[int | None] = mapped_column()
    priority: Mapped[Priority] = mapped_column(Enum(Priority), default=Priority.A)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    athlete: Mapped[Athlete] = relationship(back_populates="targets")
