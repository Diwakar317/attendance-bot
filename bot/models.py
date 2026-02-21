from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey
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

    used_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
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

    id = Column(Integer, primary_key=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    check_in = Column(
        DateTime(timezone=True)
    )

    check_out = Column(
        DateTime(timezone=True)
    )

    lat = Column(Float)

    lon = Column(Float)

    date = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True
    )
