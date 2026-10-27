import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session
from app.models.conversation import Conversation, Message
from app.models.document import Document, DocumentChunk
from app.services.context_builder import context_builder
from app.services.embedding_service import embedding_provider
from app.services.intent_router import IntentCategory, IntentRoutingResult, extract_company_entity, intent_router
from app.services.llm.base import ChatMessage
from app.services.llm.factory import get_llm_provider
from app.services.personal_context import get_relevant_personal_context

logger = logging.getLogger(__name__)


@dataclass
class SourceCitation:
    source_index: int
    document_id: str
    filename: str
    page_number: Optional[int]
    chunk_index: int
    snippet: str
    similarity_score: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        valid_page = (
            int(self.page_number)
            if (self.page_number is not None and isinstance(self.page_number, (int, float)) and self.page_number > 0)
            else None
        )
        score = (
            round(float(self.similarity_score), 4)
            if (self.similarity_score is not None and isinstance(self.similarity_score, (int, float)))
            else None
        )
        return {
            "source_index": self.source_index,
            "document_id": self.document_id,
            "filename": self.filename,
            "page_number": valid_page,
            "chunk_index": self.chunk_index,
            "snippet": self.snippet,
            "similarity_score": score,
        }


def deduplicate_citations(citations: List[SourceCitation]) -> List[SourceCitation]:
    """
    Avoid duplicate citations:
    Preserves unique citations by (filename, valid_page_number),
    retaining the highest similarity score entry.
    """
    if not citations:
        return []

    seen: Dict[Any, SourceCitation] = {}
    for c in citations:
        valid_page = (
            int(c.page_number)
            if (c.page_number is not None and isinstance(c.page_number, (int, float)) and c.page_number > 0)
            else None
        )
        key = (c.filename.lower(), valid_page)
        if key not in seen:
            seen[key] = c
        else:
            existing = seen[key]
            existing_score = existing.similarity_score if existing.similarity_score is not None else -1.0
            new_score = c.similarity_score if c.similarity_score is not None else -1.0
            if new_score > existing_score:
                seen[key] = c

    deduped: List[SourceCitation] = []
    for idx, c in enumerate(seen.values(), start=1):
        deduped.append(
            SourceCitation(
                source_index=idx,
                document_id=c.document_id,
                filename=c.filename,
                page_number=(
                    int(c.page_number)
                    if (c.page_number is not None and isinstance(c.page_number, (int, float)) and c.page_number > 0)
                    else None
                ),
                chunk_index=c.chunk_index,
                snippet=c.snippet,
                similarity_score=c.similarity_score,
            )
        )
    return deduped


@dataclass
class RAGResponse:
    query: str
    answer: str
    sources: List[SourceCitation]
    model: str
    structured_sources: List[str] = field(default_factory=list)
    context_used: bool = True
    grounded: bool = True
    intent: Optional[str] = None
    sources_used: List[str] = field(default_factory=list)


CASUAL_SYSTEM_PROMPT = """You are Karthik AI, a friendly, intelligent personal assistant created for Karthik. The user speaking with you is Karthik himself.
Respond naturally, warmly, politely, and concisely to greetings, acknowledgments, pleasantries, or casual conversation.
Greet Karthik by name (e.g. "Hello Karthik!" or "Hi Karthik!") and offer to help him with his personal profile, uploaded documents, placement preparation, or technical engineering questions.
Do not invent false documents or profile claims."""

PERSONAL_PROFILE_SYSTEM_PROMPT = """You are Karthik AI, a personal assistant for Karthik. The user speaking with you is Karthik himself.
Answer the user's question directly, concisely, and factually using the verified profile context below.

Context Guidelines:
- Identity ("who am i", "what is my name", "my name"): The user is Karthik. State his name and academic profile directly from [PROFILE].
- Answer the specific question asked using the exact field from [PROFILE], [SKILLS], [PROJECTS], or [CERTIFICATIONS].
- If asked about university or college, state the university name from [PROFILE].
- If asked about CGPA, state the CGPA from [PROFILE].
- If asked about degree or branch, state the degree and branch from [PROFILE].
- If asked about leadership or ACM role, cite the summary under [PROFILE].
- If asked about skills, cite technical skills directly from [SKILLS].
- If asked about projects:
  * When describing a project, cite ONLY the verified description, role, status, and technologies explicitly listed under [PROJECTS] and verified project documentation.
  * Do NOT infer, assume, or invent features, modules, architecture, or capabilities (such as CRUD operations, course registrations, attendance tracking, grading, student authentication, fee management, etc.) that are not explicitly written.
  * Never present common, typical, or textbook project features as implemented features.
  * Do NOT infer or assume project technologies from career goals.
  * If the user requests implementation details, architecture, modules, or features not stored in the project record or uploaded documentation, clearly state that those specific details are not documented in your stored project record, and invite the user to provide them.
- If asked about certifications, cite certifications directly from [CERTIFICATIONS].
- If the requested detail is completely absent from all sections of the context, state that there is not enough verified information in your profile.
- Do not invent, assume, or hallucinate facts not present in the context.
"""

DOCUMENT_RAG_SYSTEM_PROMPT = """You are Karthik AI, an intelligent personal assistant for Karthik. The user speaking with you is Karthik himself.
Answer the user's question strictly and factually based on the retrieved document context below.

Context Guidelines:
- Cite facts directly from the provided document excerpts.
- Source Attribution: Distinguish candidate resumes from official company documents. Candidate application documents describe Karthik's background, NOT the company's offerings.
- If the question cannot be answered from the provided excerpts, state clearly: "I couldn't find relevant information in your uploaded documents. Based on your personal profile and uploaded documents, there is not enough information to answer this question."
- Do not fabricate or extrapolate information beyond what is stated in the documents.
"""

PLACEMENT_SYSTEM_PROMPT = """You are Karthik AI, an intelligent personal assistant and placement advisor for Karthik. The user speaking with you is Karthik himself.
Answer placement, eligibility, company, and recruitment preparation questions using the verified placement data and candidate profile below.

Context Guidelines:
- Role & Employment: NEVER claim, infer, or state that Karthik holds a role at a company or works in a specific role (such as 'Senior AI Architect') unless explicitly stated in a verified job offer or placement record.
- Career Goals vs Job Role: 'Career Goals' represents Karthik's personal future ambition, NOT a current job title, role held, or role offered at any company.
- For eligibility questions, state clearly whether Karthik is ELIGIBLE or NOT ELIGIBLE, citing specific criteria (CGPA, department, graduation year, backlogs) ONLY from verified placement drive data in [COMPANIES & PLACEMENT DRIVES]. Do NOT assert eligibility unless a drive record is present.
- If no placement drives are registered in the database, clearly state that no placement drives are currently loaded. Do NOT invent company drives, eligibility, or salary packages.
- Source Attribution (Candidate Resume vs Company Documents):
  * When a retrieved document is a candidate resume or application document (such as 'KARTHIK_SRIRAM_S_HCLTech.pdf'), all skills, projects, and certifications in that document belong to Karthik, NOT to the company (e.g. HCLTech).
  * Do NOT claim that the company offers, requires, or holds certifications like AWS or IBM simply because they appear on Karthik's resume.
  * If official company brochures or drive records are not in the database, state clearly that you do not have official company information.
- Target Company Follow-ups & General Inquiries:
  * When asked general company questions (e.g. 'Tell me about [Company]'), provide a concise company overview ONLY from verified company records or official company documents in the context.
  * Distinguish general company information from campus placement details, official job descriptions, and candidate-specific eligibility.
  * If official placement information or job descriptions are missing, explicitly say so and offer helpful next steps (e.g. checking the college placement notice or uploading the official job description).
  * When an [ACTIVE SUBJECT / TARGET COMPANY] is indicated, focus preparation advice on that target company based on Karthik's actual verified profile skills (e.g., core CS fundamentals, DSA, programming languages).
  * If official company-specific interview rounds are not in the database, explicitly state that official round details are not recorded and provide clearly labeled general placement preparation recommendations without presenting them as verified company-specific guidance.
"""

GENERAL_KNOWLEDGE_SYSTEM_PROMPT = """You are Karthik AI, an intelligent, helpful, and technically adept AI assistant.
Provide clear, accurate, well-structured, and concise explanations of software engineering, computer science, and technical concepts.
Use concise explanations, bullet points, and code examples when helpful.
Do not refer to the user's personal documents or personal profile unless explicitly requested."""

GROUNDING_SYSTEM_PROMPT = """You are Karthik AI, an intelligent personal assistant for Karthik. The user speaking with you is Karthik himself.
Answer the user's questions directly, factually, and helpfully using the verified context below.

Context Guidelines:
- Identity ("who am i", "my name"): The user is Karthik. State his name and core academic profile directly from [PROFILE].
- Answer direct factual questions (CGPA, university, degree, ACM role, skills, completed projects, certifications, placement drives) immediately using the verified context.
- Projects & Technologies: Only cite projects, descriptions, and technologies explicitly listed under [PROJECTS].
  * Do NOT infer, assume, or fabricate features, modules, architecture, or capabilities (e.g. CRUD operations, course registration, attendance records, grading, authentication) not in the stored record.
  * Never present common or assumed textbook features as implemented features.
  * Do NOT infer project technologies from 'Career Goals'.
  * If the user requests implementation details, architecture, or features not documented in the project record or uploaded documents, state that those details are not documented in the project record, and invite the user to provide them.
  * If [PROJECTS] indicates no records are registered, state that no project records are registered in your profile.
- Source Attribution: Candidate resumes describe Karthik, not prospective employers. Do not attribute candidate certifications or skills to target employers.
- When an [ACTIVE SUBJECT / TARGET COMPANY] is indicated in a follow-up, focus recommendations on that subject without inventing company-specific rounds.
- If the requested topic or credential is not present in the context, state: 'Based on your personal profile and uploaded documents, there is not enough information to answer this question.'
- In multi-turn chat, resolve conversational follow-up questions using the relevant facts in the verified context and conversation history.
"""


# Trusted official reference registry for known campus recruiters:
TRUSTED_OFFICIAL_COMPANIES: Dict[str, Dict[str, str]] = {
    "hcltech": {
        "name": "HCLTech",
        "official_url": "https://www.hcltech.com/about-us",
        "overview": (
            "HCLTech is a leading global technology company headquartered in Noida, Uttar Pradesh, India, "
            "with a global workforce of over 220,000 across 60 countries. It delivers industry-leading capabilities "
            "centered around digital, engineering, cloud, and AI solutions, software products, and IT infrastructure services."
        ),
    },
}


class RAGService:
    def __init__(self):
        self.llm_provider = get_llm_provider()

    async def retrieve_relevant_chunks(
        self,
        db: AsyncSession,
        query: str,
        top_k: int = settings.rag_top_k,
        similarity_threshold: float = settings.rag_similarity_threshold,
        document_id: Optional[uuid.UUID] = None,
    ) -> List[SourceCitation]:
        """
        Embeds query and performs pgvector exact cosine similarity search.
        """
        # 1. Generate query embedding
        query_vectors = embedding_provider.embed_texts([query])
        if not query_vectors:
            return []
        query_vector = query_vectors[0]

        # 2. pgvector cosine distance: dc.embedding.cosine_distance(query_vector)
        # Cosine similarity = 1 - cosine_distance
        cosine_distance_col = DocumentChunk.embedding.cosine_distance(query_vector)

        stmt = (
            select(
                DocumentChunk,
                Document.original_filename,
                cosine_distance_col.label("distance"),
            )
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(Document.status == "completed")
        )

        if document_id:
            stmt = stmt.where(DocumentChunk.document_id == document_id)

        # Ordering by distance ascending (closest first)
        stmt = stmt.order_by(cosine_distance_col.asc()).limit(top_k * 2)

        results = await db.execute(stmt)
        rows = results.all()

        citations: List[SourceCitation] = []
        source_idx = 1

        for chunk, orig_filename, distance in rows:
            similarity = 1.0 - float(distance) if distance is not None else 0.0
            if similarity < similarity_threshold:
                continue

            # Format snippet (max 300 chars for citation overview)
            snippet = chunk.content.strip()
            if len(snippet) > 300:
                snippet = snippet[:297] + "..."

            citations.append(
                SourceCitation(
                    source_index=source_idx,
                    document_id=str(chunk.document_id),
                    filename=orig_filename,
                    page_number=chunk.page_number,
                    chunk_index=chunk.chunk_index,
                    snippet=snippet,
                    similarity_score=similarity,
                )
            )
            source_idx += 1
            if len(citations) >= top_k:
                break

        return citations

    async def _check_company_grounding(
        self,
        entity: str,
        query: str,
        structured_context: Dict[str, Any],
        sources: List[SourceCitation],
        db: Optional[AsyncSession] = None,
    ) -> Optional[str]:
        """
        Enforces strict grounding for queries targeting a specific company entity:
        1. Checks whether verified company information exists (company record, placement drive, or official company doc).
        2. If candidate application documents (e.g. KARTHIK_SRIRAM_S_HCLTech.pdf) are present, ensures they are not
           treated as official company documentation and that no role (e.g. Senior AI Architect) is inferred.
        3. Returns deterministic grounded text if reliable company data is missing, or None if verified data exists.
        """
        norm_entity = entity.lower().strip()

        # Check if database has company record
        matched_companies = [
            c for c in structured_context.get("companies", [])
            if norm_entity in c.get("name", "").lower()
        ]
        has_company_record = len(matched_companies) > 0

        # Check if database has placement drive
        matched_drives = [
            pl for pl in structured_context.get("placements", [])
            if norm_entity in pl.get("company_name", "").lower()
        ]
        has_placement_drive = len(matched_drives) > 0

        # Check document types in retrieved sources (filtered for relevance to this entity)
        official_company_docs: List[SourceCitation] = []
        resume_docs: List[SourceCitation] = []
        for s in sources:
            is_entity_related = norm_entity in s.filename.lower() or norm_entity in s.snippet.lower()
            if not is_entity_related:
                continue
            doc_type = context_builder.detect_document_type(s.filename, s.snippet)
            if doc_type == "Candidate Resume / Personal Application Document":
                resume_docs.append(s)
            else:
                official_company_docs.append(s)

        # Inspect database for any documents with filenames referencing this entity
        if db:
            doc_stmt = select(Document).where(
                Document.status == "completed",
                Document.original_filename.ilike(f"%{norm_entity}%"),
            )
            doc_res = await db.execute(doc_stmt)
            for d in doc_res.scalars().all():
                d_type = context_builder.detect_document_type(d.original_filename, "")
                if not any(s.filename == d.original_filename for s in sources):
                    fake_c = SourceCitation(
                        source_index=len(sources) + 1,
                        document_id=str(d.id),
                        filename=d.original_filename,
                        page_number=None,
                        chunk_index=0,
                        snippet="",
                        similarity_score=None,
                    )
                    if d_type == "Candidate Resume / Personal Application Document":
                        resume_docs.append(fake_c)
                    else:
                        sources.append(fake_c)
                        official_company_docs.append(fake_c)

        q_lower = query.lower()

        # Sub-case A: Interview preparation / selection process questions
        is_prep_query = any(re.search(pat, q_lower) for pat in [
            r"\bwhat should i prepare\b",
            r"\bhow should i prepare\b",
            r"\bhow to prepare\b",
            r"\bwhat to prepare\b",
            r"\bpreparation\b",
            r"\binterview prep(aration)?\b",
            r"\bselection (process|rounds?)\b",
            r"\binterview rounds?\b",
            r"\bwhat should i study\b",
            r"\bwhat should i focus on\b",
            r"\bhiring (process|rounds?)\b",
            r"\bwhat are the rounds\b",
        ])
        if is_prep_query and not has_placement_drive:
            profile = structured_context.get("profile") or {}
            degree = profile.get("degree", "B.E.")
            branch = profile.get("branch", "Computer Science and Engineering")
            return (
                f"Official company-specific interview rounds and job requirements for {entity} are not recorded in your placement database.\n\n"
                f"[General Placement Preparation Advice - Not Company-Specific]\n"
                f"As a {degree} student in {branch}, focus on core technical campus recruitment standards:\n"
                f"• Data Structures & Algorithms: Arrays, strings, linked lists, trees, searching, sorting, and time/space complexity analysis.\n"
                f"• Core CS Fundamentals: Database Management Systems (DBMS / SQL queries, schema design), Operating Systems, Computer Networks, and Object-Oriented Programming.\n"
                f"• Programming Languages: Problem-solving and coding practice in your core languages (such as Java or Python).\n"
                f"• Aptitude & Soft Skills: Quantitative aptitude, logical reasoning, and verbal communication.\n\n"
                f"Note: No active job-specific role or placement record for {entity} is recorded in your profile. "
                f"No specialized or senior job roles are assumed or inferred.\n\n"
                f"• Recommended Next Steps:\n"
                f"  1. Check your college placement portal or TPO notice for the official {entity} campus drive circular and hiring rounds.\n"
                f"  2. Upload the official {entity} Job Description (JD) into Knowledge Documents for tailored round-by-round guidance."
            )

        # Sub-case B: Specific eligibility queries for this company
        is_elig_query = any(re.search(pat, q_lower) for pat in [
            r"\bam i eligible\b",
            r"\beligib(le|ility)\b",
            r"\bqualif(y|ied)\b",
            r"\bcan i apply\b",
            r"\bopen drives?\b",
            r"\bapplication deadline\b",
        ])
        if is_elig_query and not has_placement_drive:
            return (
                f"There are currently no placement drives loaded for {entity} in the placement database. "
                f"Therefore, I cannot verify company eligibility or list recruitment criteria for {entity} yet.\n\n"
                f"• Recommended Next Steps:\n"
                f"  1. Check your college placement notice or TPO circular for {entity} eligibility criteria (minimum CGPA, permitted branches, and backlog policies).\n"
                f"  2. Add the {entity} drive details into Placement Intelligence to automatically verify your eligibility."
            )

        # If full official placement drives or official placement documents exist, allow LLM synthesis
        if has_placement_drive or (official_company_docs and any(
            "job description" in s.snippet.lower() or "placement" in s.snippet.lower() or "drive" in s.snippet.lower()
            for s in official_company_docs
        )):
            return None

        # Candidate resume distinction notice (if candidate resume(s) referencing this entity are present)
        resume_notice = ""
        if resume_docs:
            filenames = ", ".join(sorted(set(s.filename for s in resume_docs)))
            resume_notice = (
                f"\n• Candidate Document Distinction: The uploaded file ({filenames}) is your personal candidate "
                f"application resume detailing your academic credentials and projects. "
                f"It is not an official company brochure or corporate document from {entity}, and is excluded from company citations."
            )

        # Determine general company overview and official source
        company_overview_text = ""
        official_source_label = ""
        live_retrieval_notice = ""
        next_steps_source_hint = f"Upload the official {entity} Job Description (JD) or campus brochure in Knowledge Documents."

        # Case 1: Uploaded official company documentation exists
        if official_company_docs:
            doc_snippets = [s.snippet for s in official_company_docs if s.snippet]
            company_overview_text = " ".join(doc_snippets)[:400] if doc_snippets else "Referenced in uploaded official company documentation."
            official_source_label = "from uploaded official company documentation"
            next_steps_source_hint = f"Review the uploaded official {entity} documentation or upload an updated JD."

        # Case 2: Verified company record exists in PostgreSQL
        elif matched_companies:
            comp = matched_companies[0]
            overview_parts = []
            if comp.get("industry"):
                overview_parts.append(f"Industry: {comp['industry']}")
            if comp.get("location"):
                overview_parts.append(f"Location: {comp['location']}")
            if comp.get("website"):
                overview_parts.append(f"Website: {comp['website']}")
            if comp.get("notes"):
                overview_parts.append(f"Overview: {comp['notes']}")
            company_overview_text = f"{comp['name']} is recorded in your database: " + (" | ".join(overview_parts) if overview_parts else "Registered as a target company in your placement database.")
            official_source_label = "from verified company record"
            next_steps_source_hint = f"Upload the official {entity} Job Description (JD) into Knowledge Documents to evaluate role criteria."

        # Case 3: Trusted official company source available (e.g. HCLTech: https://www.hcltech.com/about-us)
        elif norm_entity in TRUSTED_OFFICIAL_COMPANIES:
            trusted_info = TRUSTED_OFFICIAL_COMPANIES[norm_entity]
            trusted_name = trusted_info["name"]
            trusted_url = trusted_info["official_url"]
            company_overview_text = trusted_info["overview"]
            official_source_label = f"from trusted official source: {trusted_url}"
            live_retrieval_notice = (
                f"\n• Live Web Retrieval Status: Live external web retrieval is not supported in this offline local system. "
                f"To keep corporate information current or ingest updated material, you can ingest the official company webpage "
                f"({trusted_url}) or placement brochure into Knowledge Documents."
            )
            next_steps_source_hint = f"Ingest the official {trusted_name} webpage ({trusted_url}) or upload the campus Job Description (JD) into Knowledge Documents."

        # Case 4: No verified corporate records or official sources available
        else:
            company_overview_text = (
                f"No official company overview, brochures, or corporate documentation for {entity} are currently stored in your knowledge base. "
                f"General corporate facts are omitted until official sources are provided to avoid unverified information."
            )
            official_source_label = "unverified / no official sources stored"
            next_steps_source_hint = f"Upload the official {entity} Job Description (JD) or campus brochure in Knowledge Documents."

        return (
            f"• General Company Information ({official_source_label}):\n"
            f"  {company_overview_text}"
            f"{live_retrieval_notice}\n\n"
            f"• Job-Specific Requirements & Drives: No placement drives or official job descriptions for {entity} "
            f"are registered in your placement database.{resume_notice}\n"
            f"• Personal Role & Eligibility: No current role at {entity} is recorded in your profile, and personal eligibility "
            f"cannot be verified without an active placement drive or official criteria loaded in the system.\n\n"
            f"• Recommended Next Steps:\n"
            f"  1. Check your college placement portal or TPO notice for the official {entity} campus recruitment circular and hiring rounds.\n"
            f"  2. {next_steps_source_hint}\n"
            f"  3. Add the drive details into Placement Intelligence to automatically evaluate your CGPA and branch eligibility."
        )

    def _check_project_grounding(
        self,
        query: str,
        structured_context: Dict[str, Any],
        sources: List[SourceCitation],
        conversation_history: Optional[List[Any]] = None,
    ) -> Optional[str]:
        """
        Enforces strict grounding for project inquiries:
        1. Identifies targeted project from query or conversational context.
        2. If the user asks for implementation details, architecture, modules, features, or database schema
           not documented in the project record or uploaded documentation, states they are not documented and
           invites the user to provide them.
        3. If the user asks to describe, explain, or give an overview of a project, provides only verified facts
           (name, role, status, description, technologies) without inferring unverified features (CRUD, course
           registration, attendance records).
        4. Preserves multi-topic inquiries (e.g. asking about skills/career goals).
        """
        projects = structured_context.get("projects", [])
        if not projects:
            return None

        q_lower = query.lower()

        # Multi-topic check: if user asks about skills, career goals, or certifications, defer to combined context
        if any(re.search(pat, q_lower) for pat in [
            r"\bcareer goals?\b",
            r"\bskills?\b",
            r"\bcert(s|ifications?)?\b",
            r"\bcgpa\b",
            r"\bwho am i\b",
        ]):
            return None

        # 1. Match project by name in query
        matched_proj = None
        for p in projects:
            p_name = p.get("name", "").lower()
            if p_name and p_name in q_lower:
                matched_proj = p
                break

        # 2. If no direct name match, match by pronoun or singular project reference
        if not matched_proj:
            has_single_proj_ref = any(re.search(pat, q_lower) for pat in [
                r"\b(the|my|this)\s+project\b",
                r"\babout\s+(the\s+|my\s+)?project\b",
                r"\bproject\s+(details|description|features?|modules?|architecture)\b",
                r"\bdescribe\s+(the\s+|my\s+)?project\b",
                r"\bexplain\s+(the\s+|my\s+)?project\b",
                r"\btell me about\s+(the\s+|my\s+)?project\b",
            ])
            if has_single_proj_ref and len(projects) == 1:
                matched_proj = projects[0]

        # 3. Check recent conversation history for active project context
        if not matched_proj and conversation_history:
            for m in reversed(conversation_history[-4:]):
                content = getattr(m, "content", "") if not isinstance(m, dict) else m.get("content", "")
                content_lower = content.lower()
                for p in projects:
                    if p.get("name", "").lower() in content_lower:
                        matched_proj = p
                        break
                if matched_proj:
                    break

        if not matched_proj:
            return None

        # Detail inquiry patterns (modules, features, architecture, database schema, auth, crud, attendance, etc.)
        details_patterns = [
            r"\bmodule(s)?\b",
            r"\bfeature(s)?\b",
            r"\bimplementation detail(s)?\b",
            r"\barchitecture\b",
            r"\bdatabase schema\b",
            r"\btable(s)?\b",
            r"\bauthentication\b",
            r"\bauth\b",
            r"\blogin\b",
            r"\bcrud\b",
            r"\bcourse registration\b",
            r"\battendance\b",
            r"\bgrade(s)?\b",
            r"\bgrading\b",
            r"\bfee(s)?\b",
            r"\bendpoint(s)?\b",
            r"\bapi route(s)?\b",
            r"\bfunctionality\b",
            r"\bcapabilities\b",
        ]
        is_details_query = any(re.search(pat, q_lower) for pat in details_patterns)

        # Description / overview inquiry patterns
        desc_patterns = [
            r"\bdescribe\b",
            r"\btell me about\b",
            r"\bexplain\b",
            r"\bwhat is\b",
            r"\boverview\b",
            r"\bsummar(y|ize)\b",
            r"\bwhat did i (work on|build|do)\b",
            r"\bwhat does (.+) do\b",
        ]
        is_desc_query = any(re.search(pat, q_lower) for pat in desc_patterns)

        if not is_details_query and not is_desc_query:
            return None

        proj_name = matched_proj["name"]
        role = matched_proj.get("role") or "Not specified"
        status = matched_proj.get("status") or "Not specified"
        desc = matched_proj.get("description") or "Not specified"
        tech_list = matched_proj.get("technologies") or []
        tech_str = ", ".join(tech_list) if isinstance(tech_list, list) else str(tech_list)

        # Check if external verified project documentation exists in sources
        verified_doc_snippets = []
        for s in sources:
            doc_type = context_builder.detect_document_type(s.filename, s.snippet)
            if doc_type != "Candidate Resume / Personal Application Document":
                if proj_name.lower() in s.filename.lower() or proj_name.lower() in s.snippet.lower():
                    verified_doc_snippets.append(s.snippet)

        if not verified_doc_snippets:
            if is_details_query:
                return (
                    f"Specific implementation details (such as modules, features, or architecture) for the '{proj_name}' "
                    f"project are not documented in your stored project records.\n\n"
                    f"• Documented Project Details:\n"
                    f"  - Project: {proj_name}\n"
                    f"  - Role: {role}\n"
                    f"  - Status: {status}\n"
                    f"  - Description: {desc}\n"
                    f"  - Technologies: {tech_str}\n\n"
                    f"Please provide the specific implementation details or features if you would like to update this project record."
                )

            if is_desc_query:
                return (
                    f"The {proj_name} project is {desc}\n\n"
                    f"• Documented Project Details:\n"
                    f"  - Project: {proj_name}\n"
                    f"  - Role: {role}\n"
                    f"  - Status: {status}\n"
                    f"  - Technologies: {tech_str}\n"
                    f"  - Description: {desc}\n\n"
                    f"Note: Specific implementation details, modules, or extended features (such as CRUD operations, course registrations, or attendance records) "
                    f"are not documented in your stored project record. If you have implemented specific features or modules, please provide them to update your project details."
                )

        return None

    async def query(
        self,
        db: AsyncSession,
        question: str,
        top_k: int = settings.rag_top_k,
        similarity_threshold: float = settings.rag_similarity_threshold,
        document_id: Optional[uuid.UUID] = None,
    ) -> RAGResponse:
        """
        Executes single-turn retrieval and answer generation:
        1. Classifies user query intent via IntentRouter
        2. Routes to direct LLM (Casual, General Knowledge) or retrieval pipeline (Profile, Document RAG, Placement)
        3. Invokes LLM with specialized system prompt
        4. Returns grounded answer with structured provenance and citations
        """
        start_time = time.perf_counter()

        # Step 0: Classify intent
        routing = intent_router.classify(question)
        logger.info(
            "Query intent: %s (confidence: %.2f, reasoning: %s)",
            routing.intent.value,
            routing.confidence,
            routing.reasoning,
        )

        # -------------------------------------------------------------
        # Intent: CASUAL
        # -------------------------------------------------------------
        if routing.intent == IntentCategory.CASUAL:
            llm_resp = await self.llm_provider.generate(
                prompt=question,
                system_prompt=CASUAL_SYSTEM_PROMPT,
                temperature=0.7,
            )
            return RAGResponse(
                query=question,
                answer=llm_resp.content,
                sources=[],
                structured_sources=[],
                model=llm_resp.model,
                context_used=False,
                grounded=True,
                intent=routing.intent.value,
                sources_used=[],
            )

        # -------------------------------------------------------------
        # Intent: GENERAL_KNOWLEDGE
        # -------------------------------------------------------------
        if routing.intent == IntentCategory.GENERAL_KNOWLEDGE:
            llm_resp = await self.llm_provider.generate(
                prompt=question,
                system_prompt=GENERAL_KNOWLEDGE_SYSTEM_PROMPT,
                temperature=0.2,
            )
            return RAGResponse(
                query=question,
                answer=llm_resp.content,
                sources=[],
                structured_sources=[],
                model=llm_resp.model,
                context_used=False,
                grounded=True,
                intent=routing.intent.value,
                sources_used=[],
            )

        # -------------------------------------------------------------
        # Intent: PERSONAL_PROFILE, PLACEMENT, DOCUMENT_RAG, UNKNOWN
        # -------------------------------------------------------------
        # Step 1: Structured Personal Context Retrieval
        structured_context: Dict[str, Any] = {}
        if routing.use_profile or routing.intent in (
            IntentCategory.PERSONAL_PROFILE,
            IntentCategory.PLACEMENT,
            IntentCategory.UNKNOWN,
        ):
            structured_context = await get_relevant_personal_context(db, question)
        structured_categories = structured_context.get("categories", [])

        # Step 2: Semantic Document Retrieval
        doc_keywords = {"document", "documents", "resume", "cv", "report", "file", "files", "pdf", "source", "sources"}
        has_doc_keyword = any(w in question.lower() for w in doc_keywords)
        is_pure_profile_query = (
            routing.intent == IntentCategory.PERSONAL_PROFILE and not has_doc_keyword and not document_id
        )

        sources: List[SourceCitation] = []
        if (
            routing.use_rag
            or document_id
            or has_doc_keyword
            or routing.intent == IntentCategory.UNKNOWN
            or routing.intent == IntentCategory.PLACEMENT
        ) and not is_pure_profile_query:
            sources = await self.retrieve_relevant_chunks(
                db=db,
                query=question,
                top_k=top_k,
                similarity_threshold=similarity_threshold,
                document_id=document_id,
            )

        # Step 3: Fetch chunk texts for citations
        chunk_texts: List[str] = []
        for s in sources:
            res = await db.execute(
                select(DocumentChunk.content).where(
                    DocumentChunk.document_id == uuid.UUID(s.document_id),
                    DocumentChunk.chunk_index == s.chunk_index,
                )
            )
            text = res.scalars().first() or s.snippet
            chunk_texts.append(text)

        # Step 4: Context Building
        built_context = context_builder.build_context(
            structured_context=structured_context,
            sources=sources,
            chunk_texts=chunk_texts,
        )

        retrieval_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            "Context retrieval completed in %.2f ms (structured: %s, doc chunks: %d)",
            retrieval_ms,
            built_context.structured_categories,
            len(sources),
        )

        # Step 5: Check Deterministic Guards before LLM invocation
        # Guard 0: Authoritative identity guard
        is_identity_inquiry = any(re.search(pat, question.lower()) for pat in [
            r"\bwho am i\b", r"\bwhat is my name\b", r"\bmy name\b",
        ])
        profile_data = structured_context.get("profile")
        if is_identity_inquiry and profile_data and profile_data.get("name"):
            name = profile_data["name"]
            deg = profile_data.get("degree", "")
            branch = profile_data.get("branch", "")
            univ = profile_data.get("university", "")
            grad = profile_data.get("graduation_year", "")
            cgpa = profile_data.get("cgpa", "")
            details = []
            if deg and branch:
                details.append(f"{deg} student in {branch}")
            elif branch:
                details.append(f"student in {branch}")
            if univ:
                details.append(f"at {univ}")
            if grad:
                details.append(f"(Class of {grad})")
            if cgpa:
                details.append(f"with a CGPA of {cgpa}/10")
            desc = " ".join(details)
            reply_text = f"You are {name}, a {desc}." if desc else f"You are {name}."
            return RAGResponse(
                query=question,
                answer=reply_text,
                sources=[],
                structured_sources=["profile"],
                model="authoritative_profile",
                context_used=True,
                grounded=True,
                intent=routing.intent.value,
                sources_used=["profile"],
            )

        # Guard 1: Empty projects guard
        is_project_inquiry = any(re.search(pat, question.lower()) for pat in [
            r"\bprojects?\b", r"\bportfolio\b", r"\btechnolog(y|ies) in (my )?projects?\b",
            r"\bwhat have i built\b", r"\bwhat have i worked on\b", r"\bmy project\b",
        ])
        if is_project_inquiry and len(structured_context.get("projects", [])) == 0 and not sources:
            return RAGResponse(
                query=question,
                answer=(
                    "You currently do not have any project records registered in your profile. "
                    "No projects or project technologies are stored in the database."
                ),
                sources=[],
                structured_sources=["projects"],
                model="deterministic_guard",
                context_used=True,
                grounded=True,
                intent=routing.intent.value,
                sources_used=["projects"],
            )

        # Guard 2: Zero placement drives guard (aggregate queries with no specific company)
        is_placement_aggregate_inquiry = any(re.search(pat, question.lower()) for pat in [
            r"\bwhich compan(y|ies) am i eligible for\b",
            r"\bam i eligible for (any|all) compan(y|ies)\b",
            r"\bwhich drives are (currently )?open\b",
            r"\bopen (placement )?drives?\b",
            r"\bplacement pipeline\b",
            r"\bwhich companies should i prioritize\b",
            r"\bplacement priorit(y|ization)\b",
            r"\bwhich companies match my skills\b",
        ])
        if (
            (routing.intent == IntentCategory.PLACEMENT or is_placement_aggregate_inquiry)
            and not routing.resolved_entity
            and len(structured_context.get("placements", [])) == 0
            and not sources
        ):
            return RAGResponse(
                query=question,
                answer=(
                    "There are currently no placement drives loaded in the placement database. "
                    "Therefore, I cannot verify company eligibility or list open recruitment opportunities yet."
                ),
                sources=[],
                structured_sources=["placements"],
                model="deterministic_guard",
                context_used=True,
                grounded=True,
                intent=routing.intent.value,
                sources_used=["placements"],
            )

        # Guard 3: Company entity grounding guard (when target company has no verified records/docs)
        if routing.resolved_entity and (routing.intent == IntentCategory.PLACEMENT or bool(extract_company_entity(routing.resolved_entity))):
            company_guard_ans = await self._check_company_grounding(
                db=db,
                entity=routing.resolved_entity,
                query=question,
                structured_context=structured_context,
                sources=sources,
            )
            if company_guard_ans:
                norm_ent = routing.resolved_entity.lower().strip()
                guard_sources = [
                    s for s in sources
                    if (norm_ent in s.filename.lower() or norm_ent in s.snippet.lower())
                    and context_builder.detect_document_type(s.filename, s.snippet) != "Candidate Resume / Personal Application Document"
                ]
                deduped_sources = deduplicate_citations(guard_sources)
                return RAGResponse(
                    query=question,
                    answer=company_guard_ans,
                    sources=deduped_sources,
                    structured_sources=["placements"] if "placements" in structured_categories else list(structured_categories),
                    model="deterministic_guard",
                    context_used=True,
                    grounded=True,
                    intent=routing.intent.value,
                    sources_used=[s.filename for s in deduped_sources] if deduped_sources else ["official_company_reference"],
                )

        # Guard 4: Project grounding guard (for project description and undocumented detail queries)
        proj_guard_ans = self._check_project_grounding(
            query=question,
            structured_context=structured_context,
            sources=sources,
        )
        if proj_guard_ans:
            return RAGResponse(
                query=question,
                answer=proj_guard_ans,
                sources=[],
                structured_sources=["projects"],
                model="deterministic_guard",
                context_used=True,
                grounded=True,
                intent=routing.intent.value,
                sources_used=["projects"],
            )

        # Step 6: Safeguard if zero context available
        if not built_context.has_structured_data and not built_context.has_document_data:
            if routing.intent == IntentCategory.DOCUMENT_RAG:
                answer = "I couldn't find relevant information in your uploaded documents to answer this question."
            elif routing.intent == IntentCategory.PERSONAL_PROFILE:
                answer = "I don't have verified information about that in your profile to answer this question."
            else:
                answer = "Based on your personal profile and uploaded documents, there is not enough information to answer this question."

            return RAGResponse(
                query=question,
                answer=answer,
                sources=[],
                structured_sources=[],
                model=self.llm_provider.model if hasattr(self.llm_provider, "model") else "none",
                context_used=False,
                grounded=True,
                intent=routing.intent.value,
                sources_used=[],
            )

        # Step 7: Select specialized system prompt
        if routing.intent == IntentCategory.PERSONAL_PROFILE:
            active_system_prompt = PERSONAL_PROFILE_SYSTEM_PROMPT
        elif routing.intent == IntentCategory.PLACEMENT:
            active_system_prompt = PLACEMENT_SYSTEM_PROMPT
        elif routing.intent == IntentCategory.DOCUMENT_RAG:
            active_system_prompt = DOCUMENT_RAG_SYSTEM_PROMPT
        else:
            active_system_prompt = GROUNDING_SYSTEM_PROMPT

        context_blocks = []
        if routing.resolved_entity:
            context_blocks.append(f"[ACTIVE SUBJECT / TARGET COMPANY: {routing.resolved_entity}]")
        if built_context.prompt_context:
            context_blocks.append(f"Verified Context:\n{built_context.prompt_context}")

        prompt_with_context = (
            f"{''.join(context_blocks)}\n\n"
            f"User Question:\n{question}\n\n"
            "Answer:"
        )

        # Step 8: Generation via configured LLM provider
        llm_resp = await self.llm_provider.generate(
            prompt=prompt_with_context,
            system_prompt=active_system_prompt,
            temperature=0.0,
        )

        deduped_sources = deduplicate_citations(sources)
        sources_used_list = list(built_context.structured_categories)
        if deduped_sources:
            sources_used_list.extend([s.filename for s in deduped_sources])

        return RAGResponse(
            query=question,
            answer=llm_resp.content,
            sources=deduped_sources,
            structured_sources=built_context.structured_categories,
            model=llm_resp.model,
            context_used=True,
            grounded=True,
            intent=routing.intent.value,
            sources_used=sources_used_list,
        )

    async def chat(
        self,
        db: AsyncSession,
        message: str,
        conversation_id: Optional[uuid.UUID] = None,
        top_k: int = settings.rag_top_k,
        similarity_threshold: float = settings.rag_similarity_threshold,
    ) -> Dict[str, Any]:
        """
        Multi-turn conversational RAG combining intent routing, structured personal context,
        semantic document retrieval, dialogue history, and message persistence.
        """
        start_time = time.perf_counter()
        conversation = None
        history_messages: List[Message] = []

        if conversation_id:
            res = await db.execute(
                select(Conversation)
                .options(selectinload(Conversation.messages))
                .where(Conversation.id == conversation_id)
            )
            conversation = res.scalars().first()

        if not conversation:
            title = message[:50] + "..." if len(message) > 50 else message
            conversation = Conversation(title=title)
            db.add(conversation)
            await db.commit()
            await db.refresh(conversation)
        else:
            history_messages = conversation.messages

        # Step 0: Classify intent with conversation history awareness
        routing = intent_router.classify(message, conversation_history=history_messages)
        logger.info(
            "Chat intent: %s (confidence: %.2f, reasoning: %s)",
            routing.intent.value,
            routing.confidence,
            routing.reasoning,
        )

        # Save User Message
        user_msg = Message(
            conversation_id=conversation.id,
            role="user",
            content=message,
        )
        db.add(user_msg)
        await db.commit()

        # Build chat history for LLM
        chat_history: List[ChatMessage] = []
        for past in history_messages[-6:]:  # last 3 turns
            chat_history.append(ChatMessage(role=past.role, content=past.content))

        # -------------------------------------------------------------
        # Intent: CASUAL
        # -------------------------------------------------------------
        if routing.intent == IntentCategory.CASUAL:
            llm_resp = await self.llm_provider.generate(
                prompt=message,
                system_prompt=CASUAL_SYSTEM_PROMPT,
                history=chat_history,
                temperature=0.7,
            )
            assistant_msg = Message(
                conversation_id=conversation.id,
                role="assistant",
                content=llm_resp.content,
                citations=[],
            )
            db.add(assistant_msg)
            await db.commit()
            await db.refresh(assistant_msg)

            return {
                "conversation_id": conversation.id,
                "message": assistant_msg,
                "sources": [],
                "structured_sources": [],
                "model": llm_resp.model,
                "intent": routing.intent.value,
                "sources_used": [],
            }

        # -------------------------------------------------------------
        # Intent: GENERAL_KNOWLEDGE
        # -------------------------------------------------------------
        if routing.intent == IntentCategory.GENERAL_KNOWLEDGE:
            llm_resp = await self.llm_provider.generate(
                prompt=message,
                system_prompt=GENERAL_KNOWLEDGE_SYSTEM_PROMPT,
                history=chat_history,
                temperature=0.2,
            )
            assistant_msg = Message(
                conversation_id=conversation.id,
                role="assistant",
                content=llm_resp.content,
                citations=[],
            )
            db.add(assistant_msg)
            await db.commit()
            await db.refresh(assistant_msg)

            return {
                "conversation_id": conversation.id,
                "message": assistant_msg,
                "sources": [],
                "structured_sources": [],
                "model": llm_resp.model,
                "intent": routing.intent.value,
                "sources_used": [],
            }

        # -------------------------------------------------------------
        # Retrieval-backed Intents: PERSONAL_PROFILE, PLACEMENT, DOCUMENT_RAG, UNKNOWN
        # -------------------------------------------------------------
        # 1. Build search query (only incorporate target entity if genuine follow-up)
        search_query = message
        if routing.is_followup and routing.resolved_entity:
            search_query = f"{routing.resolved_entity} {message}"

        # 2. Retrieve structured context for intent
        structured_context: Dict[str, Any] = {}
        if routing.use_profile or routing.intent in (
            IntentCategory.PERSONAL_PROFILE,
            IntentCategory.PLACEMENT,
            IntentCategory.UNKNOWN,
        ):
            structured_context = await get_relevant_personal_context(db, search_query)
        structured_categories = structured_context.get("categories", [])

        # 3. Retrieve document sources
        doc_keywords = {"document", "documents", "resume", "cv", "report", "file", "files", "pdf", "source", "sources"}
        has_doc_keyword = any(w in search_query.lower() for w in doc_keywords)
        is_pure_profile_query = (
            routing.intent == IntentCategory.PERSONAL_PROFILE and not has_doc_keyword
        )

        sources: List[SourceCitation] = []
        if (
            routing.use_rag
            or has_doc_keyword
            or routing.intent == IntentCategory.UNKNOWN
            or routing.intent == IntentCategory.PLACEMENT
        ) and not is_pure_profile_query:
            sources = await self.retrieve_relevant_chunks(
                db=db,
                query=search_query,
                top_k=top_k,
                similarity_threshold=similarity_threshold,
            )

        # 4. Fetch chunk texts
        chunk_texts: List[str] = []
        for s in sources:
            res = await db.execute(
                select(DocumentChunk.content).where(
                    DocumentChunk.document_id == uuid.UUID(s.document_id),
                    DocumentChunk.chunk_index == s.chunk_index,
                )
            )
            text = res.scalars().first() or s.snippet
            chunk_texts.append(text)

        # 5. Build context
        built_context = context_builder.build_context(
            structured_context=structured_context,
            sources=sources,
            chunk_texts=chunk_texts,
        )

        retrieval_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            "Chat context retrieval completed in %.2f ms (structured: %s, doc chunks: %d)",
            retrieval_ms,
            built_context.structured_categories,
            len(sources),
        )

        # Step 6: Check Deterministic Guards before LLM invocation
        # Guard 0: Authoritative identity guard
        is_identity_inquiry = any(re.search(pat, message.lower()) for pat in [
            r"\bwho am i\b", r"\bwhat is my name\b", r"\bmy name\b",
        ])
        profile_data = structured_context.get("profile")
        if is_identity_inquiry and profile_data and profile_data.get("name"):
            name = profile_data["name"]
            deg = profile_data.get("degree", "")
            branch = profile_data.get("branch", "")
            univ = profile_data.get("university", "")
            grad = profile_data.get("graduation_year", "")
            cgpa = profile_data.get("cgpa", "")
            details = []
            if deg and branch:
                details.append(f"{deg} student in {branch}")
            elif branch:
                details.append(f"student in {branch}")
            if univ:
                details.append(f"at {univ}")
            if grad:
                details.append(f"(Class of {grad})")
            if cgpa:
                details.append(f"with a CGPA of {cgpa}/10")
            desc = " ".join(details)
            reply_text = f"You are {name}, a {desc}." if desc else f"You are {name}."
            assistant_msg = Message(
                conversation_id=conversation.id,
                role="assistant",
                content=reply_text,
                citations=[],
            )
            db.add(assistant_msg)
            await db.commit()
            await db.refresh(assistant_msg)
            return {
                "conversation_id": conversation.id,
                "message": assistant_msg,
                "sources": [],
                "structured_sources": ["profile"],
                "model": "authoritative_profile",
                "intent": routing.intent.value,
                "sources_used": ["profile"],
            }

        # Guard 1: Empty projects guard
        is_project_inquiry = any(re.search(pat, message.lower()) for pat in [
            r"\bprojects?\b", r"\bportfolio\b", r"\btechnolog(y|ies) in (my )?projects?\b",
            r"\bwhat have i built\b", r"\bwhat have i worked on\b", r"\bmy project\b",
        ])
        if is_project_inquiry and len(structured_context.get("projects", [])) == 0 and not sources:
            reply_text = (
                "You currently do not have any project records registered in your profile. "
                "No projects or project technologies are stored in the database."
            )
            assistant_msg = Message(
                conversation_id=conversation.id,
                role="assistant",
                content=reply_text,
                citations=[],
            )
            db.add(assistant_msg)
            await db.commit()
            await db.refresh(assistant_msg)
            return {
                "conversation_id": conversation.id,
                "message": assistant_msg,
                "sources": [],
                "structured_sources": ["projects"],
                "model": "deterministic_guard",
                "intent": routing.intent.value,
                "sources_used": ["projects"],
            }

        # Guard 2: Zero placement drives guard (aggregate queries with no specific company)
        is_placement_aggregate_inquiry = any(re.search(pat, message.lower()) for pat in [
            r"\bwhich compan(y|ies) am i eligible for\b",
            r"\bam i eligible for (any|all) compan(y|ies)\b",
            r"\bwhich drives are (currently )?open\b",
            r"\bopen (placement )?drives?\b",
            r"\bplacement pipeline\b",
            r"\bwhich companies should i prioritize\b",
            r"\bplacement priorit(y|ization)\b",
            r"\bwhich companies match my skills\b",
        ])
        if (
            (routing.intent == IntentCategory.PLACEMENT or is_placement_aggregate_inquiry)
            and not routing.resolved_entity
            and len(structured_context.get("placements", [])) == 0
            and not sources
        ):
            reply_text = (
                "There are currently no placement drives loaded in the placement database. "
                "Therefore, I cannot verify company eligibility or list open recruitment opportunities yet."
            )
            assistant_msg = Message(
                conversation_id=conversation.id,
                role="assistant",
                content=reply_text,
                citations=[],
            )
            db.add(assistant_msg)
            await db.commit()
            await db.refresh(assistant_msg)
            return {
                "conversation_id": conversation.id,
                "message": assistant_msg,
                "sources": [],
                "structured_sources": ["placements"],
                "model": "deterministic_guard",
                "intent": routing.intent.value,
                "sources_used": ["placements"],
            }

        # Guard 3: Company entity grounding guard (when target company has no verified records/docs)
        if routing.resolved_entity and (routing.intent == IntentCategory.PLACEMENT or bool(extract_company_entity(routing.resolved_entity))):
            company_guard_ans = await self._check_company_grounding(
                db=db,
                entity=routing.resolved_entity,
                query=message,
                structured_context=structured_context,
                sources=sources,
            )
            if company_guard_ans:
                norm_ent = routing.resolved_entity.lower().strip()
                guard_sources = [
                    s for s in sources
                    if (norm_ent in s.filename.lower() or norm_ent in s.snippet.lower())
                    and context_builder.detect_document_type(s.filename, s.snippet) != "Candidate Resume / Personal Application Document"
                ]
                deduped_sources = deduplicate_citations(guard_sources)
                assistant_msg = Message(
                    conversation_id=conversation.id,
                    role="assistant",
                    content=company_guard_ans,
                    citations=[s.to_dict() for s in deduped_sources],
                )
                db.add(assistant_msg)
                await db.commit()
                await db.refresh(assistant_msg)
                return {
                    "conversation_id": conversation.id,
                    "message": assistant_msg,
                    "sources": deduped_sources,
                    "structured_sources": ["placements"] if "placements" in structured_categories else list(structured_categories),
                    "model": "deterministic_guard",
                    "intent": routing.intent.value,
                    "sources_used": [s.filename for s in deduped_sources] if deduped_sources else ["official_company_reference"],
                }

        # Guard 4: Project grounding guard (for project description and undocumented detail queries)
        proj_guard_ans = self._check_project_grounding(
            query=search_query,
            structured_context=structured_context,
            sources=sources,
            conversation_history=history_messages,
        )
        if proj_guard_ans:
            assistant_msg = Message(
                conversation_id=conversation.id,
                role="assistant",
                content=proj_guard_ans,
                citations=[],
            )
            db.add(assistant_msg)
            await db.commit()
            await db.refresh(assistant_msg)
            return {
                "conversation_id": conversation.id,
                "message": assistant_msg,
                "sources": [],
                "structured_sources": ["projects"],
                "model": "deterministic_guard",
                "intent": routing.intent.value,
                "sources_used": ["projects"],
            }

        # Step 7: Check context and construct prompt
        if built_context.has_structured_data or built_context.has_document_data:
            if routing.intent == IntentCategory.PERSONAL_PROFILE:
                active_system_prompt = PERSONAL_PROFILE_SYSTEM_PROMPT
            elif routing.intent == IntentCategory.PLACEMENT:
                active_system_prompt = PLACEMENT_SYSTEM_PROMPT
            elif routing.intent == IntentCategory.DOCUMENT_RAG:
                active_system_prompt = DOCUMENT_RAG_SYSTEM_PROMPT
            else:
                active_system_prompt = GROUNDING_SYSTEM_PROMPT

            context_blocks = []
            if routing.resolved_entity:
                context_blocks.append(f"[ACTIVE SUBJECT / TARGET COMPANY: {routing.resolved_entity}]")
            if built_context.prompt_context:
                context_blocks.append(f"Verified Context:\n{built_context.prompt_context}")

            prompt_with_context = (
                f"{''.join(context_blocks)}\n\n"
                f"User Question:\n{message}\n\n"
                "Answer:"
            )
        else:
            if routing.intent == IntentCategory.DOCUMENT_RAG:
                reply_text = "I couldn't find relevant information in your uploaded documents to answer this question."
            elif routing.intent == IntentCategory.PERSONAL_PROFILE:
                reply_text = "I don't have verified information about that in your profile to answer this question."
            else:
                reply_text = "Based on your personal profile and uploaded documents, there is not enough information to answer this question."

            assistant_msg = Message(
                conversation_id=conversation.id,
                role="assistant",
                content=reply_text,
                citations=[],
            )
            db.add(assistant_msg)
            await db.commit()
            await db.refresh(assistant_msg)

            return {
                "conversation_id": conversation.id,
                "message": assistant_msg,
                "sources": [],
                "structured_sources": [],
                "model": self.llm_provider.model if hasattr(self.llm_provider, "model") else "none",
                "intent": routing.intent.value,
                "sources_used": [],
            }

        # Step 8: Call LLM
        llm_resp = await self.llm_provider.generate(
            prompt=prompt_with_context,
            system_prompt=active_system_prompt,
            history=chat_history,
            temperature=0.0,
        )

        # Step 9: Save Assistant Message with JSONB citations
        deduped_sources = deduplicate_citations(sources)
        citations_json = [s.to_dict() for s in deduped_sources]
        assistant_msg = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=llm_resp.content,
            citations=citations_json,
        )
        db.add(assistant_msg)
        await db.commit()
        await db.refresh(assistant_msg)

        sources_used_list = list(built_context.structured_categories)
        if deduped_sources:
            sources_used_list.extend([s.filename for s in deduped_sources])

        return {
            "conversation_id": conversation.id,
            "message": assistant_msg,
            "sources": deduped_sources,
            "structured_sources": built_context.structured_categories,
            "model": llm_resp.model,
            "intent": routing.intent.value,
            "sources_used": sources_used_list,
        }

    async def evaluate_context_summary(
        self,
        db: AsyncSession,
        query: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Exposes developer-only diagnostic information without secrets or raw credentials."""
        from app.services.personal_context import (
            get_profile_context,
            get_skills_context,
            get_projects_context,
            get_certifications_context,
            get_companies_context,
            get_placement_context,
        )

        profile = await get_profile_context(db)
        skills = await get_skills_context(db)
        projects = await get_projects_context(db)
        certs = await get_certifications_context(db)
        companies = await get_companies_context(db)
        placements = await get_placement_context(db)

        base_summary = {
            "profile_present": bool(profile),
            "profile_name": profile.get("name") if profile else None,
            "skills_count": len(skills),
            "projects_count": len(projects),
            "certifications_count": len(certs),
            "companies_count": len(companies),
            "placements_count": len(placements),
        }

        if not query:
            return base_summary

        routing = intent_router.classify(query)
        structured_context = await get_relevant_personal_context(db, query)

        doc_keywords = {"document", "documents", "resume", "cv", "report", "file", "files", "pdf"}
        has_doc_keyword = any(w in query.lower() for w in doc_keywords)
        is_pure_profile = (
            routing.intent == IntentCategory.PERSONAL_PROFILE and not has_doc_keyword
        )

        sources: List[SourceCitation] = []
        if (routing.use_rag or has_doc_keyword or routing.intent == IntentCategory.UNKNOWN) and not is_pure_profile:
            sources = await self.retrieve_relevant_chunks(
                db=db,
                query=query,
                top_k=settings.rag_top_k,
                similarity_threshold=settings.rag_similarity_threshold,
            )

        guard_fired = False
        guard_name = None
        guard_reason = None
        q_lower = query.lower()

        is_project_q = any(re.search(pat, q_lower) for pat in [
            r"\bprojects?\b", r"\bportfolio\b", r"\btechnolog(y|ies) in (my )?projects?\b",
            r"\bwhat have i built\b", r"\bwhat have i worked on\b", r"\bmy project\b",
        ])
        if is_project_q and len(projects) == 0 and not sources:
            guard_fired = True
            guard_name = "EMPTY_PROJECTS_GUARD"
            guard_reason = "User inquired about projects, but zero project records exist in database."

        is_placement_elig_q = any(re.search(pat, q_lower) for pat in [
            r"\bwhich compan(y|ies) am i eligible for\b",
            r"\bam i eligible for (any|all) compan(y|ies)\b",
            r"\bwhich drives are (currently )?open\b",
            r"\bopen (placement )?drives?\b",
            r"\bplacement pipeline\b",
            r"\bwhich companies should i prioritize\b",
            r"\bplacement priorit(y|ization)\b",
            r"\bwhich companies match my skills\b",
        ])
        if (routing.intent == IntentCategory.PLACEMENT or is_placement_elig_q) and not routing.resolved_entity and len(placements) == 0 and not sources:
            guard_fired = True
            guard_name = "ZERO_PLACEMENT_DRIVES_GUARD"
            guard_reason = "User inquired about placement eligibility/drives, but zero placement drives exist in database."

        if routing.resolved_entity and (routing.intent == IntentCategory.PLACEMENT or bool(extract_company_entity(routing.resolved_entity))) and not guard_fired:
            comp_guard_res = await self._check_company_grounding(
                db=db,
                entity=routing.resolved_entity,
                query=query,
                structured_context=structured_context,
                sources=sources,
            )
            if comp_guard_res:
                guard_fired = True
                guard_name = "UNVERIFIED_COMPANY_GUARD"
                guard_reason = f"Target company '{routing.resolved_entity}' has no official records or company documents in knowledge base."

        if not guard_fired:
            proj_guard_res = self._check_project_grounding(
                query=query,
                structured_context=structured_context,
                sources=sources,
            )
            if proj_guard_res:
                guard_fired = True
                guard_name = "PROJECT_GROUNDING_GUARD"
                guard_reason = "User inquired about project description or undocumented implementation details."

        llm_invoked = not guard_fired and routing.intent not in (IntentCategory.CASUAL, IntentCategory.GENERAL_KNOWLEDGE)

        retrieved_docs = []
        for s in sources:
            retrieved_docs.append({
                "filename": s.filename,
                "document_type": context_builder.detect_document_type(s.filename, ""),
                "similarity_score": round(s.similarity_score, 4),
            })

        return {
            **base_summary,
            "query_diagnostics": {
                "query": query,
                "intent": routing.intent.value,
                "confidence": round(routing.confidence, 2),
                "resolved_entity": routing.resolved_entity,
                "is_followup": routing.is_followup,
                "use_profile": routing.use_profile,
                "use_rag": routing.use_rag,
                "use_placement": routing.use_placement,
                "has_profile_in_context": bool(structured_context.get("profile")),
                "has_projects_in_context": len(structured_context.get("projects", [])) > 0,
                "has_placements_in_context": len(structured_context.get("placements", [])) > 0,
                "retrieved_documents": retrieved_docs,
                "deterministic_guard_fired": guard_fired,
                "deterministic_guard_name": guard_name,
                "deterministic_guard_reason": guard_reason,
                "llm_invoked": llm_invoked,
            }
        }


rag_service = RAGService()
