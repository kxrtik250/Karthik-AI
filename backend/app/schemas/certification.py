import uuid
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class CertificationBase(BaseModel):
    name: str = Field(..., max_length=200)
    issuer: Optional[str] = Field(None, max_length=200)
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None
    credential_url: Optional[str] = Field(None, max_length=500)


class CertificationCreate(CertificationBase):
    profile_id: Optional[uuid.UUID] = None


class CertificationUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    issuer: Optional[str] = Field(None, max_length=200)
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None
    credential_url: Optional[str] = Field(None, max_length=500)


class CertificationResponse(CertificationBase):
    id: uuid.UUID
    profile_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
