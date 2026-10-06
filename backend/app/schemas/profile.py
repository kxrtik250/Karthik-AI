import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class ProfileBase(BaseModel):
    name: str = Field(..., max_length=100)
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=20)
    university: Optional[str] = Field(None, max_length=200)
    degree: Optional[str] = Field(None, max_length=100)
    branch: Optional[str] = Field(None, max_length=100)
    graduation_year: Optional[int] = None
    cgpa: Optional[Decimal] = Field(None, ge=0.0, le=10.0)
    career_goals: Optional[str] = None
    summary: Optional[str] = None


class ProfileCreate(ProfileBase):
    pass


class ProfileUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=20)
    university: Optional[str] = Field(None, max_length=200)
    degree: Optional[str] = Field(None, max_length=100)
    branch: Optional[str] = Field(None, max_length=100)
    graduation_year: Optional[int] = None
    cgpa: Optional[Decimal] = Field(None, ge=0.0, le=10.0)
    career_goals: Optional[str] = None
    summary: Optional[str] = None


class ProfileResponse(ProfileBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
