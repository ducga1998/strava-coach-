from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.athlete import Athlete


class StravaCredential(Base):
    __tablename__ = "strava_credentials"

    id: Mapped[int] = mapped_column(primary_key=True)
    athlete_id: Mapped[int] = mapped_column(
        ForeignKey("athletes.id"), nullable=False, unique=True, index=True
    )
    access_token_enc: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token_enc: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    refresh_failure_count: Mapped[int] = mapped_column(Integer, default=0)
    source_disconnected: Mapped[bool] = mapped_column(Boolean, default=False)
    webhook_subscription_id: Mapped[int | None] = mapped_column(Integer)

    athlete: Mapped[Athlete] = relationship(back_populates="credential")
