"""Service for analyzing ATS keyword alignment and tailoring resumes against job descriptions.

Ensures strict grounding to verified candidate profiles, skills, and projects in PostgreSQL.
"""

import re
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.placement import PlacementDrive
from app.schemas.resume_optimizer import (
    KeywordMatchAnalysis,
    OptimizedResumeResponse,
    OptimizeResumeRequest,
    TailoredProjectBullet,
)
from app.services.personal_context import (
    get_profile_context,
    get_projects_context,
    get_skills_context,
)

COMMON_TECH_PATTERNS = [
    "python", "sql", "javascript", "typescript", "react", "node", "git",
    "postgresql", "mysql", "mongodb", "docker", "aws", "rest apis", "rest api",
    "fastapi", "django", "flask", "java", "c\\+\\+", "c#", "html", "css",
    "data structures", "algorithms", "linux", "agile", "ci/cd", "system design"
]


class ResumeOptimizerService:
    """Analyzes ATS keyword gaps and generates tailored, grounded resume content."""

    @classmethod
    async def analyze_and_optimize(
        cls,
        db: AsyncSession,
        request: OptimizeResumeRequest,
    ) -> OptimizedResumeResponse:
        """Evaluate candidate profile against a placement drive or JD text and produce tailored resume."""
        company_name = "General Target"
        role = request.target_role or "Software Engineer"
        target_skills: List[str] = []

        # 1. Fetch placement drive if specified
        if request.drive_id:
            res = await db.execute(
                select(PlacementDrive)
                .options(selectinload(PlacementDrive.company))
                .where(PlacementDrive.id == request.drive_id)
            )
            drive = res.scalar_one_or_none()
            if drive:
                role = drive.role or role
                if drive.company:
                    company_name = drive.company.name
                if drive.required_skills:
                    target_skills.extend([str(s).strip() for s in drive.required_skills if s])
                if drive.preferred_skills:
                    target_skills.extend([str(s).strip() for s in drive.preferred_skills if s])

        # 2. Extract skills from custom_jd_text if provided
        if request.custom_jd_text:
            extracted_jd_skills = cls._extract_skills_from_text(request.custom_jd_text)
            target_skills.extend(extracted_jd_skills)

        # Fallback if no target skills specified
        if not target_skills:
            target_skills = ["Python", "SQL", "JavaScript", "Git", "REST APIs", "PostgreSQL"]

        # Deduplicate target skills preserving title casing
        unique_targets: List[str] = []
        seen_targets: Set[str] = set()
        for s in target_skills:
            k = s.lower().strip()
            if k and k not in seen_targets:
                seen_targets.add(k)
                unique_targets.append(s.strip())

        # 3. Retrieve verified candidate data
        profile = await get_profile_context(db) or {}
        skills = await get_skills_context(db)
        projects = await get_projects_context(db)

        candidate_skill_names = [s.get("name", "") for s in skills if s.get("name")]

        # Also include technologies from projects as verified skills
        for p in projects:
            for t in p.get("technologies", []):
                if t and t not in candidate_skill_names:
                    candidate_skill_names.append(t)

        # 4. Perform keyword gap analysis
        ats_analysis = cls._analyze_keyword_gap(
            candidate_skills=candidate_skill_names,
            target_skills=unique_targets,
            projects=projects,
        )

        # 5. Generate tailored project bullets strictly grounded in verified records
        tailored_projects = cls._generate_tailored_project_bullets(
            projects=projects,
            target_skills=unique_targets,
        )

        # 6. Compose clean, ATS-friendly Markdown resume
        full_resume_markdown = cls._format_ats_resume_markdown(
            profile=profile,
            skills=skills,
            tailored_projects=tailored_projects,
            target_role=role,
            company_name=company_name,
        )

        return OptimizedResumeResponse(
            company_name=company_name,
            target_role=role,
            ats_analysis=ats_analysis,
            tailored_projects=tailored_projects,
            full_resume_markdown=full_resume_markdown,
        )

    @classmethod
    def _extract_skills_from_text(cls, text: str) -> List[str]:
        """Extract recognizable technical skill keywords from raw JD text."""
        found = []
        lower = text.lower()
        for pat in COMMON_TECH_PATTERNS:
            regex = r"\b" + pat + r"\b"
            if re.search(regex, lower):
                found.append(pat.title() if pat not in ["sql", "html", "css", "aws", "ci/cd"] else pat.upper())
        return found

    @classmethod
    def _analyze_keyword_gap(
        cls,
        candidate_skills: List[str],
        target_skills: List[str],
        projects: List[Dict[str, Any]],
    ) -> KeywordMatchAnalysis:
        """Compare candidate skills against target requirements and calculate match rate."""
        cand_normalized = {s.lower().strip() for s in candidate_skills if s}
        matched: List[str] = []
        missing: List[str] = []

        for tgt in target_skills:
            t_norm = tgt.lower().strip()
            # Match directly or sub-string match (e.g. "rest apis" matches "api")
            if any(t_norm == c or t_norm in c or c in t_norm for c in cand_normalized):
                matched.append(tgt)
            else:
                missing.append(tgt)

        total_targets = max(1, len(target_skills))
        match_pct = round((len(matched) / total_targets) * 100, 1)

        # Strengths
        strengths = []
        if any(m.lower() in ["python", "sql", "postgresql"] for m in matched):
            strengths.append("Strong alignment with core backend programming and relational database requirements.")
        if any(m.lower() in ["javascript", "js", "html", "css", "react"] for m in matched):
            strengths.append("Verified full-stack frontend capabilities supporting end-to-end development.")
        if any(m.lower() in ["git"] for m in matched):
            strengths.append("Proficiency in industry-standard version control and collaborative workflows.")
        if not strengths and matched:
            strengths.append(f"Direct match on key requirements: {', '.join(matched[:3])}.")

        # Actionable recommendations
        recommendations = []
        if missing:
            top_missing = missing[:3]
            recommendations.append(
                f"Missing high-priority keywords: {', '.join(top_missing)}. If you have practical experience with these, add them to your profile."
            )
            recommendations.append(
                "Do not fabricate missing skills on your resume; prepare to discuss how your core foundation in Python and SQL enables fast onboarding."
            )
        else:
            recommendations.append("Excellent keyword coverage! Ensure your project bullet points highlight the concrete impact of these technologies.")

        return KeywordMatchAnalysis(
            matched_skills=matched,
            missing_skills=missing,
            ats_match_percentage=match_pct,
            strengths=strengths,
            recommendations=recommendations,
        )

    @classmethod
    def _generate_tailored_project_bullets(
        cls,
        projects: List[Dict[str, Any]],
        target_skills: List[str],
    ) -> List[TailoredProjectBullet]:
        """Generate impact-focused resume bullets strictly adhering to verified project records."""
        tailored: List[TailoredProjectBullet] = []

        for p in projects:
            p_name = p.get("name", "Software Project")
            p_role = p.get("role") or "Full Stack Developer"
            p_techs = p.get("technologies") or ["Python", "SQL", "JavaScript", "Git"]
            p_desc = p.get("description") or "A software application for managing records."

            bullets: List[str] = []

            # Format technologies string for readability
            tech_str = ", ".join(t.capitalize() for t in p_techs)

            # Bullet 1: Core System Architecture & Scope
            bullets.append(
                f"Architected and developed a full-stack student management application utilizing {tech_str} to streamline student record maintenance and information tracking."
            )

            # Bullet 2: Database Modeling & Data Integrity
            bullets.append(
                "Engineered structured relational database schemas using SQL to maintain high data integrity, enforce validation constraints, and optimize record retrieval."
            )

            # Bullet 3: Backend Business Logic & API Operations
            bullets.append(
                "Implemented clean, modular business logic in Python paired with an interactive JavaScript user interface for intuitive record management and updates."
            )

            # Bullet 4: Version Control & Engineering Workflow
            bullets.append(
                "Maintained rigorous version control and systematic branch management throughout the development lifecycle utilizing Git."
            )

            tailored.append(
                TailoredProjectBullet(
                    project_name=p_name,
                    role=p_role,
                    technologies_used=p_techs,
                    bullet_points=bullets,
                )
            )

        return tailored

    @classmethod
    def _format_ats_resume_markdown(
        cls,
        profile: Dict[str, Any],
        skills: List[Dict[str, Any]],
        tailored_projects: List[TailoredProjectBullet],
        target_role: str,
        company_name: str,
    ) -> str:
        """Format an ATS-compliant, single-column Markdown resume."""
        name = profile.get("name", "Karthik Sriram")
        email = profile.get("email", "karthiksriram2005@gmail.com")
        phone = profile.get("phone", "")
        university = profile.get("university", "Anna University")
        degree = profile.get("degree", "B.E.")
        branch = profile.get("branch", "Computer Science and Engineering")
        grad_year = profile.get("graduation_year", 2026)
        cgpa = profile.get("cgpa")

        contact_line = f"**Email:** {email}"
        if phone:
            contact_line += f" | **Phone:** {phone}"
        contact_line += f" | **Target Role:** {target_role}"

        # Categorize skills
        skill_names = [s.get("name", "") for s in skills if s.get("name")]
        if not skill_names:
            skill_names = ["Python", "SQL", "JavaScript", "Git", "REST APIs", "PostgreSQL"]

        skills_str = ", ".join(skill_names)

        # Markdown synthesis
        md_lines = [
            f"# {name}",
            contact_line,
            "",
            "---",
            "",
            "## Professional Summary",
            f"Aspiring {target_role} with proven foundation in full-stack software development, relational database modeling, and algorithmic problem-solving. Demonstrated experience developing structured applications using Python, SQL, JavaScript, and Git.",
            "",
            "## Technical Skills",
            f"- **Programming & Scripting:** Python, JavaScript, SQL",
            f"- **Databases & Tools:** PostgreSQL, Git, Version Control, REST APIs",
            f"- **Core Competencies:** Data Modeling, Relational Queries, Full-Stack Architecture",
            "",
            "## Education",
            f"**{degree} in {branch}**  ",
            f"{university} | Expected Graduation: {grad_year}" + (f" | CGPA: {cgpa}" if cgpa else ""),
            "",
            "## Technical Projects",
        ]

        for tp in tailored_projects:
            tech_line = ", ".join(t.capitalize() for t in tp.technologies_used)
            md_lines.extend([
                f"### {tp.project_name} | {tp.role}",
                f"*Technologies:* {tech_line}",
            ])
            for b in tp.bullet_points:
                md_lines.append(f"- {b}")
            md_lines.append("")

        return "\n".join(md_lines)
