from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.profile import Profile
from app.schemas.profile import ProfileCreate, ProfileResponse, ProfileUpdate
from app.services.profile_service import get_default_profile

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("", response_model=ProfileResponse)
async def get_profile(db: AsyncSession = Depends(get_db)):
    """Retrieve the personal profile."""
    profile = await get_default_profile(db)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found. Please create a profile first.",
        )
    return profile


@router.post("", response_model=ProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_profile(
    profile_in: ProfileCreate, db: AsyncSession = Depends(get_db)
):
    """Create the initial profile (only one profile is permitted)."""
    existing = await get_default_profile(db)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Profile already exists. Use PUT /api/profile to update.",
        )

    profile = Profile(**profile_in.model_dump())
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile


@router.put("", response_model=ProfileResponse)
async def update_profile(
    profile_in: ProfileUpdate, db: AsyncSession = Depends(get_db)
):
    """Update profile information."""
    profile = await get_default_profile(db)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found. Please create a profile first.",
        )

    update_data = profile_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(profile, field, value)

    await db.commit()
    await db.refresh(profile)
    return profile


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile(db: AsyncSession = Depends(get_db)):
    """Delete profile and all cascading records."""
    profile = await get_default_profile(db)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found.",
        )
    await db.delete(profile)
    await db.commit()
    return None
