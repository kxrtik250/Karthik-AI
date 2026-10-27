from decimal import Decimal
import uuid
from datetime import date
from typing import List, Optional
from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import TimestampedModel


class PlacementDrive(TimestampedModel):
    __tablename__ = "placement_drives"

    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="interested", nullable=False)
    deadline: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    compensation: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    employment_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    applied_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Placement Intelligence structured requirements
    min_cgpa: Mapped[Optional[Decimal]] = mapped_column(Numeric(4, 2), nullable=True)
    eligible_branches: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True)
    graduation_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    required_skills: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True)
    preferred_skills: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True)
    backlog_allowed: Mapped[Optional[bool]] = mapped_column(Boolean, default=False, nullable=True)
    selection_process: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True)
    tier: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Relationships
    profile: Mapped["Profile"] = relationship("Profile", back_populates="placement_drives")
    company: Mapped["Company"] = relationship("Company", back_populates="placement_drives")
