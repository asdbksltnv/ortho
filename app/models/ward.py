import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import IdMixin, TimestampMixin


class Ward(Base, IdMixin, TimestampMixin):
    __tablename__ = "wards"

    name: Mapped[str] = mapped_column(String(200))
    rooms: Mapped[list["Room"]] = relationship(back_populates="ward", order_by="Room.name")


class Room(Base, IdMixin, TimestampMixin):
    __tablename__ = "rooms"

    ward_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("wards.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    floor: Mapped[int] = mapped_column(Integer, default=1)
    # Reserved for the future floor-plan view.
    position_x: Mapped[int | None] = mapped_column(Integer, nullable=True)
    position_y: Mapped[int | None] = mapped_column(Integer, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    kind: Mapped[str] = mapped_column(
        String(16), default="patient", server_default="patient"
    )  # patient | service | exit

    ward: Mapped[Ward] = relationship(back_populates="rooms")
    beds: Mapped[list["Bed"]] = relationship(back_populates="room", order_by="Bed.label")


class Bed(Base, IdMixin, TimestampMixin):
    __tablename__ = "beds"

    room_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("rooms.id"), index=True)
    label: Mapped[str] = mapped_column(String(50))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    room: Mapped[Room] = relationship(back_populates="beds")
