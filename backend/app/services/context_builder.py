"""Context builder service.

Combines verified structured personal context from PostgreSQL with
semantic document context from pgvector into a labeled, un-hallucinated context structure.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class BuiltContext:
    prompt_context: str
    structured_categories: List[str] = field(default_factory=list)
    has_structured_data: bool = False
    has_document_data: bool = False


class ContextBuilder:
    """Builds clean, tagged context for LLM ingestion."""

    @staticmethod
    def format_profile_section(profile: Optional[Dict[str, Any]]) -> Optional[str]:
        if not profile:
            return None

        lines = ["[PROFILE]"]
        if "name" in profile:
            lines.append(f"Name: {profile['name']}")
        if "university" in profile:
            lines.append(f"University: {profile['university']}")
        if "degree" in profile:
            lines.append(f"Degree: {profile['degree']}")
        if "branch" in profile:
            lines.append(f"Branch: {profile['branch']}")
        if "graduation_year" in profile:
            lines.append(f"Graduation Year: {profile['graduation_year']}")
        if "cgpa" in profile:
            lines.append(f"CGPA: {profile['cgpa']}/10")
        if "career_goals" in profile:
            lines.append(f"Career Goals (Candidate's future aspiration, not current job role): {profile['career_goals']}")
        if "summary" in profile:
            lines.append(f"Profile Summary: {profile['summary']}")

        return "\n".join(lines) if len(lines) > 1 else None

    @staticmethod
    def format_skills_section(skills: List[Dict[str, Any]]) -> Optional[str]:
        if not skills:
            return None

        lines = ["[SKILLS]"]
        for s in skills:
            cat_str = f" ({s['category']})" if s.get("category") else ""
            prof_str = f" - Level: {s['proficiency']}" if s.get("proficiency") else ""
            lines.append(f"• {s['name']}{cat_str}{prof_str}")

        return "\n".join(lines)

    @staticmethod
    def format_projects_section(projects: List[Dict[str, Any]]) -> Optional[str]:
        if not projects:
            return None

        lines = ["[PROJECTS]"]
        lines.append(
            "  [PROJECT GROUNDING DIRECTIVE: Describe projects strictly and only using the verified facts, "
            "technologies, and description explicitly documented below. "
            "Do NOT infer, assume, extrapolate, or invent features, modules, architecture, or capabilities "
            "(e.g. CRUD operations, course registration, attendance tracking, grading, student authentication, payment gateways) "
            "that are not explicitly written. Never present common or assumed textbook features as implemented features. "
            "If the user asks for implementation details, architecture, modules, or features not documented in the project record, "
            "clearly state that those specific implementation details are not documented in the stored project record, "
            "and invite the user to provide them.]"
        )
        for p in projects:
            p_head = f"• Project: {p['name']}"
            if p.get("role"):
                p_head += f" (Role: {p['role']})"
            if p.get("status"):
                p_head += f" [Status: {p['status']}]"
            lines.append(p_head)

            if p.get("description"):
                lines.append(f"  Description: {p['description']}")
            if p.get("technologies"):
                tech_list = p["technologies"]
                if isinstance(tech_list, list):
                    lines.append(f"  Technologies: {', '.join(str(t) for t in tech_list)}")
                else:
                    lines.append(f"  Technologies: {tech_list}")
            if p.get("url"):
                lines.append(f"  Repository / URL: {p['url']}")
            if p.get("start_date") or p.get("end_date"):
                dates = []
                if p.get("start_date"):
                    dates.append(f"Start: {p['start_date']}")
                if p.get("end_date"):
                    dates.append(f"End: {p['end_date']}")
                lines.append(f"  Timeline: {' to '.join(dates)}")

        return "\n".join(lines)

    @staticmethod
    def format_certifications_section(certs: List[Dict[str, Any]]) -> Optional[str]:
        if not certs:
            return None

        lines = ["[CERTIFICATIONS]"]
        for c in certs:
            issuer_str = f" by {c['issuer']}" if c.get("issuer") else ""
            date_str = f" (Issued: {c['issue_date']})" if c.get("issue_date") else ""
            lines.append(f"• {c['name']}{issuer_str}{date_str}")

        return "\n".join(lines)

    @staticmethod
    def format_placements_section(
        placements: List[Dict[str, Any]], companies: List[Dict[str, Any]]
    ) -> Optional[str]:
        if not placements and not companies:
            return None

        lines = ["[COMPANIES & PLACEMENT DRIVES]"]

        if companies:
            lines.append("Target Companies:")
            for comp in companies:
                parts = []
                if comp.get("location"):
                    parts.append(f"Location: {comp['location']}")
                if comp.get("industry"):
                    parts.append(f"Industry: {comp['industry']}")
                if comp.get("website"):
                    parts.append(f"Website: {comp['website']}")
                if comp.get("notes"):
                    parts.append(f"Overview: {comp['notes']}")
                details = f" ({', '.join(parts)})" if parts else ""
                lines.append(f"  • {comp['name']}{details}")

        if placements:
            lines.append("Placement Opportunities:")
            for pl in placements:
                pl_str = f"  • Company: {pl['company_name']}, Role: {pl['role']}, Status: {pl['status']}"
                if pl.get("compensation"):
                    pl_str += f", Package: {pl['compensation']}"
                if pl.get("tier"):
                    pl_str += f", Tier: {pl['tier']}"
                if pl.get("deadline"):
                    pl_str += f", Deadline: {pl['deadline']}"

                # Structured eligibility evaluation
                if pl.get("eligibility_status"):
                    pl_str += f" | Eligibility: {pl['eligibility_status']}"
                    if pl.get("eligibility_reasons"):
                        pl_str += f" ({'; '.join(pl['eligibility_reasons'])})"

                # Skill matching details
                if "skill_match_percentage" in pl:
                    pl_str += f" | Skill Match: {pl['skill_match_percentage']:.0f}%"
                    if pl.get("matching_skills"):
                        pl_str += f" (Matching: {', '.join(pl['matching_skills'])})"
                    if pl.get("missing_skills"):
                        pl_str += f" (Missing: {', '.join(pl['missing_skills'])})"

                lines.append(pl_str)

        return "\n".join(lines)

    @staticmethod
    def detect_document_type(filename: str, content: str) -> str:
        fn_lower = filename.lower()
        cnt_lower = content.lower()
        if any(w in fn_lower for w in ["resume", "cv", "karthik", "sriram", "application", "biodata"]) or (
            ("education" in cnt_lower or "academics" in cnt_lower)
            and ("skills" in cnt_lower or "projects" in cnt_lower or "certifications" in cnt_lower)
            and ("karthik" in cnt_lower or "cgpa" in cnt_lower or "sriram" in cnt_lower)
        ):
            return "Candidate Resume / Personal Application Document"
        if any(w in fn_lower for w in ["placement", "drive", "brochure", "jd", "job description"]) or (
            "job description" in cnt_lower or "eligibility criteria" in cnt_lower
        ):
            return "Placement / Job Description Document"
        return "Reference Document"

    @staticmethod
    def format_documents_section(sources: List[Any], full_chunks: List[str]) -> Optional[str]:
        if not sources or not full_chunks:
            return None

        lines = ["[DOCUMENT SOURCES]"]
        for src, text in zip(sources, full_chunks):
            page_info = f", Page/Slide {src.page_number}" if src.page_number else ""
            doc_type = ContextBuilder.detect_document_type(src.filename, text)
            header = f"[Source {src.source_index}] (File: {src.filename}{page_info} | Type: {doc_type})"
            if doc_type == "Candidate Resume / Personal Application Document":
                note = (
                    "  [IMPORTANT SOURCE ATTRIBUTION NOTE: This document is Karthik's personal application resume. "
                    "All skills, projects, certifications (e.g. AWS, IBM), and experience in this document describe the candidate Karthik, "
                    "NOT any prospective employer (such as HCLTech) mentioned in the document or filename. "
                    "Do NOT attribute candidate qualifications to the company, and do NOT treat this document as an official company dossier or brochure. "
                    "Do NOT assume, infer, or state that Karthik holds a role or works at this company.]\n"
                )
                lines.append(f"{header}:\n{note}{text}")
            else:
                lines.append(f"{header}:\n{text}")

        return "\n\n".join(lines)

    def build_context(
        self,
        structured_context: Dict[str, Any],
        sources: List[Any],
        chunk_texts: List[str],
    ) -> BuiltContext:
        """
        Combines structured facts and semantic document chunks into a unified prompt context.
        """
        sections: List[str] = []
        structured_categories: List[str] = []
        requested_categories = structured_context.get("categories", [])

        # 1. Format Semantic Document Sources first (as background evidence)
        docs_str = self.format_documents_section(sources, chunk_texts)
        has_documents = bool(docs_str)
        if docs_str:
            sections.append(docs_str)

        # 2. Format Authoritative Structured Sections (adjacent to question for priority)
        profile_str = self.format_profile_section(structured_context.get("profile"))
        if profile_str:
            sections.append(profile_str)
            structured_categories.append("profile")

        skills = structured_context.get("skills", [])
        skills_str = self.format_skills_section(skills)
        if skills_str:
            sections.append(skills_str)
            structured_categories.append("skills")

        projects = structured_context.get("projects", [])
        projects_str = self.format_projects_section(projects)
        if projects_str:
            sections.append(projects_str)
            structured_categories.append("projects")
        elif "projects" in requested_categories:
            sections.append("[PROJECTS]\nNo project records are currently registered in your profile.")

        certs = structured_context.get("certifications", [])
        certs_str = self.format_certifications_section(certs)
        if certs_str:
            sections.append(certs_str)
            structured_categories.append("certifications")
        elif "certifications" in requested_categories:
            sections.append("[CERTIFICATIONS]\nNo certification records are currently registered in your profile.")

        placements = structured_context.get("placements", [])
        companies = structured_context.get("companies", [])
        placements_str = self.format_placements_section(placements, companies)
        if placements_str:
            sections.append(placements_str)
            structured_categories.append("placements")
        elif "placements" in requested_categories or "companies" in requested_categories:
            sections.append("[COMPANIES & PLACEMENT DRIVES]\nNo placement drives are currently registered in the database.")

        has_structured = len(structured_categories) > 0

        prompt_context = "\n\n".join(sections)

        return BuiltContext(
            prompt_context=prompt_context,
            structured_categories=structured_categories,
            has_structured_data=has_structured,
            has_document_data=has_documents,
        )


context_builder = ContextBuilder()
