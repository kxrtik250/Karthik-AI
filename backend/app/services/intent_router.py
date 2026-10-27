"""Intent Router Service.

Classifies incoming user messages into distinct semantic intent categories
before retrieval and response generation:
- CASUAL: Conversational greetings, farewells, acknowledgments, small talk.
- PERSONAL_PROFILE: Questions about the user's verified identity, degree, CGPA, skills, projects, certs.
- DOCUMENT_RAG: Inquiries explicitly targeting uploaded documents, resumes, CVs, reports, PDFs.
- PLACEMENT: Inquiries about placement drives, company eligibility, interview prep, hiring pipeline.
- GENERAL_KNOWLEDGE: Broad technical questions, software engineering concepts, definitions, explanations.
- UNKNOWN: Ambiguous or unclassified requests (safe fallback to conversational LLM).
"""

from dataclasses import dataclass
from enum import Enum
import logging
import re
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class IntentCategory(str, Enum):
    CASUAL = "CASUAL"
    PERSONAL_PROFILE = "PERSONAL_PROFILE"
    DOCUMENT_RAG = "DOCUMENT_RAG"
    PLACEMENT = "PLACEMENT"
    GENERAL_KNOWLEDGE = "GENERAL_KNOWLEDGE"
    UNKNOWN = "UNKNOWN"


@dataclass
class IntentRoutingResult:
    intent: IntentCategory
    confidence: float
    use_rag: bool
    use_profile: bool
    use_placement: bool
    reasoning: Optional[str] = None
    resolved_entity: Optional[str] = None
    is_followup: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent.value,
            "confidence": round(self.confidence, 2),
            "use_rag": self.use_rag,
            "use_profile": self.use_profile,
            "use_placement": self.use_placement,
            "reasoning": self.reasoning,
            "resolved_entity": self.resolved_entity,
            "is_followup": self.is_followup,
        }


# -------------------------------------------------------------
# Pattern Sets for Deterministic Classification
# -------------------------------------------------------------

# Casual Greetings & Courtesies
GREETING_WORDS: Set[str] = {
    "hi", "hello", "hey", "heya", "howdy", "sup", "yo", "greetings",
    "good morning", "good afternoon", "good evening", "good day",
    "hey there", "hi there", "hello there",
}

COURTESY_WORDS: Set[str] = {
    "thanks", "thank you", "thank you so much", "thanks a lot", "thx", "ty",
    "much appreciated", "you're welcome", "welcome",
    "cool", "nice", "okay", "ok", "k", "great", "awesome", "got it", "sure",
    "perfect", "alright", "sounds good", "understood", "noted",
}

FAREWELL_WORDS: Set[str] = {
    "bye", "goodbye", "see you", "cya", "talk to you later", "have a good day",
    "good night", "night", "take care",
}

SOCIAL_QUESTIONS: Set[str] = {
    "how are you", "how are you doing", "hows it going", "how is it going",
    "how do you do", "what's up", "whats up", "how is everything",
}

BOT_IDENTITY: Set[str] = {
    "who are you", "what are you", "what is your name", "what can you do",
    "introduce yourself", "tell me about yourself",
}

# Document & Resume Keywords (triggers DOCUMENT_RAG)
DOCUMENT_KEYWORDS: Set[str] = {
    "resume", "cv", "curriculum vitae",
    "document", "documents", "doc", "docs", "file", "files", "pdf", "pdfs",
    "uploaded", "upload", "uploaded document", "uploaded file", "uploaded report",
    "project report", "internship report", "placement notes", "brochure",
}

# Known Companies for Placement Context
COMMON_COMPANIES: Set[str] = {
    "hcltech", "hcl", "tcs", "tata consultancy services", "google", "amazon",
    "microsoft", "infosys", "wipro", "cognizant", "accenture", "zoho",
    "ibm", "oracle", "capgemini", "lti", "ltimindtree", "tech mahindra",
    "cisco", "intel", "qualcomm", "deloitte", "ey", "pwc", "kpmg",
}

TECH_KEYWORDS: Set[str] = {
    # DevOps, containers, cloud
    "docker", "kubernetes", "k8s", "container", "containers", "containerization",
    "git", "github", "gitlab", "ci cd", "cicd", "jenkins", "linux", "unix", "bash", "shell",
    "nginx", "apache", "redis", "kafka", "rabbitmq", "celery", "aws", "gcp", "azure",
    # Networking & Web
    "api", "apis", "rest", "restful", "rest api", "graphql", "grpc", "soap",
    "microservice", "microservices", "monolith", "monolithic",
    "load balancer", "reverse proxy", "caching", "cache",
    "jwt", "token", "json web token", "oauth", "oauth2", "sso", "authentication", "authorization",
    "cors", "csrf", "xss", "encryption", "hashing", "bcrypt", "ssl", "tls", "https", "http",
    "tcp", "udp", "ip", "dns", "websocket", "socket",
    # AI & ML
    "gnn", "graph neural network", "rag", "retrieval augmented generation",
    "vector database", "pgvector", "embedding", "embeddings", "llm", "large language model",
    "neural network", "deep learning", "machine learning", "nlp", "transformer", "attention mechanism",
    # Databases & storage
    "sql", "nosql", "postgres", "postgresql", "mysql", "sqlite", "mongodb", "dynamodb",
    "database", "databases", "dbms", "rdbms", "orm", "sqlalchemy", "prisma", "alembic",
    "acid", "indexing", "indexes", "sharding", "replication",
    # Programming languages & frameworks
    "python", "javascript", "typescript", "c++", "cpp", "java", "golang", "go", "rust",
    "fastapi", "flask", "django", "express", "nodejs", "react", "vue", "angular", "nextjs",
    "pydantic", "asyncio", "multithreading", "concurrency", "coroutine", "generator",
    # Computer Science & Algorithms
    "data structure", "data structures", "algorithm", "algorithms",
    "binary search", "quicksort", "mergesort", "bubble sort", "bfs", "dfs",
    "recursion", "dynamic programming", "graph", "tree", "linked list", "hash table",
    "hash map", "stack", "queue", "heap", "priority queue", "big o", "time complexity",
    "space complexity", "solid principles", "design patterns", "singleton", "factory pattern",
    "dependency injection", "unit testing", "integration testing", "tdd",
}


COMPANY_NAME_MAP: Dict[str, str] = {
    "hcltech": "HCLTech",
    "hcl": "HCLTech",
    "tcs": "TCS",
    "tata consultancy services": "TCS",
    "google": "Google",
    "amazon": "Amazon",
    "microsoft": "Microsoft",
    "infosys": "Infosys",
    "wipro": "Wipro",
    "cognizant": "Cognizant",
    "accenture": "Accenture",
    "zoho": "Zoho",
    "ibm": "IBM",
    "oracle": "Oracle",
    "capgemini": "Capgemini",
    "lti": "LTIMindtree",
    "ltimindtree": "LTIMindtree",
    "tech mahindra": "Tech Mahindra",
    "cisco": "Cisco",
    "intel": "Intel",
    "qualcomm": "Qualcomm",
    "deloitte": "Deloitte",
    "ey": "EY",
    "pwc": "PwC",
    "kpmg": "KPMG",
}


def normalize_text(text: str) -> str:
    """Lowercases, strips leading/trailing punctuation and collapses whitespace."""
    cleaned = re.sub(r"[^\w\s]", " ", text.lower())
    return " ".join(cleaned.split())


def extract_company_entity(text: str) -> Optional[str]:
    """Extracts known company entity name from text, if present."""
    norm_text = normalize_text(text)
    for key, display_name in COMPANY_NAME_MAP.items():
        if re.search(rf"\b{re.escape(key)}\b", norm_text):
            return display_name
    return None


class IntentRouter:
    """
    Hybrid intent classification and routing service.
    Directs incoming messages to Casual, Profile, Document RAG, Placement, or General Knowledge.
    """

    def classify(
        self,
        message: str,
        conversation_history: Optional[List[Any]] = None,
    ) -> IntentRoutingResult:
        """
        Classifies user prompt using deterministic priority rules with conversational context awareness.
        """
        raw = message.strip()
        norm = normalize_text(raw)
        words = norm.split()
        word_count = len(words)

        if not raw:
            return IntentRoutingResult(
                intent=IntentCategory.CASUAL,
                confidence=1.0,
                use_rag=False,
                use_profile=False,
                use_placement=False,
                reasoning="Empty message treated as casual.",
            )

        # ---------------------------------------------------------
        # 1. Deterministic CASUAL Detection
        # ---------------------------------------------------------
        # Check exact casual phrases
        if norm in GREETING_WORDS or norm in COURTESY_WORDS or norm in FAREWELL_WORDS or norm in SOCIAL_QUESTIONS or norm in BOT_IDENTITY:
            return IntentRoutingResult(
                intent=IntentCategory.CASUAL,
                confidence=0.98,
                use_rag=False,
                use_profile=False,
                use_placement=False,
                reasoning="Matched exact greeting or social courtesy phrase.",
            )

        # Check short greeting / courtesy combinations (e.g. "hey karthik", "hello!", "thanks bro")
        if word_count <= 3:
            first_word = words[0] if words else ""
            if first_word in GREETING_WORDS or first_word in COURTESY_WORDS or first_word in FAREWELL_WORDS:
                # Ensure it's not a short technical query like "hi what is docker"
                if not any(w in norm for w in ["docker", "api", "cgpa", "resume", "placement", "code"]):
                    return IntentRoutingResult(
                        intent=IntentCategory.CASUAL,
                        confidence=0.97,
                        use_rag=False,
                        use_profile=False,
                        use_placement=False,
                        reasoning="Matched short greeting/courtesy prefix.",
                    )

        # ---------------------------------------------------------
        # 2. Contextual Follow-up Analysis (Multi-turn conversations)
        # ---------------------------------------------------------
        context_intent = self._check_contextual_followup(norm, words, conversation_history)
        if context_intent:
            return context_intent

        # ---------------------------------------------------------
        # 3. Explicit DOCUMENT_RAG Detection
        # ---------------------------------------------------------
        # If the user explicitly mentions their resume, uploaded documents, files, reports, etc.
        has_doc_reference = any(re.search(rf"\b{re.escape(k)}\b", norm) for k in DOCUMENT_KEYWORDS)
        doc_actions = ["summarize", "summary", "review", "find in", "search", "what does", "listed in", "according to"]
        has_doc_action = any(a in norm for a in doc_actions)

        if has_doc_reference and (has_doc_action or any(w in norm for w in ["resume", "cv", "report", "pdf", "file"])):
            return IntentRoutingResult(
                intent=IntentCategory.DOCUMENT_RAG,
                confidence=0.95,
                use_rag=True,
                use_profile=True,
                use_placement=False,
                reasoning="User explicitly requested information from uploaded documents or resume.",
            )

        # ---------------------------------------------------------
        # 4. PLACEMENT Intelligence Detection
        # ---------------------------------------------------------
        placement_patterns = [
            r"\bplacement(s)?\b",
            r"\bplacement drive(s)?\b",
            r"\bcampus placement\b",
            r"\bwhich compan(y|ies) am i eligible for\b",
            r"\bam i eligible\b",
            r"\beligib(le|ility)\b",
            r"\bqualif(y|ied)\b",
            r"\bpriorit(y|ize|ization)\b",
            r"\bplacement pipeline\b",
            r"\bplacement readiness\b",
            r"\bupcoming deadline(s)?\b",
            r"\bopen drive(s)?\b",
            r"\bcompare (my )?placement\b",
            r"\bcompare [a-z0-9\s]+ and [a-z0-9\s]+\b",
            r"\binterview prep(aration)?\b",
            r"\bwhat should i prepare for\b",
            r"\bwhat should i study for\b",
            r"\bwhich companies match my skills\b",
            r"\bskills i don t have\b",
            r"\bskills i dont have\b",
            r"\bselection process\b",
            r"\binterview rounds?\b",
            r"\bhiring pipeline\b",
        ]

        # Check known target company (e.g. "Tell me about HCLTech", "What is HCLTech?", "HCLTech interview")
        comp_entity = extract_company_entity(norm)
        if comp_entity:
            return IntentRoutingResult(
                intent=IntentCategory.PLACEMENT,
                confidence=0.95,
                use_rag=True,
                use_profile=True,
                use_placement=True,
                reasoning=f"Identified company '{comp_entity}' inquiry.",
                resolved_entity=comp_entity,
                is_followup=False,
            )

        if any(re.search(pat, norm) for pat in placement_patterns):
            return IntentRoutingResult(
                intent=IntentCategory.PLACEMENT,
                confidence=0.95,
                use_rag=True,
                use_profile=True,
                use_placement=True,
                reasoning="Matched recruitment, company eligibility, or interview preparation intent.",
                resolved_entity=comp_entity,
                is_followup=False,
            )

        # ---------------------------------------------------------
        # 5. PERSONAL_PROFILE Detection
        # ---------------------------------------------------------
        profile_patterns = [
            r"\bwho am i\b",
            r"\bwhat is my name\b",
            r"\bmy name\b",
            r"\btell me about myself\b",
            r"\bwhat do you know about me\b",
            r"\bmy profile\b",
            r"\bmy bio\b",
            r"\bmy summary\b",
            r"\b(my )?cgpa\b",
            r"\b(my )?gpa\b",
            r"\bmy marks\b",
            r"\bmy percentage\b",
            r"\bmy grade\b",
            r"\bwhere do i study\b",
            r"\buniversity\b",
            r"\bcollege\b",
            r"\binstitute\b",
            r"\bdegree\b",
            r"\bbranch\b",
            r"\bmajor\b",
            r"\bgraduation year\b",
            r"\bwhen do i graduate\b",
            r"\bgraduation\b",
            r"\beducation\b",
            r"\bacademics?\b",
            r"\bwhat skills do i have\b",
            r"\bwhat are my (technical )?skills\b",
            r"\bmy skills\b",
            r"\bwhat projects have i (done|built|worked on|completed)\b",
            r"\b(what\s+)?projects?\s+(do\s+i\s+have|have\s+i|did\s+i)\b",
            r"\b(my|our)\s+projects?\b",
            r"\bprojects?\s+(do\s+i\s+have|have\s+i|did\s+i|list|portfolio)\b",
            r"\b(describe|explain|tell me about|what is|overview of|summary of)\s+(the\s+|my\s+)?(.+\s+)?projects?\b",
            r"\b(features?|modules?|architecture|implementation details?|tech stack|technologies)\s+(in|of|for)\s+(the\s+|my\s+)?(.+\s+)?projects?\b",
            r"\bstudent management(\s+project)?\b",
            r"\bwhat certifications do i have\b",
            r"\bmy certifications\b",
            r"\bmy certs\b",
            r"\b(role in )?acm\b",
            r"\bmy email\b",
            r"\bmy phone\b",
            r"\bmy contact\b",
        ]

        if any(re.search(pat, norm) for pat in profile_patterns):
            return IntentRoutingResult(
                intent=IntentCategory.PERSONAL_PROFILE,
                confidence=0.95,
                use_rag=False,
                use_profile=True,
                use_placement=False,
                reasoning="Matched personal profile or verified credentials inquiry.",
            )

        # ---------------------------------------------------------
        # 6. GENERAL_KNOWLEDGE Technical Explanation Detection
        # ---------------------------------------------------------
        # Technical terms, concepts, architectures, and programming questions.
        has_personal_pronoun = any(re.search(rf"\b{p}\b", norm) for p in ["my", "mine", "myself", "i", "me"])
        has_tech_keyword = any(re.search(rf"\b{re.escape(tk)}\b", norm) for tk in TECH_KEYWORDS)

        if not has_personal_pronoun and has_tech_keyword:
            # Check for explanatory or question triggers
            tech_triggers = [
                "what", "explain", "how", "define", "why", "difference",
                "overview", "compare", "implement", "write", "code", "example",
            ]
            if any(t in norm for t in tech_triggers) or len(words) <= 4:
                return IntentRoutingResult(
                    intent=IntentCategory.GENERAL_KNOWLEDGE,
                    confidence=0.95,
                    use_rag=False,
                    use_profile=False,
                    use_placement=False,
                    reasoning="Matched technical concept or software engineering inquiry.",
                )

        # ---------------------------------------------------------
        # 7. Fallback / UNKNOWN
        # ---------------------------------------------------------
        # Avoid aggressive document retrieval; prefer conversational fallback.
        return IntentRoutingResult(
            intent=IntentCategory.UNKNOWN,
            confidence=0.50,
            use_rag=False,
            use_profile=False,
            use_placement=False,
            reasoning="Query did not match specific intent triggers; routing to conversational LLM.",
        )

    def _check_contextual_followup(
        self,
        norm: str,
        words: List[str],
        conversation_history: Optional[List[Any]],
    ) -> Optional[IntentRoutingResult]:
        """
        Analyzes conversation context for short follow-ups (e.g. 'What should I prepare?').
        """
        if not conversation_history or len(words) > 12:
            return None

        # Short follow-up phrases that rely on past context
        followup_prefixes = [
            "what should i prepare", "how should i prepare", "how to prepare",
            "what to prepare", "what should i study", "how should i study",
            "what should i focus on", "what are the rounds", "what rounds",
            "selection process", "interview process", "hiring process",
            "what else", "tell me more", "explain more", "and what", "how about",
            "why is that", "when is the deadline", "how do i install it", "give me an example",
            "what about", "and my", "how do i use it", "what requirements",
            "and what university", "and what college", "and my cgpa",
            "what features", "which features", "what are its", "what are the modules",
            "what modules", "describe it", "explain it", "tell me about it", "what is it",
            "how does it work", "how is it implemented", "what did i build in it",
        ]
        is_followup = any(norm.startswith(p) for p in followup_prefixes)

        if not is_followup:
            return None

        # Inspect the recent 2 messages (last turn)
        recent_text = ""
        for m in reversed(conversation_history[-4:]):
            content = getattr(m, "content", "") if not isinstance(m, dict) else m.get("content", "")
            recent_text += " " + content.lower()

        # Did recent turn discuss a company or placement?
        has_recent_company = any(c in recent_text for c in COMMON_COMPANIES)
        has_recent_placement = any(w in recent_text for w in ["placement", "interview", "drive", "eligible", "recruitment"])

        if has_recent_company or has_recent_placement:
            resolved_comp = extract_company_entity(recent_text)
            return IntentRoutingResult(
                intent=IntentCategory.PLACEMENT,
                confidence=0.92,
                use_rag=True,
                use_profile=True,
                use_placement=True,
                reasoning=f"Contextual follow-up continuing placement/company topic (Entity: {resolved_comp}).",
                resolved_entity=resolved_comp,
                is_followup=True,
            )

        # Did recent turn discuss general technology (e.g. Docker, API)?
        if any(t in recent_text for t in ["docker", "api", "gnn", "jwt", "kubernetes", "postgres"]):
            return IntentRoutingResult(
                intent=IntentCategory.GENERAL_KNOWLEDGE,
                confidence=0.90,
                use_rag=False,
                use_profile=False,
                use_placement=False,
                reasoning="Contextual follow-up continuing general technical topic.",
            )

        # Did recent turn discuss projects?
        if any(p in recent_text for p in ["project", "projects", "student management", "portfolio"]):
            resolved_proj = "Student management" if "student management" in recent_text else None
            return IntentRoutingResult(
                intent=IntentCategory.PERSONAL_PROFILE,
                confidence=0.92,
                use_rag=False,
                use_profile=True,
                use_placement=False,
                reasoning=f"Contextual follow-up continuing project topic (Entity: {resolved_proj}).",
                resolved_entity=resolved_proj,
                is_followup=True,
            )

        # Did recent turn discuss profile credentials (CGPA, degree)?
        if any(p in recent_text for p in ["cgpa", "gpa", "university", "degree", "branch"]):
            return IntentRoutingResult(
                intent=IntentCategory.PERSONAL_PROFILE,
                confidence=0.92,
                use_rag=False,
                use_profile=True,
                use_placement=False,
                reasoning="Contextual follow-up continuing personal profile topic.",
            )

        return None


intent_router = IntentRouter()
