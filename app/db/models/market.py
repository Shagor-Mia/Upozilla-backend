import enum
import uuid
from datetime import time

from sqlalchemy import ARRAY, Enum, Float, ForeignKey, String, Text, Time
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TenantMixin, TimestampMixin, UUIDPKMixin


class MarketType(str, enum.Enum):
    GENERAL = "general"
    CATTLE = "cattle"
    FISH = "fish"
    VEGETABLE = "vegetable"


class Market(Base, UUIDPKMixin, TenantMixin, TimestampMixin):
    __tablename__ = "markets"

    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id"), nullable=False, index=True
    )
    name_bn: Mapped[str] = mapped_column(String(255), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name_ar: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # What's generally traded/available here (e.g. "fish wholesale, Sat/Tue mornings") -
    # shown as a highlight on the market detail page, distinct from any one shop.
    description_bn: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    market_day: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    type: Mapped[MarketType] = mapped_column(Enum(MarketType, name="market_type"), nullable=False)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
