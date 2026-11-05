"""Only identity entities belong to NI-003; domain tables have later migrations."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, MetaData, String, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    metadata = MetaData(schema="app", naming_convention={
        "pk": "pk_%(table_name)s", "fk": "fk_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s", "ix": "ix_%(table_name)s_%(column_0_name)s",
    })


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("auth_provider = 'supabase'", name="auth_provider"),)

    id: Mapped[UUID] = mapped_column(primary_key=True)
    auth_provider: Mapped[str] = mapped_column(String(16), server_default=text("'supabase'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UserProfile(Base):
    __tablename__ = "user_profiles"
    __table_args__ = (
        CheckConstraint("app.is_valid_timezone(display_timezone)", name="timezone"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("app.users.id", ondelete="CASCADE"), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(80), server_default=text("''"))
    display_timezone: Mapped[str] = mapped_column(String(64), server_default=text("'UTC'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
