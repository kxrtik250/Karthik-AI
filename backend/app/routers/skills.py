import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.skill import Skill
from app.schemas.skill import SkillCreate, SkillResponse, SkillUpdate
from app.services.profile_service import get_default_profile

router = APIRouter(prefix="/skills", tags=["skills"])


@router.get("", response_model=List[SkillResponse])
async def list_skills(
    category: Optional[str] = Query(None, description="Filter skills by category"),
    db: AsyncSession = Depends(get_db),
):
    """List all skills, optionally filtered by category."""
    query = select(Skill)
    if category:
        query = query.where(Skill.category == category)
    query = query.order_by(Skill.name.asc())

    result = await db.execute(query)
    return result.scalars().all()


@router.post("", response_model=SkillResponse, status_code=status.HTTP_201_CREATED)
async def create_skill(
    skill_in: SkillCreate, db: AsyncSession = Depends(get_db)
):
    """Add a new skill."""
    target_profile_id = skill_in.profile_id
    if not target_profile_id:
        profile = await get_default_profile(db)
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No profile exists. Please create a profile first before adding skills.",
            )
        target_profile_id = profile.id

    skill_data = skill_in.model_dump()
    skill_data["profile_id"] = target_profile_id

    skill = Skill(**skill_data)
    db.add(skill)
    try:
        await db.commit()
        await db.refresh(skill)
        return skill
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Skill '{skill_in.name}' already exists for this profile.",
        )


@router.put("/{skill_id}", response_model=SkillResponse)
async def update_skill(
    skill_id: uuid.UUID,
    skill_in: SkillUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a skill by ID."""
    result = await db.execute(select(Skill).where(Skill.id == skill_id))
    skill = result.scalars().first()
    if not skill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill with ID {skill_id} not found.",
        )

    update_data = skill_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(skill, field, value)

    try:
        await db.commit()
        await db.refresh(skill)
        return skill
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Skill name conflict with existing skill.",
        )


@router.delete("/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_skill(
    skill_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    """Delete a skill by ID."""
    result = await db.execute(select(Skill).where(Skill.id == skill_id))
    skill = result.scalars().first()
    if not skill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill with ID {skill_id} not found.",
        )

    await db.delete(skill)
    await db.commit()
    return None
