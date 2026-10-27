"""Placement Parser Service.

Parses unstructured Job Descriptions (JDs), campus placement notices,
and recruitment circulars (from text or uploaded documents) into structured
placement drive records for Placement Intelligence.
"""

from datetime import date, datetime
from decimal import Decimal
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple
import uuid
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.models.document import Document, DocumentChunk
from app.models.placement import PlacementDrive
from app.schemas.placement import ExtractedDriveData
from app.services.intent_router import COMMON_COMPANIES, COMPANY_NAME_MAP, TECH_KEYWORDS, extract_company_entity
from app.services.profile_service import get_default_profile

logger = logging.getLogger(__name__)

MONTH_MAP = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

CANONICAL_BRANCHES = [
    ("CSE", [r"\bcse\b", r"\bcomputer\s*science\b", r"\bcs\b"]),
    ("IT", [r"\bit\b", r"\binformation\s*technology\b"]),
    ("ECE", [r"\bece\b", r"\belectronics\s*(?:and|&)\s*communication\b"]),
    ("EEE", [r"\beee\b", r"\belectrical\s*(?:and|&)\s*electronics\b"]),
    ("Mechanical", [r"\bmech(?:anical)?\b"]),
    ("Civil", [r"\bcivil\b"]),
    ("AI & DS", [r"\bai\s*(?:and|&|\/)\s*ds\b", r"\bdata\s*science\b", r"\bartificial\s*intelligence\b"]),
    ("Cyber Security", [r"\bcyber\s*security\b", r"\binformation\s*security\b"]),
]

COMMON_ROLE_TITLES = [
    "Graduate Engineer Trainee",
    "Associate Software Engineer",
    "Software Engineer",
    "Software Development Engineer",
    "SDE",
    "Junior Software Engineer",
    "System Engineer",
    "Programmer Analyst",
    "Full Stack Developer",
    "Backend Developer",
    "Frontend Developer",
    "AI/ML Engineer",
    "Data Analyst",
    "Cloud Engineer",
    "DevOps Engineer",
    "QA Engineer",
]


class PlacementParserService:
    """Extracts structured placement criteria from circulars and documents."""

    @staticmethod
    def parse_date(date_str: str) -> Optional[date]:
        """Safely parses common date formats in circulars to a date object."""
        if not date_str:
            return None
        cleaned = date_str.strip()

        # ISO format: YYYY-MM-DD
        m_iso = re.search(r"\b(20[2-3][0-9])[-/.](0?[1-9]|1[0-2])[-/.](0?[1-9]|[12][0-9]|3[01])\b", cleaned)
        if m_iso:
            try:
                return date(int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3)))
            except ValueError:
                pass

        # DD-MM-YYYY or DD/MM/YYYY
        m_dmy = re.search(r"\b(0?[1-9]|[12][0-9]|3[01])[-/.](0?[1-9]|1[0-2])[-/.](20[2-3][0-9])\b", cleaned)
        if m_dmy:
            try:
                return date(int(m_dmy.group(3)), int(m_dmy.group(2)), int(m_dmy.group(1)))
            except ValueError:
                pass

        # DDth Month YYYY or Month DD, YYYY
        m_text = re.search(
            r"\b(0?[1-9]|[12][0-9]|3[01])(?:st|nd|rd|th)?\s+([A-Za-z]+)\s+(20[2-3][0-9])\b",
            cleaned,
            re.IGNORECASE,
        )
        if m_text:
            day = int(m_text.group(1))
            month_name = m_text.group(2).lower()
            year = int(m_text.group(3))
            month = MONTH_MAP.get(month_name) or MONTH_MAP.get(month_name[:3])
            if month:
                try:
                    return date(year, month, day)
                except ValueError:
                    pass

        m_text2 = re.search(
            r"\b([A-Za-z]+)\s+(0?[1-9]|[12][0-9]|3[01])(?:st|nd|rd|th)?,?\s+(20[2-3][0-9])\b",
            cleaned,
            re.IGNORECASE,
        )
        if m_text2:
            month_name = m_text2.group(1).lower()
            day = int(m_text2.group(2))
            year = int(m_text2.group(3))
            month = MONTH_MAP.get(month_name) or MONTH_MAP.get(month_name[:3])
            if month:
                try:
                    return date(year, month, day)
                except ValueError:
                    pass

        return None

    def extract_company_name(self, text: str, source_filename: Optional[str] = None) -> Tuple[str, float]:
        """Extracts and normalizes company name from circular text or filename."""
        # 1. Check known entities in filename first
        if source_filename:
            fn_entity = extract_company_entity(source_filename)
            if fn_entity:
                return fn_entity, 0.95

        # 2. Check known entities in full text
        text_entity = extract_company_entity(text)
        if text_entity:
            return text_entity, 0.90

        # 3. Look for explicit company headings
        patterns = [
            r"(?:company\s*name|recruiter|organization|employer|company)[:\s-]+([A-Za-z0-9\s&.,'-]+)",
            r"(?:campus\s*(?:recruitment|placement)\s*notice[:\s-]+)([A-Za-z0-9\s&.,'-]+)",
            r"(?:hiring\s*drive\s*(?:for|by)[:\s-]+)([A-Za-z0-9\s&.,'-]+)",
        ]
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                raw_comp = m.group(1).strip()
                # Clean up noise from raw line
                raw_comp = re.split(r"[\n\r,;|]|\s{2,}|\b(?:recruitment|placement|drive|notice|202[0-9]|batch)\b", raw_comp, flags=re.IGNORECASE)[0].strip()
                raw_comp = re.sub(r"^[-: ]+|[-: ]+$", "", raw_comp)
                if len(raw_comp) >= 2 and len(raw_comp) <= 60:
                    ent = extract_company_entity(raw_comp)
                    return ent or raw_comp, 0.85

        # 4. Fallback from filename if available
        if source_filename:
            clean_fn = re.sub(r"\.[a-zA-Z0-9]+$", "", source_filename)
            clean_fn = re.sub(r"[_-]", " ", clean_fn)
            clean_fn = re.sub(r"\b(?:jd|job|description|circular|drive|placement|notice|campus)\b", "", clean_fn, flags=re.IGNORECASE).strip()
            if clean_fn:
                return clean_fn.title(), 0.70

        return "Campus Recruiter", 0.50

    def extract_role(self, text: str) -> str:
        """Extracts hiring job role or designation."""
        patterns = [
            r"(?:role|designation|position|job\s*title|profile)[:\s-]+([^\n\r,;]+)",
            r"(?:hiring\s*for[:\s-]+)([^\n\r,;]+)",
        ]
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                role_val = m.group(1).strip()
                role_val = re.sub(r"^[-: ]+|[-: ]+$", "", role_val)
                if len(role_val) >= 3 and len(role_val) <= 100:
                    return role_val

        # Match against common known roles
        for common_role in COMMON_ROLE_TITLES:
            if re.search(rf"\b{re.escape(common_role)}\b", text, re.IGNORECASE):
                return common_role

        return "Software Engineer"

    def extract_min_cgpa(self, text: str) -> Optional[float]:
        """Extracts minimum qualifying CGPA."""
        patterns = [
            r"(?:min(?:imum)?\s+)?cgpa\s*(?:criteria|cutoff)?[:\s=]+(?:>=|>|min)?\s*([0-9](?:\.[0-9]{1,2})?)",
            r"(?:cutoff|criteria)[:\s=]+(?:>=|>|min)?\s*([0-9](?:\.[0-9]{1,2})?)\s*(?:cgpa|gpa)",
            r"\b([0-9]\.[0-9]{1,2})\s*(?:cgpa|gpa)\b",
        ]
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                try:
                    val = float(m.group(1))
                    if 4.0 <= val <= 10.0:
                        return val
                except (ValueError, TypeError):
                    pass

        # Percentage format (e.g. 70% or 60% throughout -> convert to CGPA / 10 if standard)
        pct_match = re.search(r"([6-9][0-9])\s*%\s*(?:throughout|in\s*academics|and\s*above|criteria)?", text, re.IGNORECASE)
        if pct_match:
            try:
                pct = float(pct_match.group(1))
                return round(pct / 10.0, 1)
            except (ValueError, TypeError):
                pass

        return None

    def extract_eligible_branches(self, text: str) -> Optional[List[str]]:
        """Identifies eligible academic departments."""
        matched: List[str] = []
        for branch_name, patterns in CANONICAL_BRANCHES:
            if any(re.search(p, text, re.IGNORECASE) for p in patterns):
                matched.append(branch_name)

        if not matched:
            if re.search(r"\bcircuit\s*branches\b", text, re.IGNORECASE):
                return ["CSE", "IT", "ECE", "EEE"]
            if re.search(r"\ball\s*(?:branches|departments|disciplines|streams)\b", text, re.IGNORECASE):
                return ["All Engineering Branches"]
            return None

        return matched

    def extract_graduation_year(self, text: str) -> Optional[int]:
        """Identifies targeted graduation batch year."""
        patterns = [
            r"(?:batch|graduating|passout|class|year\s*of\s*passing)[:\s=]+(?:of\s+)?(20[2-3][0-9])",
            r"\b(20[2-3][0-9])\s*(?:batch|graduating|passout|graduates)\b",
            r"\b(?:class\s*of\s*)(20[2-3][0-9])\b",
        ]
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                try:
                    return int(m.group(1))
                except (ValueError, TypeError):
                    pass
        return None

    def extract_compensation(self, text: str) -> Optional[str]:
        """Extracts salary package or CTC information."""
        # 1. First look for explicit LPA / Lakhs pattern (e.g. "5.5 LPA", "12 Lakhs per annum")
        m_lpa = re.search(r"\b([0-9]+(?:\.[0-9]+)?\s*(?:lpa|lakhs?(?:\s*per\s*annum)?|inr(?:\s*[0-9,]+)?))\b", text, re.IGNORECASE)
        if m_lpa:
            return m_lpa.group(1).strip()

        # 2. Look for labelled lines like "Annual CTC: 5.5 LPA" or "CTC: 6,00,000" where the value contains digits
        patterns = [
            r"(?:annual\s*ctc|ctc|package|compensation|salary|stipend)[:\s=]+([^\n\r;]+)",
        ]
        for pat in patterns:
            for m in re.finditer(pat, text, re.IGNORECASE):
                comp = m.group(1).strip()
                comp = re.split(r"[\n\r;]|(?:\s{2,})", comp)[0].strip()
                # Skip non-informative section headings like "& Package" or "Details"
                if re.search(r"^\s*(&|and)?\s*(package|structure|breakup|details|criteria)\b", comp, re.IGNORECASE):
                    continue
                # Require at least one digit or currency symbol
                if any(ch.isdigit() for ch in comp) and 2 <= len(comp) <= 80:
                    return comp

        return None

    def extract_employment_type(self, text: str) -> Optional[str]:
        """Extracts employment type (full-time, internship, intern+fte)."""
        if re.search(r"\b(?:internship\s*\+\s*fte|intern\s*\+\s*full\s*time)\b", text, re.IGNORECASE):
            return "Internship + FTE"
        if re.search(r"\bfull[- ]time\b", text, re.IGNORECASE):
            return "Full-Time"
        if re.search(r"\binternship\b", text, re.IGNORECASE):
            return "Internship"
        return "Full-Time"

    def extract_location(self, text: str) -> Optional[str]:
        """Extracts work location / cities."""
        loc_patterns = [
            r"(?:work\s*)?location[:\s=]+([^\n\r;]+)",
            r"(?:job\s*location)[:\s=]+([^\n\r;]+)",
        ]
        for pat in loc_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                loc = m.group(1).strip()
                loc = re.split(r"[\n\r;]|(?:\s{2,})", loc)[0].strip()
                if len(loc) >= 2 and len(loc) <= 80:
                    return loc

        cities = ["Bangalore", "Bengaluru", "Chennai", "Hyderabad", "Noida", "Gurgaon", "Gurugram", "Pune", "Mumbai", "Pan India", "Remote", "Hybrid"]
        found = [c for c in cities if re.search(rf"\b{c}\b", text, re.IGNORECASE)]
        if found:
            return " / ".join(found[:3])
        return None

    def extract_deadline(self, text: str) -> Optional[date]:
        """Extracts application registration deadline."""
        patterns = [
            r"(?:last\s*date(?: to apply| to register)?|deadline|apply\s*before|closing\s*date)[:\s=]+([^\n\r;]+)",
        ]
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                d = self.parse_date(m.group(1))
                if d:
                    return d
        return None

    def extract_backlog_policy(self, text: str) -> bool:
        """Determines whether active backlogs/arrears are permitted."""
        if re.search(r"\b(?:no\s*(?:active|standing|current)?\s*backlogs?|0\s*backlogs?|no\s*arrears?)\b", text, re.IGNORECASE):
            return False
        m_allow = re.search(r"\b([1-9])\s*(?:standing|active)?\s*backlog(?:s)?\s*(?:allowed|permitted)\b", text, re.IGNORECASE)
        if m_allow:
            return True
        return False

    def extract_selection_process(self, text: str) -> Optional[List[str]]:
        """Extracts ordered recruitment interview rounds."""
        round_matches: List[str] = []

        # Check numbered rounds under selection process
        process_block = re.search(r"(?:selection\s*(?:process|rounds?)|interview\s*rounds?|hiring\s*process)[:\s-]+([\s\S]{10,400}?)(?:\n\s*\n|[A-Z][a-z]+:|$)", text, re.IGNORECASE)
        search_scope = process_block.group(1) if process_block else text

        lines = search_scope.splitlines()
        for line in lines:
            cleaned = line.strip()
            # Match "1. Online Test", "Round 1: Coding", "• Technical Interview"
            m_round = re.search(r"^(?:(?:round\s*)?[0-9]+[.:)]|•|\*|-)?\s*([A-Za-z0-9\s/&()-]+(?:assessment|test|interview|round|discussion|evaluation)[A-Za-z0-9\s/&()-]*)", cleaned, re.IGNORECASE)
            if m_round:
                round_title = m_round.group(1).strip()
                if 4 <= len(round_title) <= 80 and round_title not in round_matches:
                    round_matches.append(round_title)

        if not round_matches:
            # Fallback to standard rounds if mentioned in text
            default_rounds = [
                ("Online Assessment / Aptitude", [r"\bonline\s*(?:assessment|test|exam)\b", r"\baptitude\s*test\b"]),
                ("Technical Interview", [r"\btechnical\s*(?:interview|round)\b", r"\bcoding\s*round\b"]),
                ("HR Interview", [r"\bhr\s*(?:interview|round)\b", r"\bmanagerial\s*round\b"]),
            ]
            for r_name, r_pats in default_rounds:
                if any(re.search(p, text, re.IGNORECASE) for p in r_pats):
                    round_matches.append(r_name)

        return round_matches if round_matches else None

    def extract_skills(self, text: str) -> Tuple[List[str], List[str]]:
        """Extracts required and preferred skills using known technical terminology."""
        req_skills: Set[str] = set()
        pref_skills: Set[str] = set()

        # Separate sections if present
        req_block = ""
        pref_block = ""

        m_req = re.search(r"(?:required\s*skills|mandatory\s*skills|key\s*skills|requirements|technical\s*skills)[:\s-]+([\s\S]{10,400}?)(?:\n\s*\n|[A-Z][a-z]+:|$)", text, re.IGNORECASE)
        if m_req:
            req_block = m_req.group(1).lower()

        m_pref = re.search(r"(?:preferred\s*skills|good\s*to\s*have|desirable)[:\s-]+([\s\S]{10,300}?)(?:\n\s*\n|[A-Z][a-z]+:|$)", text, re.IGNORECASE)
        if m_pref:
            pref_block = m_pref.group(1).lower()

        for tech in TECH_KEYWORDS:
            pat = rf"\b{re.escape(tech)}\b"
            display_tech = tech.title() if len(tech) > 3 else tech.upper()
            if tech.lower() in ["fastapi", "postgresql", "docker", "kubernetes", "react", "nextjs", "sqlite", "graphql", "mongodb"]:
                display_tech = {
                    "fastapi": "FastAPI",
                    "postgresql": "PostgreSQL",
                    "docker": "Docker",
                    "kubernetes": "Kubernetes",
                    "react": "React",
                    "nextjs": "Next.js",
                    "sqlite": "SQLite",
                    "graphql": "GraphQL",
                    "mongodb": "MongoDB",
                }.get(tech.lower(), display_tech)

            if req_block and re.search(pat, req_block):
                req_skills.add(display_tech)
            elif pref_block and re.search(pat, pref_block):
                pref_skills.add(display_tech)
            elif re.search(pat, text, re.IGNORECASE):
                req_skills.add(display_tech)

        return sorted(list(req_skills)), sorted(list(pref_skills))

    def extract_tier(self, text: str, compensation: Optional[str] = None) -> Optional[str]:
        """Identifies placement tier category."""
        if re.search(r"\bsuper\s*dream\b", text, re.IGNORECASE):
            return "Super Dream"
        if re.search(r"\bdream\b", text, re.IGNORECASE):
            return "Dream"
        if re.search(r"\bregular\b", text, re.IGNORECASE):
            return "Regular"

        # Infer from compensation if possible (e.g. 10 LPA -> Super Dream, 5 LPA -> Dream)
        if compensation:
            m_lpa = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*lpa", compensation, re.IGNORECASE)
            if m_lpa:
                try:
                    val = float(m_lpa.group(1))
                    if val >= 10.0:
                        return "Super Dream"
                    elif val >= 5.0:
                        return "Dream"
                    else:
                        return "Regular"
                except (ValueError, TypeError):
                    pass

        return None

    def extract_from_text(
        self,
        text: str,
        source_filename: Optional[str] = None,
        source_document_id: Optional[uuid.UUID] = None,
    ) -> ExtractedDriveData:
        """
        Parses unstructured text into a validated ExtractedDriveData object.
        """
        company_name, conf = self.extract_company_name(text, source_filename)
        role = self.extract_role(text)
        min_cgpa = self.extract_min_cgpa(text)
        eligible_branches = self.extract_eligible_branches(text)
        graduation_year = self.extract_graduation_year(text)
        compensation = self.extract_compensation(text)
        employment_type = self.extract_employment_type(text)
        location = self.extract_location(text)
        deadline = self.extract_deadline(text)
        backlog_allowed = self.extract_backlog_policy(text)
        selection_process = self.extract_selection_process(text)
        req_skills, pref_skills = self.extract_skills(text)
        tier = self.extract_tier(text, compensation)

        # Build clean notes summary
        notes_lines = []
        if source_filename:
            notes_lines.append(f"Parsed from document: {source_filename}")
        if compensation:
            notes_lines.append(f"Package: {compensation}")
        if location:
            notes_lines.append(f"Location: {location}")
        if selection_process:
            notes_lines.append(f"Rounds: {' → '.join(selection_process)}")
        notes = " | ".join(notes_lines) if notes_lines else None

        return ExtractedDriveData(
            company_name=company_name,
            role=role,
            status="interested",
            deadline=deadline,
            compensation=compensation,
            employment_type=employment_type,
            location=location,
            notes=notes,
            min_cgpa=min_cgpa,
            eligible_branches=eligible_branches,
            graduation_year=graduation_year,
            required_skills=req_skills if req_skills else None,
            preferred_skills=pref_skills if pref_skills else None,
            backlog_allowed=backlog_allowed,
            selection_process=selection_process,
            tier=tier,
            confidence_score=conf,
            source_document_id=source_document_id,
            source_filename=source_filename,
        )

    async def extract_from_document(
        self,
        db: AsyncSession,
        document_id: uuid.UUID,
    ) -> ExtractedDriveData:
        """
        Extracts placement drive requirements directly from an ingested document record.
        """
        doc_res = await db.execute(select(Document).where(Document.id == document_id))
        doc = doc_res.scalars().first()
        if not doc:
            raise ValueError(f"Document with ID {document_id} not found.")

        # Load chunks in order
        chunks_res = await db.execute(
            select(DocumentChunk.content)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index.asc())
        )
        chunk_texts = chunks_res.scalars().all()
        full_text = "\n\n".join(chunk_texts) if chunk_texts else ""

        if not full_text:
            raise ValueError(f"Document '{doc.original_filename}' has no chunk contents available.")

        return self.extract_from_text(
            text=full_text,
            source_filename=doc.original_filename,
            source_document_id=doc.id,
        )

    async def create_drive_from_extracted(
        self,
        db: AsyncSession,
        drive_data: ExtractedDriveData,
        profile_id: Optional[uuid.UUID] = None,
        create_company_if_missing: bool = True,
    ) -> PlacementDrive:
        """
        Persists extracted drive data to PostgreSQL:
        - Checks if Company exists by name (case-insensitive); creates if missing.
        - Attaches to current user's profile.
        - Inserts new PlacementDrive record with all extracted intelligence fields.
        """
        target_profile_id = profile_id
        if not target_profile_id:
            profile = await get_default_profile(db)
            if not profile:
                raise ValueError("No profile exists in database. Please create a profile first.")
            target_profile_id = profile.id

        comp_name = drive_data.company_name.strip()
        comp_res = await db.execute(
            select(Company).where(Company.name.ilike(comp_name))
        )
        company = comp_res.scalars().first()

        if not company:
            if not create_company_if_missing:
                raise ValueError(f"Company '{comp_name}' does not exist in the database.")
            company = Company(
                name=comp_name,
                location=drive_data.location,
                notes=f"Auto-created from placement circular: {drive_data.source_filename or 'document import'}",
            )
            db.add(company)
            await db.commit()
            await db.refresh(company)

        # Create PlacementDrive
        placement = PlacementDrive(
            profile_id=target_profile_id,
            company_id=company.id,
            role=drive_data.role,
            status=drive_data.status or "interested",
            deadline=drive_data.deadline,
            compensation=drive_data.compensation,
            employment_type=drive_data.employment_type,
            location=drive_data.location,
            notes=drive_data.notes,
            min_cgpa=Decimal(str(drive_data.min_cgpa)) if drive_data.min_cgpa is not None else None,
            eligible_branches=drive_data.eligible_branches,
            graduation_year=drive_data.graduation_year,
            required_skills=drive_data.required_skills,
            preferred_skills=drive_data.preferred_skills,
            backlog_allowed=drive_data.backlog_allowed,
            selection_process=drive_data.selection_process,
            tier=drive_data.tier,
        )
        db.add(placement)
        await db.commit()

        # Re-fetch with company eager-loaded
        query = (
            select(PlacementDrive)
            .options(selectinload(PlacementDrive.company))
            .where(PlacementDrive.id == placement.id)
        )
        refreshed = await db.execute(query)
        return refreshed.scalars().first()


placement_parser_service = PlacementParserService()
