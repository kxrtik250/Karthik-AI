import uuid
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.company import CompanyResponse


class PlacementDriveBase(BaseModel):
    role: str = Field(..., max_length=200)
    status: str = Field(default="interested", max_length=30)
    deadline: Optional[date] = None
    compensation: Optional[str] = Field(None, max_length=100)
    employment_type: Optional[str] = Field(None, max_length=50)
    location: Optional[str] = Field(None, max_length=200)
    notes: Optional[str] = None
    applied_date: Optional[date] = None


class PlacementDriveCreate(PlacementDriveBase):
    profile_id: Optional[uuid.UUID] = None
    company_id: uuid.UUID


class PlacementDriveUpdate(BaseModel):
    role: Optional[str] = Field(None, max_length=200)
    company_id: Optional[uuid.UUID] = None
    status: Optional[str] = Field(None, max_length=30)
    deadline: Optional[date] = None
    compensation: Optional[str] = Field(None, max_length=100)
    employment_type: Optional[str] = Field(None, max_length=50)
    location: Optional[str] = Field(None, max_length=200)
    notes: Optional[str] = None
    applied_date: Optional[date] = None


class PlacementDriveResponse(PlacementDriveBase):
    id: uuid.UUID
    profile_id: uuid.UUID
    company_id: uuid.UUID
    company: Optional[CompanyResponse] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
