"""Placement Intelligence Service.

Provides deterministic eligibility verification, skill matching, opportunity prioritization,
company comparison, and targeted preparation advice for placement drives.
"""

from datetime import date, datetime
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple
import uuid
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.models.placement import PlacementDrive
from app.models.profile import Profile
from app.models.project import Project
from app.models.certification import Certification
from app.models.skill import Skill
from app.schemas.placement import (
    CriterionEvaluation,
    DriveComparison,
    EligibilityResult,
    PlacementDriveResponse,
    PreparationPlanResponse,
    PriorityEvaluation,
    SkillMatchResult,
)
from app.services.llm import get_llm_provider
from app.services.profile_service import get_default_profile

logger = logging.getLogger(__name__)

# Common branch normalization synonyms
BRANCH_SYNONYMS: Dict[str, Set[str]] = {
    "cse": {
        "cse", "cs", "computer science", "computer science and engineering",
        "computer science & engineering", "b.e cse", "b.tech cse", "b.e. cse", "b.tech. cse"
    },
    "it": {
        "it", "information technology", "b.e it", "b.tech it", "b.e. it", "b.tech. it"
    },
    "ece": {
        "ece", "electronics and communication", "electronics and communication engineering",
        "electronics & communication engineering", "b.e ece", "b.tech ece"
    },
    "eee": {
        "eee", "electrical and electronics engineering", "electrical & electronics engineering",
        "b.e eee", "b.tech eee"
    },
    "mech": {
        "mech", "mechanical", "mechanical engineering", "b.e mech", "b.tech mech"
    },
}

# Skill synonyms for fuzzy matching
SKILL_SYNONYMS: Dict[str, str] = {
    "react": "react",
    "react.js": "react",
    "reactjs": "react",
    "node": "node.js",
    "node.js": "node.js",
    "nodejs": "node.js",
    "postgres": "postgresql",
    "postgresql": "postgresql",
    "psql": "postgresql",
    "mongo": "mongodb",
    "mongodb": "mongodb",
    "python": "python",
    "python3": "python",
    "fastapi": "fastapi",
    "fast-api": "fastapi",
    "fast api": "fastapi",
    "docker": "docker",
    "k8s": "kubernetes",
    "kubernetes": "kubernetes",
    "aws": "aws",
    "amazon web services": "aws",
    "gcp": "gcp",
    "google cloud platform": "gcp",
    "ts": "typescript",
    "typescript": "typescript",
    "js": "javascript",
    "javascript": "javascript",
}


def normalize_string(val: Optional[str]) -> str:
    """Standardizes string for comparison by lowercasing, stripping punctuation and extra spaces."""
    if not val:
        return ""
    cleaned = re.sub(r"[^\w\s\.]", " ", val.lower())
    return " ".join(cleaned.split())


def normalize_skill(name: str) -> str:
    norm = normalize_string(name)
    return SKILL_SYNONYMS.get(norm, norm)


def normalize_branch(name: str) -> str:
    norm = normalize_string(name)
    for canonical, aliases in BRANCH_SYNONYMS.items():
        if norm in aliases or any(alias in norm for alias in aliases):
            return canonical
    return norm


class PlacementIntelligenceService:
    """Deterministic placement intelligence engine."""

    @staticmethod
    async def get_open_drives(db: AsyncSession) -> List[PlacementDrive]:
        """Fetch active placement drives."""
        stmt = (
            select(PlacementDrive)
            .options(selectinload(PlacementDrive.company))
            .where(PlacementDrive.status.notin_(["rejected", "offer_accepted", "closed"]))
            .order_by(PlacementDrive.deadline.asc().nullslast())
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def get_upcoming_deadlines(db: AsyncSession, days: int = 30) -> List[PlacementDrive]:
        """Fetch active drives with deadlines within the specified days window."""
        today = date.today()
        stmt = (
            select(PlacementDrive)
            .options(selectinload(PlacementDrive.company))
            .where(
                PlacementDrive.deadline.isnot(None),
                PlacementDrive.deadline >= today,
                PlacementDrive.status.notin_(["rejected", "offer_accepted", "closed"]),
            )
            .order_by(PlacementDrive.deadline.asc())
        )
        res = await db.execute(stmt)
        all_drives = res.scalars().all()
        return [d for d in all_drives if d.deadline and (d.deadline - today).days <= days]

    @staticmethod
    def evaluate_eligibility(
        profile: Optional[Profile],
        drive: PlacementDrive,
    ) -> EligibilityResult:
        """
        Deterministically evaluates candidate eligibility against placement criteria.
        Missing data yields explicit 'unknown' status, never a false pass.
        """
        company_name = drive.company.name if drive.company else "Unknown Company"
        criteria: List[CriterionEvaluation] = []
        reasons: List[str] = []

        if not profile:
            # Entire profile is missing
            return EligibilityResult(
                drive_id=drive.id,
                company_name=company_name,
                role=drive.role,
                status="UNKNOWN",
                is_eligible=None,
                criteria=[
                    CriterionEvaluation(
                        criterion="profile",
                        status="unknown",
                        required="Candidate Profile",
                        actual=None,
                        message="No candidate profile found in database to evaluate eligibility.",
                    )
                ],
                reasons=["Profile data is missing."],
            )

        # 1. CGPA Criterion
        if drive.min_cgpa is not None:
            min_cgpa = float(drive.min_cgpa)
            if profile.cgpa is None:
                criteria.append(
                    CriterionEvaluation(
                        criterion="cgpa",
                        status="unknown",
                        required=min_cgpa,
                        actual=None,
                        message=f"Candidate CGPA is not recorded (drive requires min {min_cgpa:.2f}).",
                    )
                )
                reasons.append(f"CGPA requirement is {min_cgpa:.2f}, but profile CGPA is missing.")
            else:
                actual_cgpa = float(profile.cgpa)
                if actual_cgpa >= min_cgpa:
                    criteria.append(
                        CriterionEvaluation(
                            criterion="cgpa",
                            status="eligible",
                            required=min_cgpa,
                            actual=actual_cgpa,
                            message=f"CGPA {actual_cgpa:.2f} meets minimum requirement of {min_cgpa:.2f}.",
                        )
                    )
                else:
                    criteria.append(
                        CriterionEvaluation(
                            criterion="cgpa",
                            status="not_eligible",
                            required=min_cgpa,
                            actual=actual_cgpa,
                            message=f"CGPA {actual_cgpa:.2f} is below minimum requirement of {min_cgpa:.2f}.",
                        )
                    )
                    reasons.append(f"CGPA {actual_cgpa:.2f} does not meet required {min_cgpa:.2f}.")
        else:
            criteria.append(
                CriterionEvaluation(
                    criterion="cgpa",
                    status="na",
                    required=None,
                    actual=float(profile.cgpa) if profile.cgpa is not None else None,
                    message="No minimum CGPA requirement specified.",
                )
            )

        # 2. Branch Criterion
        if drive.eligible_branches and len(drive.eligible_branches) > 0:
            if not profile.branch:
                criteria.append(
                    CriterionEvaluation(
                        criterion="branch",
                        status="unknown",
                        required=drive.eligible_branches,
                        actual=None,
                        message="Candidate branch is not recorded.",
                    )
                )
                reasons.append("Branch requirement specified, but profile branch is missing.")
            else:
                user_branch_norm = normalize_branch(profile.branch)
                allowed_norms = [normalize_branch(b) for b in drive.eligible_branches]

                if user_branch_norm in allowed_norms:
                    criteria.append(
                        CriterionEvaluation(
                            criterion="branch",
                            status="eligible",
                            required=drive.eligible_branches,
                            actual=profile.branch,
                            message=f"Branch '{profile.branch}' is eligible.",
                        )
                    )
                else:
                    criteria.append(
                        CriterionEvaluation(
                            criterion="branch",
                            status="not_eligible",
                            required=drive.eligible_branches,
                            actual=profile.branch,
                            message=f"Branch '{profile.branch}' is not in eligible branches ({', '.join(drive.eligible_branches)}).",
                        )
                    )
                    reasons.append(f"Branch '{profile.branch}' is not eligible.")
        else:
            criteria.append(
                CriterionEvaluation(
                    criterion="branch",
                    status="na",
                    required=None,
                    actual=profile.branch,
                    message="All branches eligible.",
                )
            )

        # 3. Graduation Year Criterion
        if drive.graduation_year is not None:
            if profile.graduation_year is None:
                criteria.append(
                    CriterionEvaluation(
                        criterion="graduation_year",
                        status="unknown",
                        required=drive.graduation_year,
                        actual=None,
                        message=f"Candidate graduation year is not recorded (drive requires {drive.graduation_year}).",
                    )
                )
                reasons.append(f"Batch requirement is {drive.graduation_year}, but profile graduation year is missing.")
            elif profile.graduation_year == drive.graduation_year:
                criteria.append(
                    CriterionEvaluation(
                        criterion="graduation_year",
                        status="eligible",
                        required=drive.graduation_year,
                        actual=profile.graduation_year,
                        message=f"Graduation year {profile.graduation_year} matches required batch {drive.graduation_year}.",
                    )
                )
            else:
                criteria.append(
                    CriterionEvaluation(
                        criterion="graduation_year",
                        status="not_eligible",
                        required=drive.graduation_year,
                        actual=profile.graduation_year,
                        message=f"Graduation year {profile.graduation_year} does not match required batch {drive.graduation_year}.",
                    )
                )
                reasons.append(f"Graduation year {profile.graduation_year} does not match required {drive.graduation_year}.")
        else:
            criteria.append(
                CriterionEvaluation(
                    criterion="graduation_year",
                    status="na",
                    required=None,
                    actual=profile.graduation_year,
                    message="No specific graduation batch requirement.",
                )
            )

        # 4. Backlog Criterion
        if drive.backlog_allowed is False:
            criteria.append(
                CriterionEvaluation(
                    criterion="backlog",
                    status="unknown",
                    required="0 active backlogs",
                    actual=None,
                    message="No active backlogs allowed. Candidate must verify 0 standing arrears.",
                )
            )
        else:
            criteria.append(
                CriterionEvaluation(
                    criterion="backlog",
                    status="na",
                    required=None,
                    actual=None,
                    message="Backlogs permitted or not restricted.",
                )
            )

        # Compute Overall Status
        has_not_eligible = any(c.status == "not_eligible" for c in criteria)
        has_unknown = any(c.status == "unknown" for c in criteria)

        if has_not_eligible:
            overall_status = "NOT_ELIGIBLE"
            is_eligible = False
        elif has_unknown:
            overall_status = "UNKNOWN"
            is_eligible = None
        else:
            overall_status = "ELIGIBLE"
            is_eligible = True

        return EligibilityResult(
            drive_id=drive.id,
            company_name=company_name,
            role=drive.role,
            status=overall_status,
            is_eligible=is_eligible,
            criteria=criteria,
            reasons=reasons,
        )

    @staticmethod
    def calculate_skill_match(
        user_skills: List[Skill],
        drive: PlacementDrive,
    ) -> SkillMatchResult:
        """
        Deterministically evaluates matching and missing skills for required and preferred requirements.
        """
        company_name = drive.company.name if drive.company else "Unknown Company"
        user_skill_map = {normalize_skill(s.name): s.name for s in user_skills}

        req_skills = drive.required_skills or []
        pref_skills = drive.preferred_skills or []

        matching_required: List[str] = []
        missing_required: List[str] = []

        for req in req_skills:
            norm_req = normalize_skill(req)
            if norm_req in user_skill_map:
                matching_required.append(req)
            elif any(norm_req in u_norm or u_norm in norm_req for u_norm in user_skill_map):
                matching_required.append(req)
            else:
                missing_required.append(req)

        matching_preferred: List[str] = []
        missing_preferred: List[str] = []

        for pref in pref_skills:
            norm_pref = normalize_skill(pref)
            if norm_pref in user_skill_map:
                matching_preferred.append(pref)
            elif any(norm_pref in u_norm or u_norm in norm_pref for u_norm in user_skill_map):
                matching_preferred.append(pref)
            else:
                missing_preferred.append(pref)

        req_pct = (
            (len(matching_required) / len(req_skills) * 100.0)
            if req_skills
            else 100.0
        )
        pref_pct = (
            (len(matching_preferred) / len(pref_skills) * 100.0)
            if pref_skills
            else 100.0
        )

        if req_skills and pref_skills:
            overall_pct = (req_pct * 0.75) + (pref_pct * 0.25)
        elif req_skills:
            overall_pct = req_pct
        elif pref_skills:
            overall_pct = pref_pct
        else:
            overall_pct = 100.0

        return SkillMatchResult(
            drive_id=drive.id,
            company_name=company_name,
            role=drive.role,
            total_required_count=len(req_skills),
            matching_required=matching_required,
            missing_required=missing_required,
            required_match_percentage=round(req_pct, 1),
            total_preferred_count=len(pref_skills),
            matching_preferred=matching_preferred,
            missing_preferred=missing_preferred,
            preferred_match_percentage=round(pref_pct, 1),
            overall_match_percentage=round(overall_pct, 1),
        )

    @classmethod
    async def rank_opportunities(
        cls,
        db: AsyncSession,
        profile: Optional[Profile],
        user_skills: List[Skill],
    ) -> List[PriorityEvaluation]:
        """
        Ranks all open opportunities using a transparent composite formula:
        Eligibility (40) + Skill Match (30) + Deadline Urgency (15) + Tier/Compensation (15).
        """
        drives = await cls.get_open_drives(db)
        evaluations: List[PriorityEvaluation] = []
        today = date.today()

        for drive in drives:
            company_name = drive.company.name if drive.company else "Unknown Company"
            eligibility = cls.evaluate_eligibility(profile, drive)
            skill_match = cls.calculate_skill_match(user_skills, drive)

            score = 0.0
            breakdown: List[str] = []

            # 1. Eligibility Points (max 40)
            if eligibility.status == "ELIGIBLE":
                score += 40.0
                breakdown.append("Eligibility: 40/40 (Candidate meets all specified criteria)")
            elif eligibility.status == "UNKNOWN":
                score += 20.0
                breakdown.append("Eligibility: 20/40 (Criteria need verification or backlog check)")
            else:
                score += 0.0
                breakdown.append("Eligibility: 0/40 (Candidate does not meet criteria)")

            # 2. Skill Match Points (max 30)
            skill_pts = (skill_match.overall_match_percentage / 100.0) * 30.0
            score += skill_pts
            breakdown.append(f"Skill Match: {skill_pts:.1f}/30 ({skill_match.overall_match_percentage:.0f}% match)")

            # 3. Deadline Urgency (max 15)
            days_left = None
            if drive.deadline:
                days_left = (drive.deadline - today).days
                if days_left < 0:
                    deadline_pts = 0.0
                    breakdown.append("Urgency: 0/15 (Deadline has passed)")
                elif days_left <= 7:
                    deadline_pts = 15.0
                    breakdown.append(f"Urgency: 15/15 (Critical: {days_left} days left)")
                elif days_left <= 14:
                    deadline_pts = 12.0
                    breakdown.append(f"Urgency: 12/15 (Urgent: {days_left} days left)")
                elif days_left <= 30:
                    deadline_pts = 8.0
                    breakdown.append(f"Urgency: 8/15 (Approaching: {days_left} days left)")
                else:
                    deadline_pts = 4.0
                    breakdown.append(f"Urgency: 4/15 ({days_left} days remaining)")
            else:
                deadline_pts = 5.0
                breakdown.append("Urgency: 5/15 (No deadline announced)")
            score += deadline_pts

            # 4. Tier & Compensation Points (max 15)
            tier_pts = 5.0
            tier_lower = (drive.tier or "").lower()
            if any(t in tier_lower for t in ["super dream", "tier 1", "tier-1", "marquee"]):
                tier_pts = 15.0
                breakdown.append(f"Role Value: 15/15 ({drive.tier or 'Super Dream'})")
            elif any(t in tier_lower for t in ["dream", "tier 2", "tier-2"]):
                tier_pts = 10.0
                breakdown.append(f"Role Value: 10/15 ({drive.tier or 'Dream'})")
            else:
                # Inspect compensation string (e.g. "30 LPA", "12 LPA")
                comp_match = re.search(r"(\d+(\.\d+)?)", drive.compensation or "")
                if comp_match:
                    comp_val = float(comp_match.group(1))
                    if comp_val >= 18.0:
                        tier_pts = 15.0
                        breakdown.append(f"Role Value: 15/15 (High compensation: {drive.compensation})")
                    elif comp_val >= 9.0:
                        tier_pts = 10.0
                        breakdown.append(f"Role Value: 10/15 (Good compensation: {drive.compensation})")
                    else:
                        tier_pts = 6.0
                        breakdown.append(f"Role Value: 6/15 (Standard compensation: {drive.compensation})")
                else:
                    breakdown.append("Role Value: 5/15 (Standard role)")
            score += tier_pts

            composite_score = round(score, 1)
            if composite_score >= 70.0:
                priority_level = "HIGH"
            elif composite_score >= 45.0:
                priority_level = "MEDIUM"
            else:
                priority_level = "LOW"

            evaluations.append(
                PriorityEvaluation(
                    drive_id=drive.id,
                    company_name=company_name,
                    role=drive.role,
                    priority_level=priority_level,
                    composite_score=composite_score,
                    eligibility_status=eligibility.status,
                    skill_match_percentage=skill_match.overall_match_percentage,
                    deadline=drive.deadline,
                    days_until_deadline=days_left,
                    compensation=drive.compensation,
                    tier=drive.tier,
                    score_breakdown=breakdown,
                )
            )

        # Sort descending by composite score
        evaluations.sort(key=lambda x: x.composite_score, reverse=True)
        return evaluations

    @classmethod
    async def compare_profile_to_drive(
        cls,
        db: AsyncSession,
        drive_id: uuid.UUID,
    ) -> Optional[DriveComparison]:
        """
        Detailed comparison between candidate's profile and a placement drive.
        """
        stmt = (
            select(PlacementDrive)
            .options(selectinload(PlacementDrive.company))
            .where(PlacementDrive.id == drive_id)
        )
        res = await db.execute(stmt)
        drive = res.scalars().first()
        if not drive:
            return None

        profile = await get_default_profile(db)
        skills_res = await db.execute(select(Skill))
        user_skills = list(skills_res.scalars().all())

        projects_res = await db.execute(select(Project).order_by(Project.created_at.desc()))
        projects = list(projects_res.scalars().all())

        certs_res = await db.execute(select(Certification).order_by(Certification.created_at.desc()))
        certs = list(certs_res.scalars().all())

        eligibility = cls.evaluate_eligibility(profile, drive)
        skill_match = cls.calculate_skill_match(user_skills, drive)

        # Find matching projects based on technologies used
        drive_techs = {normalize_skill(s) for s in (drive.required_skills or []) + (drive.preferred_skills or [])}
        matching_projects: List[Dict[str, Any]] = []

        for p in projects:
            p_techs = [normalize_skill(t) for t in (p.technologies or [])]
            overlap = drive_techs.intersection(p_techs)
            if overlap:
                matching_projects.append({
                    "id": str(p.id),
                    "name": p.name,
                    "technologies": p.technologies,
                    "status": p.status,
                    "role": p.role,
                    "matched_technologies": list(overlap),
                })

        # Find matching certifications
        matching_certs: List[Dict[str, Any]] = []
        company_norm = normalize_string(drive.company.name if drive.company else "")
        for c in certs:
            c_norm = normalize_string(c.name)
            if any(t in c_norm for t in drive_techs) or (company_norm and company_norm in c_norm):
                matching_certs.append({
                    "id": str(c.id),
                    "name": c.name,
                    "issuer": c.issuer,
                    "issue_date": c.issue_date.isoformat() if c.issue_date else None,
                })

        drive_resp = PlacementDriveResponse.model_validate(drive)
        return DriveComparison(
            drive=drive_resp,
            eligibility=eligibility,
            skill_match=skill_match,
            matching_projects=matching_projects,
            matching_certifications=matching_certs,
        )

    @classmethod
    async def generate_preparation_plan(
        cls,
        db: AsyncSession,
        drive_id: uuid.UUID,
    ) -> Optional[PreparationPlanResponse]:
        """
        Generates targeted company/role preparation plan combining structured drive requirements,
        profile facts, relevant projects, and document retrieval.
        """
        comparison = await cls.compare_profile_to_drive(db, drive_id)
        if not comparison:
            return None

        drive = comparison.drive
        company_name = drive.company.name if drive.company else "Unknown Company"

        # Semantic retrieval for company-related document context
        from app.services.rag_service import rag_service
        query_text = f"{company_name} {drive.role} interview rounds syllabus coding questions selection process"
        doc_sources = await rag_service.retrieve_relevant_chunks(
            db=db,
            query=query_text,
            top_k=3,
            similarity_threshold=0.35,
        )

        doc_snippets = "\n".join([f"- From {s.filename}: {s.snippet}" for s in doc_sources]) if doc_sources else "None"

        # Build prompt facts
        rounds_info = ", ".join(drive.selection_process) if drive.selection_process else "Standard Technical & HR Rounds"
        missing_skills_info = ", ".join(comparison.skill_match.missing_required) if comparison.skill_match.missing_required else "None (all required skills covered!)"
        matching_skills_info = ", ".join(comparison.skill_match.matching_required) if comparison.skill_match.matching_required else "None"
        matching_projects_names = [p["name"] for p in comparison.matching_projects]

        prompt = f"""Generate a focused, actionable interview preparation strategy for Karthik.

Placement Drive Details:
- Company: {company_name}
- Role: {drive.role}
- Compensation: {drive.compensation or 'Not specified'}
- Selection Process Rounds: {rounds_info}
- Matching Candidate Skills: {matching_skills_info}
- Missing Required Skills to Prepare: {missing_skills_info}
- Relevant Projects Candidate Can Discuss: {', '.join(matching_projects_names) if matching_projects_names else 'General projects'}

Relevant Document Knowledge:
{doc_snippets}

Please provide a structured preparation roadmap:
1. Selection Rounds Overview & Strategy
2. Key Technical Topics & Priority Focus Areas (highlighting how to address missing skills)
3. Project Presentation Tips (which projects to highlight and key talking points)
4. Company & Behavioral Prep Advice
"""
        llm = get_llm_provider()
        system_prompt = (
            "You are Karthik AI, Karthik's placement advisor. Provide concrete, well-structured, "
            "practical preparation advice without generic filler. Format clearly with bullet points."
        )

        resp = await llm.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.0,
        )

        return PreparationPlanResponse(
            drive_id=drive.id,
            company_name=company_name,
            role=drive.role,
            selection_process=drive.selection_process,
            preparation_advice=resp.content,
            matching_projects=matching_projects_names,
            key_skills_to_prepare=comparison.skill_match.missing_required,
            relevant_document_sources=[s.filename for s in doc_sources],
        )


placement_intelligence_service = PlacementIntelligenceService()
