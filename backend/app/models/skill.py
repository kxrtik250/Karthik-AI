import uuid
from typing import Optional
from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import TimestampedModel


class Skill(TimestampedModel):
    __tablename__ = "skills"

    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    proficiency: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Relationships
    profile: Mapped["Profile"] = relationship("Profile", back_populates="skills")

    __table_args__ = (
        UniqueConstraint("profile_id", "name", name="uq_skill_profile_name"),
    )
