from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base
from app.models.activity import Activity
from app.models.athlete import Athlete


class ActivityMetrics(Base):
    __tablename__ = "activity_metrics"

    id: Mapped[int] = mapped_column(primary_key=True)
    activity_id: Mapped[int] = mapped_column(
        ForeignKey("activities.id"), nullable=False, unique=True, index=True
    )
    athlete_id: Mapped[int] = mapped_column(
        ForeignKey("athletes.id"), nullable=False, index=True
    )
    tss: Mapped[float | None] = mapped_column(Float)
    hr_tss: Mapped[float | None] = mapped_column(Float)
    gap_avg_sec_km: Mapped[float | None] = mapped_column(Float)
    ngp_sec_km: Mapped[float | None] = mapped_column(Float)
    hr_drift_pct: Mapped[float | None] = mapped_column(Float)
    aerobic_decoupling_pct: Mapped[float | None] = mapped_column(Float)
    zone_distribution: Mapped[dict[str, float] | None] = mapped_column(JSON)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    activity: Mapped[Activity] = relationship(back_populates="metrics")
    athlete: Mapped[Athlete] = relationship(back_populates="metrics")


class LoadHistory(Base):
    __tablename__ = "load_history"
    __table_args__ = (UniqueConstraint("athlete_id", "date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    athlete_id: Mapped[int] = mapped_column(
        ForeignKey("athletes.id"), nullable=False, index=True
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    ctl: Mapped[float] = mapped_column(Float, default=0.0)
    atl: Mapped[float] = mapped_column(Float, default=0.0)
    tsb: Mapped[float] = mapped_column(Float, default=0.0)
    acwr: Mapped[float] = mapped_column(Float, default=0.0)
    monotony: Mapped[float] = mapped_column(Float, default=0.0)
    strain: Mapped[float] = mapped_column(Float, default=0.0)

    athlete: Mapped[Athlete] = relationship(back_populates="load_history")
