"""Модели SQLAlchemy: users и user_slice_state (docs/spec/shell-spec.md)."""
import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class SliceState(str, enum.Enum):
    Unavailable = "Unavailable"
    Available = "Available"
    InProgress = "InProgress"
    Done = "Done"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class UserSliceState(Base):
    __tablename__ = "user_slice_state"
    __table_args__ = (UniqueConstraint("user_id", "slice_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    slice_id: Mapped[str] = mapped_column(String(100))
    state: Mapped[SliceState] = mapped_column(
        Enum(SliceState, native_enum=False, length=20, validate_strings=True)
    )
    last_page: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
