"""Router for Interactive Mock Interview and Technical Assessment Simulator."""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.interview import (
    AnswerEvaluation,
    CompleteInterviewRequest,
    EvaluateAnswerRequest,
    InterviewSummary,
    MockInterviewSession,
    MockInterviewStartRequest,
)
from app.services.interview_simulator import InterviewSimulatorService
from app.services.personal_context import get_projects_context

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/interview", tags=["interview"])


@router.post(
    "/start",
    response_model=MockInterviewSession,
    status_code=status.HTTP_200_OK,
    summary="Start a new interactive mock interview session",
)
async def start_mock_interview(
    request: MockInterviewStartRequest,
    db: AsyncSession = Depends(get_db),
):
    """Generate tailored interview questions grounded in candidate's skills and projects."""
    try:
        session = await InterviewSimulatorService.start_interview(db=db, request=request)
        return session
    except Exception as e:
        logger.error(f"Error starting mock interview session: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start mock interview session: {str(e)}",
        )


@router.post(
    "/evaluate-answer",
    response_model=AnswerEvaluation,
    status_code=status.HTTP_200_OK,
    summary="Evaluate a submitted interview answer",
)
async def evaluate_interview_answer(
    request: EvaluateAnswerRequest,
    db: AsyncSession = Depends(get_db),
):
    """Score the candidate's answer against rubrics and generate targeted feedback."""
    try:
        projects = await get_projects_context(db)
        evaluation = InterviewSimulatorService.evaluate_answer(
            request=request,
            projects=projects,
        )
        return evaluation
    except Exception as e:
        logger.error(f"Error evaluating interview answer: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to evaluate answer: {str(e)}",
        )


@router.post(
    "/complete",
    response_model=InterviewSummary,
    status_code=status.HTTP_200_OK,
    summary="Complete the mock interview and compute final readiness report",
)
async def complete_mock_interview(
    request: CompleteInterviewRequest,
):
    """Compute overall score, readiness level, and concrete action items."""
    try:
        summary = InterviewSimulatorService.generate_summary(
            session_id=request.session_id,
            company_name=request.company_name,
            role=request.role,
            round_type=request.round_type,
            evaluations=request.evaluations,
        )
        return summary
    except Exception as e:
        logger.error(f"Error completing mock interview: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate interview summary: {str(e)}",
        )
