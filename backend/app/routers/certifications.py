import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.certification import Certification
from app.schemas.certification import (
    CertificationCreate,
    CertificationResponse,
    CertificationUpdate,
)
from app.services.profile_service import get_default_profile

router = APIRouter(prefix="/certifications", tags=["certifications"])


@router.get("", response_model=List[CertificationResponse])
async def list_certifications(db: AsyncSession = Depends(get_db)):
    """List all certifications."""
    query = select(Certification).order_by(Certification.issue_date.desc().nullslast())
    result = await db.execute(query)
    return result.scalars().all()


@router.post("", response_model=CertificationResponse, status_code=status.HTTP_201_CREATED)
async def create_certification(
    cert_in: CertificationCreate, db: AsyncSession = Depends(get_db)
):
    """Add a new certification."""
    target_profile_id = cert_in.profile_id
    if not target_profile_id:
        profile = await get_default_profile(db)
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No profile exists. Please create a profile first before adding certifications.",
            )
        target_profile_id = profile.id

    cert_data = cert_in.model_dump()
    cert_data["profile_id"] = target_profile_id

    cert = Certification(**cert_data)
    db.add(cert)
    await db.commit()
    await db.refresh(cert)
    return cert


@router.put("/{cert_id}", response_model=CertificationResponse)
async def update_certification(
    cert_id: uuid.UUID,
    cert_in: CertificationUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a certification by ID."""
    result = await db.execute(select(Certification).where(Certification.id == cert_id))
    cert = result.scalars().first()
    if not cert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Certification with ID {cert_id} not found.",
        )

    update_data = cert_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(cert, field, value)

    await db.commit()
    await db.refresh(cert)
    return cert


@router.delete("/{cert_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_certification(
    cert_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    """Delete a certification by ID."""
    result = await db.execute(select(Certification).where(Certification.id == cert_id))
    cert = result.scalars().first()
    if not cert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Certification with ID {cert_id} not found.",
        )

    await db.delete(cert)
    await db.commit()
    return None
