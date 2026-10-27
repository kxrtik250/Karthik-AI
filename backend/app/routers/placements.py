import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.company import Company
from app.models.placement import PlacementDrive
from app.models.skill import Skill
from app.schemas.placement import (
    DriveComparison,
    EligibilityResult,
    ExtractAndCreateRequest,
    ExtractFromTextRequest,
    ExtractedDriveData,
    PlacementDriveCreate,
    PlacementDriveResponse,
    PlacementDriveUpdate,
    PreparationPlanResponse,
    PriorityEvaluation,
    SkillMatchResult,
)
from app.services.placement_intelligence import placement_intelligence_service
from app.services.placement_parser import placement_parser_service
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


@router.get("/open", response_model=List[PlacementDriveResponse])
async def list_open_placements(db: AsyncSession = Depends(get_db)):
    """List all currently active / open placement drives."""
    return await placement_intelligence_service.get_open_drives(db)


@router.get("/upcoming", response_model=List[PlacementDriveResponse])
async def list_upcoming_placements(
    days: int = Query(30, ge=1, le=365, description="Number of days forward to check"),
    db: AsyncSession = Depends(get_db),
):
    """List drives with approaching deadlines within the specified number of days."""
    return await placement_intelligence_service.get_upcoming_deadlines(db, days=days)


@router.get("/eligible", response_model=List[EligibilityResult])
async def list_eligible_placements(db: AsyncSession = Depends(get_db)):
    """Evaluate and list eligibility status across all open placement drives."""
    profile = await get_default_profile(db)
    drives = await placement_intelligence_service.get_open_drives(db)
    results = [
        placement_intelligence_service.evaluate_eligibility(profile, d)
        for d in drives
    ]
    return [r for r in results if r.status == "ELIGIBLE"]


@router.get("/priorities", response_model=List[PriorityEvaluation])
async def list_priority_opportunities(db: AsyncSession = Depends(get_db)):
    """Rank opportunities by transparent composite score (Eligibility + Skill Match + Deadline + Tier)."""
    profile = await get_default_profile(db)
    skills_res = await db.execute(select(Skill))
    user_skills = list(skills_res.scalars().all())
    return await placement_intelligence_service.rank_opportunities(db, profile, user_skills)


@router.post("/extract-from-text", response_model=ExtractedDriveData)
async def extract_placement_from_text(
    payload: ExtractFromTextRequest,
):
    """
    Parse an unstructured placement notice, campus circular, or Job Description (JD) text
    into structured drive criteria.
    """
    try:
        return placement_parser_service.extract_from_text(
            text=payload.text,
            source_filename=payload.source_filename,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse placement notice text: {str(e)}",
        )


@router.post("/extract-from-document/{document_id}", response_model=ExtractedDriveData)
async def extract_placement_from_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Extract structured placement criteria from an existing uploaded document (PDF, DOCX, TXT)
    stored in the knowledge documents repository.
    """
    try:
        return await placement_parser_service.extract_from_document(db, document_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error extracting placement drive from document: {str(e)}",
        )


@router.post("/extract-and-create", response_model=PlacementDriveResponse, status_code=status.HTTP_201_CREATED)
async def extract_and_create_placement(
    payload: ExtractAndCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Creates a placement drive directly from extracted data.
    Automatically checks and creates the company record if missing.
    """
    try:
        return await placement_parser_service.create_drive_from_extracted(
            db=db,
            drive_data=payload.drive_data,
            create_company_if_missing=payload.create_company_if_missing,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create placement drive from extracted data: {str(e)}",
        )


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


@router.get("/{placement_id}/eligibility", response_model=EligibilityResult)
async def get_placement_eligibility(
    placement_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    """Evaluate deterministic eligibility for a specific placement drive."""
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
    profile = await get_default_profile(db)
    return placement_intelligence_service.evaluate_eligibility(profile, placement)


@router.get("/{placement_id}/match", response_model=SkillMatchResult)
async def get_placement_skill_match(
    placement_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    """Calculate matching and missing skills for a specific placement drive."""
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
    skills_res = await db.execute(select(Skill))
    user_skills = list(skills_res.scalars().all())
    return placement_intelligence_service.calculate_skill_match(user_skills, placement)


@router.get("/{placement_id}/comparison", response_model=DriveComparison)
async def get_placement_comparison(
    placement_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    """Compare candidate profile, projects, and certifications against this placement drive."""
    comparison = await placement_intelligence_service.compare_profile_to_drive(db, placement_id)
    if not comparison:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Placement drive with ID {placement_id} not found.",
        )
    return comparison


@router.post("/{placement_id}/prepare", response_model=PreparationPlanResponse)
async def prepare_for_placement(
    placement_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    """Generate comprehensive interview preparation roadmap with document grounding."""
    plan = await placement_intelligence_service.generate_preparation_plan(db, placement_id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Placement drive with ID {placement_id} not found.",
        )
    return plan

