import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional
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

    # Placement Intelligence structured requirements
    min_cgpa: Optional[float] = None
    eligible_branches: Optional[List[str]] = None
    graduation_year: Optional[int] = None
    required_skills: Optional[List[str]] = None
    preferred_skills: Optional[List[str]] = None
    backlog_allowed: Optional[bool] = False
    selection_process: Optional[List[str]] = None
    tier: Optional[str] = Field(None, max_length=50)


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

    min_cgpa: Optional[float] = None
    eligible_branches: Optional[List[str]] = None
    graduation_year: Optional[int] = None
    required_skills: Optional[List[str]] = None
    preferred_skills: Optional[List[str]] = None
    backlog_allowed: Optional[bool] = None
    selection_process: Optional[List[str]] = None
    tier: Optional[str] = Field(None, max_length=50)


class PlacementDriveResponse(PlacementDriveBase):
    id: uuid.UUID
    profile_id: uuid.UUID
    company_id: uuid.UUID
    company: Optional[CompanyResponse] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Placement Intelligence schemas
class CriterionEvaluation(BaseModel):
    criterion: str
    status: str  # "eligible", "not_eligible", "unknown", "na"
    required: Optional[Any] = None
    actual: Optional[Any] = None
    message: str


class EligibilityResult(BaseModel):
    drive_id: Optional[uuid.UUID] = None
    company_name: str
    role: str
    status: str  # "ELIGIBLE", "NOT_ELIGIBLE", "UNKNOWN"
    is_eligible: Optional[bool] = None
    criteria: List[CriterionEvaluation] = []
    reasons: List[str] = []


class SkillMatchResult(BaseModel):
    drive_id: Optional[uuid.UUID] = None
    company_name: str
    role: str
    total_required_count: int
    matching_required: List[str] = []
    missing_required: List[str] = []
    required_match_percentage: float
    total_preferred_count: int
    matching_preferred: List[str] = []
    missing_preferred: List[str] = []
    preferred_match_percentage: float
    overall_match_percentage: float


class PriorityEvaluation(BaseModel):
    drive_id: uuid.UUID
    company_name: str
    role: str
    priority_level: str  # "HIGH", "MEDIUM", "LOW"
    composite_score: float
    eligibility_status: str
    skill_match_percentage: float
    deadline: Optional[date] = None
    days_until_deadline: Optional[int] = None
    compensation: Optional[str] = None
    tier: Optional[str] = None
    score_breakdown: List[str] = []


class DriveComparison(BaseModel):
    drive: PlacementDriveResponse
    eligibility: EligibilityResult
    skill_match: SkillMatchResult
    matching_projects: List[Dict[str, Any]] = []
    matching_certifications: List[Dict[str, Any]] = []


class PreparationPlanResponse(BaseModel):
    drive_id: uuid.UUID
    company_name: str
    role: str
    selection_process: Optional[List[str]] = None
    preparation_advice: str
    matching_projects: List[str] = []
    key_skills_to_prepare: List[str] = []
    relevant_document_sources: List[str] = []


# Placement Drive Ingestion & Parsing schemas
class ExtractedDriveData(BaseModel):
    company_name: str = Field(..., description="Recruiting company name")
    role: str = Field(..., description="Hiring job role or designation")
    status: str = Field(default="interested", max_length=30)
    deadline: Optional[date] = None
    compensation: Optional[str] = Field(None, max_length=100)
    employment_type: Optional[str] = Field(None, max_length=50)
    location: Optional[str] = Field(None, max_length=200)
    notes: Optional[str] = None

    # Placement Intelligence criteria
    min_cgpa: Optional[float] = None
    eligible_branches: Optional[List[str]] = None
    graduation_year: Optional[int] = None
    required_skills: Optional[List[str]] = None
    preferred_skills: Optional[List[str]] = None
    backlog_allowed: Optional[bool] = False
    selection_process: Optional[List[str]] = None
    tier: Optional[str] = Field(None, max_length=50)

    # Ingestion metadata
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)
    source_document_id: Optional[uuid.UUID] = None
    source_filename: Optional[str] = None


class ExtractFromTextRequest(BaseModel):
    text: str = Field(..., min_length=10, description="Placement circular or job description text")
    source_filename: Optional[str] = Field(None, description="Optional name of the document or source")


class ExtractAndCreateRequest(BaseModel):
    drive_data: ExtractedDriveData
    create_company_if_missing: bool = True


