"""Router for Resume Optimizer and ATS Tailoring Studio."""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.resume_optimizer import (
    OptimizedResumeResponse,
    OptimizeResumeRequest,
)
from app.services.resume_optimizer import ResumeOptimizerService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/resume", tags=["resume"])


@router.post(
    "/optimize",
    response_model=OptimizedResumeResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze ATS alignment and generate tailored, grounded resume content",
)
async def optimize_resume(
    request: OptimizeResumeRequest,
    db: AsyncSession = Depends(get_db),
):
    """Analyze keyword gaps and produce strictly-grounded resume bullet points and ATS markdown."""
    try:
        response = await ResumeOptimizerService.analyze_and_optimize(
            db=db,
            request=request,
        )
        return response
    except Exception as e:
        logger.error(f"Error optimizing resume: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to optimize resume: {str(e)}",
        )
