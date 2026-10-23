from datetime import datetime

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import IdMixin, TimestampMixin, UTCDateTime


class User(Base, IdMixin, TimestampMixin):
    __tablename__ = "users"

    login: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32))
    telegram_chat_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # One-time code the user sends to the bot as «/start <code>» to link Telegram.
    telegram_link_code: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    telegram_link_expires: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    @property
    def telegram_linked(self) -> bool:
        return self.telegram_chat_id is not None
