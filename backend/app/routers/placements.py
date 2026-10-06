import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.company import Company
from app.models.placement import PlacementDrive
from app.schemas.placement import (
    PlacementDriveCreate,
    PlacementDriveResponse,
    PlacementDriveUpdate,
)
from app.services.profile_service import get_default_profile

router = APIRouter(prefix="/placements", tags=["placements"])


@router.get("", response_model=List[PlacementDriveResponse])
async def list_placements(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter placement drives by status"),
    db: AsyncSession = Depends(get_db),
):
    """List all placement drives, optionally filtered by status."""
    query = (
        select(PlacementDrive)
        .options(selectinload(PlacementDrive.company))
        .order_by(PlacementDrive.deadline.asc().nullslast())
    )
    if status_filter:
        query = query.where(PlacementDrive.status == status_filter)

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{placement_id}", response_model=PlacementDriveResponse)
async def get_placement(
    placement_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    """Retrieve details of a single placement drive."""
    query = (
        select(PlacementDrive)
        .options(selectinload(PlacementDrive.company))
        .where(PlacementDrive.id == placement_id)
    )
    result = await db.execute(query)
    placement = result.scalars().first()
    if not placement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Placement drive with ID {placement_id} not found.",
        )
    return placement


@router.post("", response_model=PlacementDriveResponse, status_code=status.HTTP_201_CREATED)
async def create_placement(
    placement_in: PlacementDriveCreate, db: AsyncSession = Depends(get_db)
):
    """Add a new placement drive."""
    # Verify company exists
    company_check = await db.execute(select(Company).where(Company.id == placement_in.company_id))
    if not company_check.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company with ID {placement_in.company_id} does not exist.",
        )

    target_profile_id = placement_in.profile_id
    if not target_profile_id:
        profile = await get_default_profile(db)
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No profile exists. Please create a profile first before tracking placement drives.",
            )
        target_profile_id = profile.id

    placement_data = placement_in.model_dump()
    placement_data["profile_id"] = target_profile_id

    placement = PlacementDrive(**placement_data)
    db.add(placement)
    await db.commit()

    # Re-fetch with company eager-loaded
    query = (
        select(PlacementDrive)
        .options(selectinload(PlacementDrive.company))
        .where(PlacementDrive.id == placement.id)
    )
    result = await db.execute(query)
    return result.scalars().first()


@router.put("/{placement_id}", response_model=PlacementDriveResponse)
async def update_placement(
    placement_id: uuid.UUID,
    placement_in: PlacementDriveUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a placement drive by ID."""
    result = await db.execute(
        select(PlacementDrive).where(PlacementDrive.id == placement_id)
    )
    placement = result.scalars().first()
    if not placement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Placement drive with ID {placement_id} not found.",
        )

    if placement_in.company_id:
        company_check = await db.execute(
            select(Company).where(Company.id == placement_in.company_id)
        )
        if not company_check.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Company with ID {placement_in.company_id} does not exist.",
            )

    update_data = placement_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(placement, field, value)

    await db.commit()

    # Re-fetch with eager loaded company
    query = (
        select(PlacementDrive)
        .options(selectinload(PlacementDrive.company))
        .where(PlacementDrive.id == placement.id)
    )
    refreshed = await db.execute(query)
    return refreshed.scalars().first()


@router.delete("/{placement_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_placement(
    placement_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    """Delete a placement drive by ID."""
    result = await db.execute(
        select(PlacementDrive).where(PlacementDrive.id == placement_id)
    )
    placement = result.scalars().first()
    if not placement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Placement drive with ID {placement_id} not found.",
        )

    await db.delete(placement)
    await db.commit()
    return None
