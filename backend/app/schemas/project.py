import uuid
from datetime import date, datetime
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

VALID_PROJECT_STATUSES = {"planned", "in_progress", "completed", "archived"}

GENERIC_ROOT_DOMAINS = {
    "github.com",
    "www.github.com",
    "gitlab.com",
    "www.gitlab.com",
    "bitbucket.org",
    "www.bitbucket.org",
}


def validate_project_url(v: Optional[str]) -> Optional[str]:
    """Validate project URL: normalize backslashes, check scheme and domain, and reject bare generic roots."""
    if v is None:
        return None
    cleaned = v.strip().replace("\\", "/")
    if not cleaned:
        return None
    if not (cleaned.startswith("http://") or cleaned.startswith("https://")):
        cleaned = "https://" + cleaned
    from urllib.parse import urlparse
    parsed = urlparse(cleaned)
    if not parsed.netloc or "." not in parsed.netloc:
        raise ValueError("Project URL must have a valid domain (e.g. https://github.com/username/project).")
    netloc_lower = parsed.netloc.lower()
    path_cleaned = parsed.path.strip("/")
    if netloc_lower in GENERIC_ROOT_DOMAINS and not path_cleaned:
        raise ValueError(
            f"Generic link '{v}' is invalid. Please provide the specific repository or project URL (e.g. https://github.com/username/project)."
        )
    return cleaned


def validate_project_description(v: Optional[str]) -> Optional[str]:
    """Validate project description: trim whitespace and require at least 10 characters when provided."""
    if v is None:
        return None
    cleaned = v.strip()
    if not cleaned:
        return None
    if len(cleaned) < 10:
        raise ValueError("Project description must be at least 10 characters long to provide an informative summary.")
    return cleaned


class ProjectBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    technologies: Optional[List[str]] = None
    status: str = Field(default="planned", max_length=20)
    role: Optional[str] = Field(None, max_length=100)
    url: Optional[str] = Field(None, max_length=500)
    start_date: Optional[date] = None
    end_date: Optional[date] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Project name cannot be empty or whitespace.")
        return cleaned

    @field_validator("url")
    @classmethod
    def sanitize_base_url(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        cleaned = v.strip().replace("\\", "/")
        return cleaned if cleaned else None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        cleaned = v.strip().lower()
        if cleaned not in VALID_PROJECT_STATUSES:
            raise ValueError(f"Status must be one of: {', '.join(sorted(VALID_PROJECT_STATUSES))}")
        return cleaned

    @field_validator("technologies")
    @classmethod
    def clean_technologies(cls, v: Optional[List[Any]]) -> Optional[List[str]]:
        if v is None:
            return []
        cleaned_techs = []
        seen = set()
        for t in v:
            if isinstance(t, str):
                item = t.strip()
                if item and item.lower() not in seen:
                    cleaned_techs.append(item)
                    seen.add(item.lower())
        return cleaned_techs

    @model_validator(mode="after")
    def validate_dates(self) -> "ProjectBase":
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("Project end_date cannot be earlier than start_date.")
        return self


class ProjectCreate(ProjectBase):
    profile_id: Optional[uuid.UUID] = None

    @field_validator("url")
    @classmethod
    def validate_create_url(cls, v: Optional[str]) -> Optional[str]:
        return validate_project_url(v)

    @field_validator("description")
    @classmethod
    def validate_create_description(cls, v: Optional[str]) -> Optional[str]:
        return validate_project_description(v)


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    technologies: Optional[List[str]] = None
    status: Optional[str] = Field(None, max_length=20)
    role: Optional[str] = Field(None, max_length=100)
    url: Optional[str] = Field(None, max_length=500)
    start_date: Optional[date] = None
    end_date: Optional[date] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Project name cannot be empty or whitespace.")
        return cleaned

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        cleaned = v.strip().lower()
        if cleaned not in VALID_PROJECT_STATUSES:
            raise ValueError(f"Status must be one of: {', '.join(sorted(VALID_PROJECT_STATUSES))}")
        return cleaned

    @field_validator("technologies")
    @classmethod
    def clean_technologies(cls, v: Optional[List[Any]]) -> Optional[List[str]]:
        if v is None:
            return None
        cleaned_techs = []
        seen = set()
        for t in v:
            if isinstance(t, str):
                item = t.strip()
                if item and item.lower() not in seen:
                    cleaned_techs.append(item)
                    seen.add(item.lower())
        return cleaned_techs

    @field_validator("url")
    @classmethod
    def validate_update_url(cls, v: Optional[str]) -> Optional[str]:
        return validate_project_url(v)

    @field_validator("description")
    @classmethod
    def validate_update_description(cls, v: Optional[str]) -> Optional[str]:
        return validate_project_description(v)

    @model_validator(mode="after")
    def validate_dates(self) -> "ProjectUpdate":
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("Project end_date cannot be earlier than start_date.")
        return self


class ProjectResponse(ProjectBase):
    id: uuid.UUID
    profile_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
