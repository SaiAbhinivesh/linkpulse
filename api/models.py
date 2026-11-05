from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from api.db import Base


class Link(Base):
    __tablename__ = "links"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(16), unique=True)
    long_url: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DailyClick(Base):
    __tablename__ = "daily_clicks"

    code: Mapped[str] = mapped_column(
        String(16), ForeignKey("links.code", ondelete="CASCADE"), primary_key=True
    )
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0)


class ProcessedEvent(Base):
    __tablename__ = "processed_events"

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
