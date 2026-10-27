"""Service for conducting interactive mock interviews and evaluating technical assessments.

Generates tailored interview questions grounded in candidate's real profile, skills, and
projects, and evaluates answers against deterministic rubrics with actionable feedback.
"""

from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.placement import PlacementDrive
from app.schemas.interview import (
    AnswerEvaluation,
    EvaluateAnswerRequest,
    InterviewQuestion,
    InterviewSummary,
    MockInterviewSession,
    MockInterviewStartRequest,
)
from app.services.personal_context import (
    get_profile_context,
    get_projects_context,
    get_skills_context,
)


class InterviewSimulatorService:
    """Orchestrates mock interview session lifecycle, question generation, and evaluation."""

    @classmethod
    async def start_interview(
        cls,
        db: AsyncSession,
        request: MockInterviewStartRequest,
    ) -> MockInterviewSession:
        """Initialize a new mock interview session tailored to the candidate and optional drive."""
        company_name = "General Technology"
        role = "Software Engineer"
        drive_skills: List[str] = []

        # 1. Fetch placement drive if specified
        if request.drive_id:
            drive_res = await db.execute(
                select(PlacementDrive)
                .options(selectinload(PlacementDrive.company))
                .where(PlacementDrive.id == request.drive_id)
            )
            drive = drive_res.scalar_one_or_none()
            if drive:
                role = drive.role
                if drive.company:
                    company_name = drive.company.name
                if drive.required_skills:
                    drive_skills = [str(s).strip() for s in drive.required_skills]

        # 2. Fetch candidate's profile, skills, and projects
        profile = await get_profile_context(db)
        skills = await get_skills_context(db)
        projects = await get_projects_context(db)

        candidate_skills = [s["name"] for s in skills]
        candidate_project_names = [p["name"] for p in projects]

        # 3. Generate tailored questions based on round type
        questions = cls._generate_questions(
            round_type=request.round_type,
            difficulty=request.difficulty,
            company_name=company_name,
            role=role,
            candidate_skills=candidate_skills,
            drive_skills=drive_skills,
            projects=projects,
        )

        session_id = str(uuid.uuid4())

        return MockInterviewSession(
            session_id=session_id,
            company_name=company_name,
            role=role,
            round_type=request.round_type,
            difficulty=request.difficulty,
            total_questions=len(questions),
            current_question_index=0,
            questions=questions,
        )

    @classmethod
    def _generate_questions(
        cls,
        round_type: str,
        difficulty: str,
        company_name: str,
        role: str,
        candidate_skills: List[str],
        drive_skills: List[str],
        projects: List[Dict[str, Any]],
    ) -> List[InterviewQuestion]:
        """Generate structured interview questions grounded in candidate experience."""
        questions: List[InterviewQuestion] = []
        q_idx = 1

        if round_type == "project_deep_dive":
            if projects:
                primary_proj = projects[0]
                p_name = primary_proj.get("name", "Project")
                p_role = primary_proj.get("role", "Developer")
                p_tech = ", ".join(primary_proj.get("technologies", [])) or "Python and SQL"
                p_desc = primary_proj.get("description", "A software application")

                # Q1: Architecture & Technology Choices
                questions.append(
                    InterviewQuestion(
                        question_id=f"q_{q_idx}",
                        question_index=q_idx,
                        round_type=round_type,
                        topic="Architecture & Tech Stack",
                        question_text=(
                            f"Walk me through the architecture of your '{p_name}' project. "
                            f"Why did you choose {p_tech} as your stack, and how did your role as {p_role} shape the project structure?"
                        ),
                        context_hint=f"Focus on your documented role and technologies for {p_name}.",
                        expected_key_points=[
                            "Separation of concerns (frontend vs backend vs database)",
                            "Rationale for chosen technologies",
                            "Data flow between client, server, and database",
                            "Personal contributions and engineering decisions",
                        ],
                    )
                )
                q_idx += 1

                # Q2: Data Management & Schema Design
                questions.append(
                    InterviewQuestion(
                        question_id=f"q_{q_idx}",
                        question_index=q_idx,
                        round_type=round_type,
                        topic="Data Management & Modeling",
                        question_text=(
                            f"In '{p_name}', how did you structure your database to manage student records? "
                            f"How did you prevent data anomalies and ensure efficient queries as records grow?"
                        ),
                        context_hint="Explain relational schema design, primary/foreign keys, indexing, and input validation.",
                        expected_key_points=[
                            "Relational schema structure and entity relationships",
                            "Data validation rules to ensure record consistency",
                            "Database indexing on frequently searched fields",
                            "CRUD operation error handling",
                        ],
                    )
                )
                q_idx += 1

                # Q3: Technical Challenges & Debugging
                questions.append(
                    InterviewQuestion(
                        question_id=f"q_{q_idx}",
                        question_index=q_idx,
                        round_type=round_type,
                        topic="Technical Troubleshooting & Version Control",
                        question_text=(
                            f"Describe a challenging technical obstacle you encountered while developing '{p_name}'. "
                            f"How did you isolate the problem, and how did you use Git or debugging tools to resolve it safely?"
                        ),
                        context_hint="Explain your root cause analysis, branch management, and verification process.",
                        expected_key_points=[
                            "Clear identification of the technical bottleneck or bug",
                            "Structured debugging methodology and log inspection",
                            "Git feature branching and clean commit history",
                            "Testing the fix to prevent regressions",
                        ],
                    )
                )
            else:
                # Fallback if no projects stored yet
                questions.append(
                    InterviewQuestion(
                        question_id=f"q_{q_idx}",
                        question_index=q_idx,
                        round_type=round_type,
                        topic="System Design & Project Scoping",
                        question_text=(
                            "If you were tasked with designing a Student Management application from scratch using Python and SQL, "
                            "how would you architect the API layer, database schema, and validation rules?"
                        ),
                        context_hint="Outline clean architecture principles and REST conventions.",
                        expected_key_points=[
                            "Layered architecture (controller, service, repository)",
                            "Relational schema design with normalized tables",
                            "Input validation and defensive error responses",
                        ],
                    )
                )

        elif round_type == "hr_behavioral":
            # Q1: Working under pressure / deadlined project
            questions.append(
                InterviewQuestion(
                    question_id=f"q_{q_idx}",
                    question_index=q_idx,
                    round_type=round_type,
                    topic="Time Management & Priorities",
                    question_text=(
                        f"Tell me about a time you had to balance academic deadlines, technical coursework, and interview preparation for companies like {company_name}. "
                        "How did you prioritize your commitments, and what was the outcome?"
                    ),
                    context_hint="Use the STAR method: Situation, Task, Action taken, and measurable Result.",
                    expected_key_points=[
                        "Situation: Description of conflicting priorities and tight deadline",
                        "Task: What needed to be delivered and standard of quality required",
                        "Action: Prioritization strategy, time allocation, breaking tasks into milestones",
                        "Result: Successful completion and key lesson learned",
                    ],
                )
            )
            q_idx += 1

            # Q2: Handling technical conflict or feedback
            questions.append(
                InterviewQuestion(
                    question_id=f"q_{q_idx}",
                    question_index=q_idx,
                    round_type=round_type,
                    topic="Collaboration & Constructive Feedback",
                    question_text=(
                        "Describe a situation where a peer or reviewer suggested a significant change to your code or design approach. "
                        "How did you evaluate their feedback and arrive at the best solution for the project?"
                    ),
                    context_hint="Highlight objectivity, technical trade-off evaluation, and team collaboration.",
                    expected_key_points=[
                        "Receptive, professional attitude towards constructive feedback",
                        "Evaluating trade-offs objectively based on maintainability and performance",
                        "Collaborative discussion with data or benchmarks",
                        "Positive team outcome and mutual learning",
                    ],
                )
            )
            q_idx += 1

            # Q3: Growth & learning agility
            questions.append(
                InterviewQuestion(
                    question_id=f"q_{q_idx}",
                    question_index=q_idx,
                    round_type=round_type,
                    topic="Adaptability & Learning Agility",
                    question_text=(
                        f"At {company_name}, technologies and business requirements evolve rapidly. "
                        "Can you share an example of a new technical skill or framework you had to learn quickly on your own? What was your approach?"
                    ),
                    context_hint="Detail your self-directed learning workflow and hands-on practice.",
                    expected_key_points=[
                        "Self-motivated learning initiative",
                        "Practical hands-on methodology (building a proof of concept or project)",
                        "Consulting official documentation and community best practices",
                        "Applying the acquired skill to solve a real problem",
                    ],
                )
            )

        else:
            # Default: Technical & Problem Solving
            # Q1: Python & Programming Foundations
            questions.append(
                InterviewQuestion(
                    question_id=f"q_{q_idx}",
                    question_index=q_idx,
                    round_type="technical",
                    topic="Core Python & Memory Management",
                    question_text=(
                        f"In the context of the {role} position at {company_name}, how do Python's memory management "
                        "and garbage collection mechanisms work? What are the key differences between shallow and deep copying?"
                    ),
                    context_hint="Explain reference counting, cyclic garbage collector, and object mutability.",
                    expected_key_points=[
                        "Reference counting as primary mechanism",
                        "Generational cyclic garbage collector for circular references",
                        "Shallow copy duplicates reference; deep copy recursively duplicates objects",
                        "Performance implications in large data structures",
                    ],
                )
            )
            q_idx += 1

            # Q2: SQL & Database Optimization
            questions.append(
                InterviewQuestion(
                    question_id=f"q_{q_idx}",
                    question_index=q_idx,
                    round_type="technical",
                    topic="SQL & Relational Query Optimization",
                    question_text=(
                        "When designing backend APIs that query a relational database like PostgreSQL, "
                        "what strategies do you employ to prevent N+1 query problems and optimize index usage on multi-column filters?"
                    ),
                    context_hint="Discuss eager loading (JOINs/selectin), composite indexes, and EXPLAIN ANALYZE.",
                    expected_key_points=[
                        "Using JOINs or eager loading (e.g. selectinload) to prevent N+1 overhead",
                        "B-tree index fundamentals and composite index column ordering",
                        "Execution plan inspection using EXPLAIN ANALYZE",
                        "Database connection pooling and transaction scoping",
                    ],
                )
            )
            q_idx += 1

            # Q3: REST API Design & Error Handling
            questions.append(
                InterviewQuestion(
                    question_id=f"q_{q_idx}",
                    question_index=q_idx,
                    round_type="technical",
                    topic="RESTful Architecture & Robust Error Handling",
                    question_text=(
                        "How do you design idempotent REST API endpoints, and how do you ensure consistent, "
                        "informative error responses when handling unexpected server exceptions or input validation failures?"
                    ),
                    context_hint="Explain HTTP methods idempotency (GET/PUT/DELETE vs POST), standard status codes, and exception handlers.",
                    expected_key_points=[
                        "Idempotency semantics (PUT and DELETE are idempotent; POST typically is not)",
                        "Semantic HTTP status codes (400, 404, 409, 422, 500)",
                        "Global exception middleware and structured error envelopes",
                        "Preventing internal stack traces from leaking to clients",
                    ],
                )
            )

        return questions

    @classmethod
    def evaluate_answer(
        cls,
        request: EvaluateAnswerRequest,
        projects: Optional[List[Dict[str, Any]]] = None,
    ) -> AnswerEvaluation:
        """Evaluate a candidate's submitted answer using rubric-based scoring."""
        text = request.answer_text.strip()
        words = text.split()
        word_count = len(words)
        lower_text = text.lower()
        question = request.question
        total_questions = request.total_questions

        score = 5  # Baseline
        strengths: List[str] = []
        improvements: List[str] = []
        grounding_warning: Optional[str] = None

        # 1. Depth & Length Check
        if word_count < 15:
            score = max(1, score - 3)
            improvements.append("The response is too brief. Provide a more detailed explanation with concrete examples.")
        elif word_count >= 50:
            score += 1
            strengths.append("Good elaboration and comprehensive explanations provided.")

        if word_count >= 100:
            score = min(10, score + 1)
            strengths.append("Demonstrated high depth and clarity with thorough context.")

        # 2. Key Point Matching
        matched_points = 0
        for pt in question.expected_key_points:
            # Check keywords from key points
            tokens = [w.lower() for w in pt.split() if len(w) > 3]
            if any(tok in lower_text for tok in tokens):
                matched_points += 1

        coverage_pct = matched_points / max(1, len(question.expected_key_points))
        if coverage_pct >= 0.75:
            score = min(10, score + 2)
            strengths.append("Directly addressed the core principles and key concepts evaluated by the question.")
        elif coverage_pct >= 0.4:
            score = min(10, score + 1)
            strengths.append("Addressed several foundational aspects of the problem.")
        else:
            score = max(2, score - 1)
            improvements.append(
                f"Missing critical coverage on key technical topics: {', '.join(question.expected_key_points[:2])}."
            )

        # 3. Grounding checks for Project Deep Dive
        if question.round_type == "project_deep_dive":
            # Check if answer introduces completely unsupported claims
            unsupported_buzzwords = ["blockchain", "attendance tracking", "course registration", "microservices architecture"]
            hallucinated_claims = [b for b in unsupported_buzzwords if b in lower_text]
            if hallucinated_claims:
                grounding_warning = (
                    f"Note: You mentioned '{', '.join(hallucinated_claims)}' which is not documented in your "
                    "project record. In real interviews, stick strictly to what you built to avoid aggressive follow-up questions."
                )
                score = max(3, score - 1)

            # Check if mentioned candidate's real tech stack
            if any(t in lower_text for t in ["python", "sql", "javascript", "js", "git"]):
                strengths.append("Correctly grounded the response in your verified technology stack.")
            else:
                improvements.append("Explicitly reference your core tools (Python, SQL, JavaScript, Git) to demonstrate hands-on implementation.")

        # 4. Behavioral STAR method check for HR
        if question.round_type == "hr_behavioral":
            star_elements = {
                "situation / context": any(k in lower_text for k in ["when", "during", "project", "college", "time", "scenario"]),
                "action / initiative": any(k in lower_text for k in ["i decided", "i took", "i organized", "i built", "i focused", "i implemented", "i communicated"]),
                "outcome / result": any(k in lower_text for k in ["result", "outcome", "learned", "delivered", "achieved", "completed", "improved"]),
            }
            missing_star = [k for k, v in star_elements.items() if not v]
            if not missing_star:
                score = min(10, score + 1)
                strengths.append("Followed a structured STAR narrative with clear context, personal actions, and measurable outcomes.")
            else:
                improvements.append(f"Structure your story more clearly using STAR. Be sure to articulate your {', '.join(missing_star)}.")

        # Clamp final score
        final_score = max(1, min(10, score))

        # Default fallbacks if empty
        if not strengths:
            strengths.append("Attempted the question and maintained a professional tone.")
        if not improvements:
            improvements.append("Include more granular metric results (e.g. latency, query time reduction, or percentage improvements) to make your answer even more compelling.")

        model_answer = cls._generate_model_answer(question)
        is_final = question.question_index >= total_questions

        return AnswerEvaluation(
            session_id=request.session_id,
            question_id=request.question_id,
            question_index=question.question_index,
            score=final_score,
            feedback_strengths=strengths,
            feedback_improvements=improvements,
            model_answer=model_answer,
            grounding_warning=grounding_warning,
            is_final_question=is_final,
        )

    @classmethod
    def _generate_model_answer(cls, question: InterviewQuestion) -> str:
        """Provide a benchmark model answer illustrating ideal structure and depth."""
        if question.round_type == "project_deep_dive":
            return (
                "**Exemplary Structure**:\n"
                "1. **Overview & Role**: 'In my Student Management application, I served as the full stack developer responsible for end-to-end functionality.'\n"
                "2. **Architecture**: 'I organized the project with clear separation: a responsive frontend interface, a Python backend handling business logic and validation, and a relational SQL database for persistent student records.'\n"
                "3. **Technical Rationale**: 'Python allowed rapid prototyping and maintainable clean code, SQL ensured ACID-compliant transactional integrity for student records, and Git ensured traceability across feature branches.'\n"
                "4. **Concrete Decision**: 'I implemented strict input validation at the boundary to ensure invalid student records never corrupted database state.'"
            )
        elif question.round_type == "hr_behavioral":
            return (
                "**Exemplary STAR Structure**:\n"
                "- **Situation**: Describe the specific context, deadline, or challenge concisely.\n"
                "- **Task**: Clarify the exact objective you needed to fulfill.\n"
                "- **Action**: Explain the proactive steps you took personally, highlighting communication, problem-solving, and adaptability.\n"
                "- **Result**: Summarize the successful deliverable, team impact, and key take-away you carry forward."
            )
        else:
            return (
                "**Exemplary Technical Structure**:\n"
                "1. **Direct Definition**: Give a crisp definition of the concept upfront.\n"
                "2. **Underlying Mechanism**: Explain the 'how' and 'why' (e.g. data structure, memory layout, or protocol handshake).\n"
                "3. **Engineering Trade-offs**: Contrast advantages against potential bottlenecks (e.g. memory vs CPU, indexing vs write latency).\n"
                "4. **Practical Implementation**: Conclude with how you apply this in practice when building reliable backend systems."
            )

    @classmethod
    def generate_summary(
        cls,
        session_id: str,
        company_name: str,
        role: str,
        round_type: str,
        evaluations: List[AnswerEvaluation],
    ) -> InterviewSummary:
        """Compute final aggregated performance report and interview readiness score."""
        if not evaluations:
            return InterviewSummary(
                session_id=session_id,
                company_name=company_name,
                role=role,
                round_type=round_type,
                total_questions=0,
                overall_score=0.0,
                readiness_level="Significant Preparation Needed",
                strengths_summary=["No questions completed yet."],
                improvement_areas=["Complete mock interview questions to assess performance."],
                suggested_action_items=["Launch an interview round and submit answers for evaluation."],
            )

        total_score = sum(e.score for e in evaluations)
        avg_score = round(total_score / len(evaluations), 1)

        if avg_score >= 8.0:
            readiness = "Ready for Interview"
        elif avg_score >= 6.0:
            readiness = "Needs Practice"
        else:
            readiness = "Significant Preparation Needed"

        # Deduplicate strengths and improvements
        all_strengths = []
        for e in evaluations:
            all_strengths.extend(e.feedback_strengths)
        unique_strengths = list(dict.fromkeys(all_strengths))[:4]

        all_improvements = []
        for e in evaluations:
            all_improvements.extend(e.feedback_improvements)
        unique_improvements = list(dict.fromkeys(all_improvements))[:4]

        # Action items based on round type and score
        action_items: List[str] = []
        if round_type == "project_deep_dive":
            action_items.append("Review your Student Management project architecture diagrams and practice explaining your schema design.")
            action_items.append("Prepare clear talking points on how your Git workflow kept codebase commits organized.")
        elif round_type == "hr_behavioral":
            action_items.append("Draft 3-4 distinct STAR stories covering deadline pressure, feedback handling, and teamwork.")
            action_items.append("Practice keeping answers under 2 minutes while emphasizing measurable outcomes.")
        else:
            action_items.append("Revise core technical topics: PostgreSQL indexing, transaction isolation, and Python memory management.")
            action_items.append("Practice whiteboarding API endpoints and defining error status envelopes.")

        return InterviewSummary(
            session_id=session_id,
            company_name=company_name,
            role=role,
            round_type=round_type,
            total_questions=len(evaluations),
            overall_score=avg_score,
            readiness_level=readiness,
            strengths_summary=unique_strengths or ["Answered all questions."],
            improvement_areas=unique_improvements or ["Continue refining concise delivery."],
            suggested_action_items=action_items,
        )
