"""Personal context retrieval service.

Fetches authoritative structured personal information from PostgreSQL
(Profile, Skills, Projects, Certifications, Companies, Placement Drives).
"""

import logging
import re
from typing import Any, Dict, List, Optional, Set
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.certification import Certification
from app.models.company import Company
from app.models.placement import PlacementDrive
from app.models.profile import Profile
from app.models.project import Project
from app.models.skill import Skill
from app.services.profile_service import get_default_profile

logger = logging.getLogger(__name__)


async def get_profile_context(db: AsyncSession) -> Optional[Dict[str, Any]]:
    """Retrieve structured profile data."""
    profile = await get_default_profile(db)
    if not profile:
        return None

    data = {
        "name": profile.name,
        "email": profile.email,
        "phone": profile.phone,
        "university": profile.university,
        "degree": profile.degree,
        "branch": profile.branch,
        "graduation_year": profile.graduation_year,
        "cgpa": float(profile.cgpa) if profile.cgpa is not None else None,
        "career_goals": profile.career_goals,
        "summary": profile.summary,
    }
    # Filter out None values to keep context concise
    return {k: v for k, v in data.items() if v is not None}


async def get_skills_context(db: AsyncSession) -> List[Dict[str, Any]]:
    """Retrieve structured skills data."""
    result = await db.execute(select(Skill).order_by(Skill.category.asc().nullslast(), Skill.name.asc()))
    skills = result.scalars().all()
    return [
        {
            "name": s.name,
            "category": s.category,
            "proficiency": s.proficiency,
        }
        for s in skills
    ]


async def get_projects_context(db: AsyncSession) -> List[Dict[str, Any]]:
    """Retrieve structured projects data."""
    result = await db.execute(select(Project).order_by(Project.created_at.desc()))
    projects = result.scalars().all()
    return [
        {
            "name": p.name,
            "description": p.description,
            "technologies": p.technologies or [],
            "status": p.status,
            "role": p.role,
            "url": p.url,
            "start_date": p.start_date.isoformat() if p.start_date else None,
            "end_date": p.end_date.isoformat() if p.end_date else None,
        }
        for p in projects
    ]


async def get_certifications_context(db: AsyncSession) -> List[Dict[str, Any]]:
    """Retrieve structured certifications data."""
    result = await db.execute(select(Certification).order_by(Certification.issue_date.desc().nullslast()))
    certs = result.scalars().all()
    return [
        {
            "name": c.name,
            "issuer": c.issuer,
            "issue_date": c.issue_date.isoformat() if c.issue_date else None,
            "expiry_date": c.expiry_date.isoformat() if c.expiry_date else None,
            "credential_url": c.credential_url,
        }
        for c in certs
    ]


async def get_companies_context(db: AsyncSession) -> List[Dict[str, Any]]:
    """Retrieve structured companies data."""
    result = await db.execute(select(Company).order_by(Company.name.asc()))
    companies = result.scalars().all()
    return [
        {
            "name": c.name,
            "industry": c.industry,
            "location": c.location,
            "website": c.website,
            "notes": c.notes,
        }
        for c in companies
    ]


async def get_placement_context(db: AsyncSession) -> List[Dict[str, Any]]:
    """Retrieve structured placement drives data with company information and intelligence evaluation."""
    stmt = (
        select(PlacementDrive)
        .options(selectinload(PlacementDrive.company))
        .order_by(PlacementDrive.deadline.asc().nullslast())
    )
    result = await db.execute(stmt)
    drives = result.scalars().all()

    profile = await get_default_profile(db)
    skills_res = await db.execute(select(Skill))
    user_skills = list(skills_res.scalars().all())

    from app.services.placement_intelligence import placement_intelligence_service

    out = []
    for d in drives:
        eligibility = placement_intelligence_service.evaluate_eligibility(profile, d)
        skill_match = placement_intelligence_service.calculate_skill_match(user_skills, d)
        out.append({
            "id": str(d.id),
            "company_name": d.company.name if d.company else "Unknown",
            "role": d.role,
            "status": d.status,
            "deadline": d.deadline.isoformat() if d.deadline else None,
            "compensation": d.compensation,
            "employment_type": d.employment_type,
            "location": d.location,
            "notes": d.notes,
            "applied_date": d.applied_date.isoformat() if d.applied_date else None,
            "min_cgpa": float(d.min_cgpa) if d.min_cgpa is not None else None,
            "eligible_branches": d.eligible_branches or [],
            "graduation_year": d.graduation_year,
            "required_skills": d.required_skills or [],
            "preferred_skills": d.preferred_skills or [],
            "tier": d.tier,
            "eligibility_status": eligibility.status,
            "eligibility_reasons": eligibility.reasons,
            "matching_skills": skill_match.matching_required,
            "missing_skills": skill_match.missing_required,
            "skill_match_percentage": skill_match.overall_match_percentage,
        })
    return out


def analyze_question_intent(question: str) -> Set[str]:
    """
    Deterministic intent analysis mapping user question to structured context categories.
    Avoids unnecessary LLM calls while preventing blind full-database queries.
    """
    q = question.lower()
    categories: Set[str] = set()

    # Pattern sets
    profile_patterns = [
        r"\bcgpa\b", r"\bgpa\b", r"\bgrade\b", r"\bmarks\b", r"\bpercentage\b",
        r"\buniversity\b", r"\bcollege\b", r"\binstitute\b", r"\bcampus\b",
        r"\bdegree\b", r"\bbranch\b", r"\bmajor\b", r"\bgraduation\b", r"\bgraduate\b",
        r"\beducation\b", r"\bacademics?\b", r"\bcareer goals?\b",
        r"\bwho am i\b", r"\bmy name\b", r"\bcontact\b", r"\bemail\b", r"\bphone\b",
        r"\bprofile\b", r"\bacm\b", r"\brole in\b", r"\bbio\b", r"\bsummary\b",
    ]

    skills_patterns = [
        r"\bskills?\b", r"\blanguages?\b", r"\btech stack\b", r"\btechnolog(y|ies)\b",
        r"\bframeworks?\b", r"\btools?\b", r"\bdatabases?\b", r"\bproficien(t|cy)\b",
        r"\bprogramming\b", r"\bcoding\b", r"\bcompetenc(y|ies)\b", r"\bbackend\b",
        r"\bfrontend\b", r"\bfull-?stack\b",
    ]

    projects_patterns = [
        r"\bprojects?\b", r"\bbuilt\b", r"\bbuild\b", r"\bdevelop(ed|ing)?\b",
        r"\bportfolio\b", r"\bapplication\b", r"\bapp\b", r"\brepository\b",
        r"\bcodebase\b", r"\bcarbon footprint\b", r"\bstudent management\b", r"\bcreated\b",
    ]

    certs_patterns = [
        r"\bcert(s|ification|ifications)?\b", r"\bcertified\b", r"\bcredential(s)?\b",
        r"\blicense(s|d)?\b", r"\bbadge(s)?\b",
    ]

    placement_patterns = [
        r"\bplacement(s)?\b", r"\bdrive(s)?\b", r"\bcompan(y|ies)\b", r"\binterview(s)?\b",
        r"\bapplication(s)?\b", r"\bapplied\b", r"\bdeadline(s)?\b", r"\bsalary\b",
        r"\bpackage\b", r"\blpa\b", r"\bctc\b", r"\boffer(s|ed)?\b", r"\bshortlist(ed)?\b",
        r"\btarget company\b", r"\btarget companies\b", r"\bjob(s)?\b",
    ]

    placement_intelligence_patterns = [
        r"\beligib(le|ility)\b", r"\bqualif(y|ied|ication)\b",
        r"\bpriorit(y|ize|ization)\b", r"\bpipeline\b",
        r"\bupcoming\b", r"\bopen drives?\b", r"\bcompare\b",
        r"\bweakest\b", r"\bstrongest\b",
    ]

    # Broad / holistic placement advice patterns
    broad_advice_patterns = [
        r"\bwhat should i improve\b", r"\bimprove for placement\b", r"\bhow to prepare\b",
        r"\bpreparation plan\b", r"\breview my (profile|resume)\b", r"\bstrengths? and weakness(es)?\b",
        r"\bplacement readiness\b", r"\bhow is my preparation\b",
    ]

    if any(re.search(pat, q) for pat in broad_advice_patterns):
        # Broad questions benefit from holistic profile, skills, projects, certs, and placements
        return {"profile", "skills", "projects", "certifications", "placements"}

    if any(re.search(pat, q) for pat in placement_intelligence_patterns):
        categories.add("placements")
        categories.add("companies")
        categories.add("profile")
        categories.add("skills")

    if any(re.search(pat, q) for pat in profile_patterns):
        categories.add("profile")

    if any(re.search(pat, q) for pat in skills_patterns):
        categories.add("skills")

    if any(re.search(pat, q) for pat in projects_patterns):
        categories.add("projects")

    if any(re.search(pat, q) for pat in certs_patterns):
        categories.add("certifications")

    if any(re.search(pat, q) for pat in placement_patterns):
        categories.add("placements")
        categories.add("companies")

    # Known target companies inquiry
    from app.services.intent_router import COMMON_COMPANIES
    if any(re.search(rf"\b{re.escape(c)}\b", q) for c in COMMON_COMPANIES):
        categories.add("companies")
        categories.add("placements")

    # Ensure profile identity is included as an anchor when querying personal credentials
    if categories & {"skills", "projects", "certifications"}:
        categories.add("profile")

    # If the user asks general questions about "me" / "my" / "myself" without specific match,
    # include profile as baseline (avoid matching 'me' in 'tell me about <company>')
    if not categories and any(re.search(pat, q) for pat in [r"\babout me\b", r"\babout myself\b", r"\bwho am i\b", r"\bmy\b", r"\bmyself\b"]):
        categories.add("profile")

    return categories


async def get_relevant_personal_context(db: AsyncSession, question: str) -> Dict[str, Any]:
    """
    Fetches structured context only for relevant categories based on deterministic intent.
    """
    categories = analyze_question_intent(question)
    logger.info("Determined personal context categories for query: %s", categories)

    context_data: Dict[str, Any] = {
        "categories": list(categories),
        "profile": None,
        "skills": [],
        "projects": [],
        "certifications": [],
        "companies": [],
        "placements": [],
    }

    if "profile" in categories:
        context_data["profile"] = await get_profile_context(db)

    if "skills" in categories:
        context_data["skills"] = await get_skills_context(db)

    if "projects" in categories:
        context_data["projects"] = await get_projects_context(db)

    if "certifications" in categories:
        context_data["certifications"] = await get_certifications_context(db)

    if "companies" in categories:
        context_data["companies"] = await get_companies_context(db)

    if "placements" in categories:
        context_data["placements"] = await get_placement_context(db)

    return context_data
