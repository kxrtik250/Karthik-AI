from decimal import Decimal
from typing import List, Optional
from sqlalchemy import Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import TimestampedModel


class Profile(TimestampedModel):
    __tablename__ = "profiles"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    university: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    degree: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    branch: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    graduation_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cgpa: Mapped[Optional[Decimal]] = mapped_column(Numeric(4, 2), nullable=True)
    career_goals: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    skills: Mapped[List["Skill"]] = relationship(
        "Skill", back_populates="profile", cascade="all, delete-orphan"
    )
    projects: Mapped[List["Project"]] = relationship(
        "Project", back_populates="profile", cascade="all, delete-orphan"
    )
    certifications: Mapped[List["Certification"]] = relationship(
        "Certification", back_populates="profile", cascade="all, delete-orphan"
    )
    placement_drives: Mapped[List["PlacementDrive"]] = relationship(
        "PlacementDrive", back_populates="profile", cascade="all, delete-orphan"
    )
