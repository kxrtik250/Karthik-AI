from typing import List, Optional
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import TimestampedModel


class Company(TimestampedModel):
    __tablename__ = "companies"

    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    industry: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    website: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    placement_drives: Mapped[List["PlacementDrive"]] = relationship(
        "PlacementDrive", back_populates="company", cascade="all, delete-orphan"
    )
