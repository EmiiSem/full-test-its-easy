from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CampaignRecord(Base):
    __tablename__ = "campaign_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    keitaro_campaign_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    alias: Mapped[str] = mapped_column(String(255))
    geos: Mapped[str] = mapped_column(String(255))
    offer_id: Mapped[int] = mapped_column(Integer)
    domain_id: Mapped[int] = mapped_column(Integer)
    group_id: Mapped[int] = mapped_column(Integer)
    traffic_source_id: Mapped[int] = mapped_column(Integer)
    google_stream_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    offer_stream_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class OfferCatalog(Base):
    __tablename__ = "offer_catalog"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    keitaro_offer_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(500))
    country: Mapped[str] = mapped_column(String(255), default="")


class StreamDraft(Base):
    __tablename__ = "stream_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    keitaro_campaign_id: Mapped[int] = mapped_column(Integer, index=True)
    keitaro_stream_id: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(255))
    position: Mapped[int] = mapped_column(Integer, default=0)
    role: Mapped[str] = mapped_column(String(32))
    dirty: Mapped[bool] = mapped_column(Boolean, default=False)
    published_offers: Mapped[str] = mapped_column(Text, default="[]")
    offers: Mapped[list["StreamOfferDraft"]] = relationship(
        back_populates="stream",
        cascade="all, delete-orphan",
    )

    __table_args__ = (UniqueConstraint("keitaro_campaign_id", "role"),)


class StreamOfferDraft(Base):
    __tablename__ = "stream_offer_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stream_draft_id: Mapped[int] = mapped_column(ForeignKey("stream_drafts.id"), index=True)
    keitaro_offer_id: Mapped[int] = mapped_column(Integer)
    share: Mapped[int] = mapped_column(Integer, default=0)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(16), default="active")
    stream: Mapped[StreamDraft] = relationship(back_populates="offers")

    __table_args__ = (UniqueConstraint("stream_draft_id", "keitaro_offer_id"),)
