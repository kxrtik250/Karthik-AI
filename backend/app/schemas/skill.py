import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class SkillBase(BaseModel):
    name: str = Field(..., max_length=100)
    category: Optional[str] = Field(None, max_length=50)
    proficiency: Optional[str] = Field(None, max_length=20)


class SkillCreate(SkillBase):
    profile_id: Optional[uuid.UUID] = None


class SkillUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    category: Optional[str] = Field(None, max_length=50)
    proficiency: Optional[str] = Field(None, max_length=20)


class SkillResponse(SkillBase):
    id: uuid.UUID
    profile_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
