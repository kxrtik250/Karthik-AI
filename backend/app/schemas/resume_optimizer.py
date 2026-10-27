"""Schemas for the Resume Optimizer and ATS Tailoring Studio."""

from typing import List, Optional
import uuid
from pydantic import BaseModel, Field


class OptimizeResumeRequest(BaseModel):
    """Request payload to analyze and optimize a resume against a job description or drive."""

    drive_id: Optional[uuid.UUID] = Field(
        None,
        description="ID of the PlacementDrive to optimize against. If omitted, uses target_role and custom_jd_text.",
    )
    target_role: Optional[str] = Field(
        "Software Engineer",
        description="Target job title or role.",
    )
    custom_jd_text: Optional[str] = Field(
        None,
        description="Optional raw job description or skills text to evaluate against.",
    )


class KeywordMatchAnalysis(BaseModel):
    """Keyword gap analysis and ATS alignment breakdown."""

    matched_skills: List[str] = Field(default_factory=list)
    missing_skills: List[str] = Field(default_factory=list)
    ats_match_percentage: float = Field(..., ge=0.0, le=100.0)
    strengths: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)


class TailoredProjectBullet(BaseModel):
    """ATS-optimized bullet points for a candidate project."""

    project_name: str
    role: str
    technologies_used: List[str]
    bullet_points: List[str]


class OptimizedResumeResponse(BaseModel):
    """Complete resume optimization response with analysis and ATS-compliant text."""

    company_name: str
    target_role: str
    ats_analysis: KeywordMatchAnalysis
    tailored_projects: List[TailoredProjectBullet]
    full_resume_markdown: str
