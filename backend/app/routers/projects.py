import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate
from app.services.profile_service import get_default_profile

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=List[ProjectResponse])
async def list_projects(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter projects by status"),
    db: AsyncSession = Depends(get_db),
):
    """List all projects, optionally filtered by status."""
    query = select(Project)
    if status_filter:
        query = query.where(Project.status == status_filter)
    query = query.order_by(Project.created_at.desc())

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    """Retrieve details of a single project."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalars().first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID {project_id} not found.",
        )
    return project


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_in: ProjectCreate, db: AsyncSession = Depends(get_db)
):
    """Add a new project."""
    target_profile_id = project_in.profile_id
    if not target_profile_id:
        profile = await get_default_profile(db)
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No profile exists. Please create a profile first before adding projects.",
            )
        target_profile_id = profile.id

    # Case-insensitive duplicate check
    existing_project = await db.execute(
        select(Project).where(
            Project.profile_id == target_profile_id,
            func.lower(Project.name) == project_in.name.lower(),
        )
    )
    if existing_project.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Project '{project_in.name}' already exists in your profile.",
        )

    project_data = project_in.model_dump()
    project_data["profile_id"] = target_profile_id

    project = Project(**project_data)
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: uuid.UUID,
    project_in: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a project by ID."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalars().first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID {project_id} not found.",
        )

    update_data = project_in.model_dump(exclude_unset=True)
    if "name" in update_data and update_data["name"]:
        conflict = await db.execute(
            select(Project).where(
                Project.profile_id == project.profile_id,
                Project.id != project_id,
                func.lower(Project.name) == update_data["name"].lower(),
            )
        )
        if conflict.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Another project named '{update_data['name']}' already exists in your profile.",
            )

    new_start = update_data.get("start_date", project.start_date)
    new_end = update_data.get("end_date", project.end_date)
    if new_start and new_end and new_end < new_start:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project end_date cannot be earlier than start_date.",
        )

    for field, value in update_data.items():
        setattr(project, field, value)

    await db.commit()
    await db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    """Delete a project by ID."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalars().first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID {project_id} not found.",
        )

    await db.delete(project)
    await db.commit()
    return None
