from sqlalchemy import (
    Column, Integer, String, DateTime, Date, Float,
    ForeignKey, UniqueConstraint, Index
)
from bot.database import Base
from datetime import datetime, timezone


class UsedPhoto(Base):

    __tablename__ = "used_photos"

    id = Column(Integer, primary_key=True, index=True)

    file_unique_id = Column(
        String,
        unique=True,
        nullable=False,
        index=True
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    used_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )


class User(Base):

    __tablename__ = "users"

    id = Column(Integer, primary_key=True)

    telegram_id = Column(
        String,
        unique=True,
        index=True
    )

    phone = Column(
        String,
        unique=True,
        nullable=False,
        index=True
    )

    name = Column(String)

    face_registered = Column(Integer, default=0)


class Attendance(Base):

    __tablename__ = "attendance"

    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_user_date"),
        Index("ix_attendance_date", "date"),
        Index("ix_attendance_checkin", "check_in"),
    )

    id = Column(Integer, primary_key=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    check_in = Column(
        DateTime(timezone=True),
        nullable=False
    )

    check_out = Column(
        DateTime(timezone=True),
        nullable=True
    )

    lat = Column(Float)

    lon = Column(Float)

    date = Column(
        Date,
        default=lambda: datetime.now(timezone.utc).date(),
        nullable=False
    )
