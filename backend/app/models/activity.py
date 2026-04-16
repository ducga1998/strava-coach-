from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base
from app.models.athlete import Athlete

if TYPE_CHECKING:
    from app.models.metrics import ActivityMetrics


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(primary_key=True)
    strava_activity_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, nullable=False, index=True
    )
    athlete_id: Mapped[int] = mapped_column(
        ForeignKey("athletes.id"), nullable=False, index=True
    )
    name: Mapped[str | None] = mapped_column(String(255))
    sport_type: Mapped[str | None] = mapped_column(String(50))
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    elapsed_time_sec: Mapped[int | None] = mapped_column()
    moving_time_sec: Mapped[int | None] = mapped_column()
    distance_m: Mapped[float | None] = mapped_column(Float)
    total_elevation_gain_m: Mapped[float | None] = mapped_column(Float)
    average_heartrate: Mapped[float | None] = mapped_column(Float)
    max_heartrate: Mapped[float | None] = mapped_column(Float)
    streams_raw: Mapped[dict[str, object] | None] = mapped_column(JSON)
    debrief: Mapped[dict[str, object] | None] = mapped_column(JSON)
    excluded_from_load: Mapped[bool] = mapped_column(Boolean, default=False)
    skipped_reason: Mapped[str | None] = mapped_column(String(100))
    processing_status: Mapped[str] = mapped_column(String(50), default="pending")
    retry_count: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    athlete: Mapped[Athlete] = relationship(back_populates="activities")
    metrics: Mapped["ActivityMetrics | None"] = relationship(
        back_populates="activity", cascade="all, delete-orphan"
    )
