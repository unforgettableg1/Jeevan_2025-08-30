from __future__ import annotations
from sqlalchemy.orm import declarative_base, Mapped, mapped_column
from sqlalchemy import Integer, String, DateTime, Text, Index
import datetime as dt
Base = declarative_base()

class StoreStatus(Base):
    __tablename__ = "store_status"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    store_id: Mapped[str] = mapped_column(String, index=True)
    timestamp_utc: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String)  # "active" or "inactive"
    __table_args__ = (
        Index("ix_store_ts", "store_id", "timestamp_utc"),
    )

class BusinessHours(Base):
    __tablename__ = "business_hours"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    store_id: Mapped[str] = mapped_column(String, index=True)
    day_of_week: Mapped[int] = mapped_column(Integer)  # 0=Mon ... 6=Sun
    start_time_local: Mapped[str] = mapped_column(String)  # "HH:MM:SS"
    end_time_local: Mapped[str] = mapped_column(String)

class StoreTimeZone(Base):
    __tablename__ = "store_timezone"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    store_id: Mapped[str] = mapped_column(String, index=True, unique=True)
    timezone_str: Mapped[str] = mapped_column(String)  # e.g., "America/Chicago"

class Report(Base):
    __tablename__ = "reports"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[str] = mapped_column(String, index=True, unique=True)
    status: Mapped[str] = mapped_column(String, default="Running")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    path: Mapped[str | None] = mapped_column(Text, nullable=True)
