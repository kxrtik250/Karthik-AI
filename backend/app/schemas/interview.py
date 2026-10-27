"""Schemas for the Interactive Mock Interview & Technical Assessment Simulator."""

from typing import List, Optional
import uuid
from pydantic import BaseModel, Field


class MockInterviewStartRequest(BaseModel):
    """Request payload to initiate a new mock interview session."""

    drive_id: Optional[uuid.UUID] = Field(
        None,
        description="ID of the PlacementDrive to tailor the interview towards. If omitted, generates a general tech interview.",
    )
    round_type: str = Field(
        "technical",
        description="Type of round: 'technical', 'project_deep_dive', or 'hr_behavioral'",
    )
    difficulty: str = Field(
        "intermediate",
        description="Difficulty level: 'entry', 'intermediate', or 'advanced'",
    )


class InterviewQuestion(BaseModel):
    """A generated interview question tailored to the candidate and role."""

    question_id: str
    question_index: int
    round_type: str
    topic: str
    question_text: str
    context_hint: Optional[str] = None
    expected_key_points: List[str] = Field(default_factory=list)


class MockInterviewSession(BaseModel):
    """Active mock interview session state."""

    session_id: str
    company_name: str
    role: str
    round_type: str
    difficulty: str
    total_questions: int
    current_question_index: int
    questions: List[InterviewQuestion]


class EvaluateAnswerRequest(BaseModel):
    """Candidate's submitted answer alongside the target question context for evaluation."""

    session_id: str
    question_id: str
    answer_text: str = Field(..., min_length=5, description="Candidate's detailed verbal/written answer")
    question: InterviewQuestion
    total_questions: int = Field(3, ge=1)


class AnswerEvaluation(BaseModel):
    """Real-time feedback and rubric scoring on a candidate's answer."""

    session_id: str
    question_id: str
    question_index: int
    score: int = Field(..., ge=1, le=10, description="Score from 1 to 10")
    feedback_strengths: List[str] = Field(default_factory=list)
    feedback_improvements: List[str] = Field(default_factory=list)
    model_answer: str
    grounding_warning: Optional[str] = None
    is_final_question: bool = False


class CompleteInterviewRequest(BaseModel):
    """Payload to complete an interview session and compute final summary."""

    session_id: str
    company_name: str
    role: str
    round_type: str
    evaluations: List[AnswerEvaluation]


class InterviewSummary(BaseModel):
    """Aggregated assessment report with readiness level and actionable takeaways."""

    session_id: str
    company_name: str
    role: str
    round_type: str
    total_questions: int
    overall_score: float
    readiness_level: str  # "Ready", "Needs Practice", "Significant Preparation Needed"
    strengths_summary: List[str]
    improvement_areas: List[str]
    suggested_action_items: List[str]
