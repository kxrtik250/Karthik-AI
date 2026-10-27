import re
from typing import List, Optional

from app.services.llm.base import BaseLLMProvider, ChatMessage, LLMResponse


class MockLLMProvider(BaseLLMProvider):
    """Deterministic local testing provider for Phase 6 RAG and Personal Context verification."""

    def __init__(self, model_name: str = "mock-llm"):
        self.model = model_name

    async def is_healthy(self) -> bool:
        return True

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        history: Optional[List[ChatMessage]] = None,
        temperature: float = 0.2,
    ) -> LLMResponse:
        prompt_lower = prompt.lower()
        source_tags = re.findall(r"\[Source \d+\]", prompt)
        tags_str = ", ".join(sorted(set(source_tags))) if source_tags else ""

        # 1. CGPA Question
        if "cgpa" in prompt_lower:
            m = re.search(r"cgpa:\s*([\d\.]+)(/10)?", prompt_lower)
            if m:
                cgpa_val = m.group(1)
                return LLMResponse(
                    content=f"Your current CGPA is {cgpa_val}/10.",
                    model=self.model,
                )

        # 2. University Question
        if "university" in prompt_lower or "college" in prompt_lower:
            m = re.search(r"university:\s*([^\n\r]+)", prompt, re.IGNORECASE)
            if m:
                uni_val = m.group(1).strip()
                return LLMResponse(
                    content=f"You study at {uni_val}.",
                    model=self.model,
                )

        # 3. ACM Role Question
        if "acm" in prompt_lower:
            if "media co-lead" in prompt_lower or "lead" in prompt_lower:
                return LLMResponse(
                    content="Your role in ACM is Media Co-Lead.",
                    model=self.model,
                )

        # 4. Technical Skills Question
        if "technical skills" in prompt_lower or "what are my skills" in prompt_lower:
            skills_found = []
            for line in prompt.splitlines():
                if line.strip().startswith("• ") and "Level:" in line or "Language" in line:
                    skills_found.append(line.replace("• ", "").strip())
            if skills_found:
                return LLMResponse(
                    content="Your technical skills include: " + ", ".join(skills_found) + ".",
                    model=self.model,
                )

        # 5. Projects Question
        if "what projects have i" in prompt_lower or "completed projects" in prompt_lower:
            projects_found = []
            for line in prompt.splitlines():
                if "• Project:" in line:
                    projects_found.append(line.replace("• Project:", "").strip())
            if projects_found:
                return LLMResponse(
                    content="Your completed projects include: " + ", ".join(projects_found) + ".",
                    model=self.model,
                )

        # 6. Certifications Question
        if "certification" in prompt_lower or "certifications do i have" in prompt_lower:
            certs_found = []
            for line in prompt.splitlines():
                if line.strip().startswith("• ") and ("by " in line or "Issued:" in line):
                    certs_found.append(line.replace("• ", "").strip())
            if certs_found:
                return LLMResponse(
                    content="Your certifications include: " + ", ".join(certs_found) + ".",
                    model=self.model,
                )

        # 7. Placement Drives Question
        if "placement drive" in prompt_lower or "placement drives am i tracking" in prompt_lower:
            drives_found = []
            for line in prompt.splitlines():
                if "• Company:" in line:
                    drives_found.append(line.replace("• Company:", "").strip())
            if drives_found:
                return LLMResponse(
                    content="You are tracking the following placement drives: " + "; ".join(drives_found) + ".",
                    model=self.model,
                )

        # 8. Carbon Footprint Project Technologies
        if "carbon footprint" in prompt_lower and ("technolog" in prompt_lower or "use" in prompt_lower):
            doc_cite = f" [{source_tags[0]}]" if source_tags else ""
            return LLMResponse(
                content=f"In your Carbon Footprint Tracker project, you utilized Python, FastAPI, React, and PostgreSQL for carbon emissions calculation and telemetry visualization{doc_cite}.",
                model=self.model,
            )

        # 9. Placement Improvement / Recommendations Question
        if "what should i improve for placement" in prompt_lower or "improve for placement" in prompt_lower:
            doc_cite = f" [{source_tags[0]}]" if source_tags else ""
            content = (
                "FACTS:\n"
                "- Your academic background is B.Tech in Computer Science with verified coursework in Data Structures and Algorithms.\n"
                "- Verified skills include Python, SQL, and FastAPI.\n\n"
                "OBSERVATIONS:\n"
                "- While your backend fundamentals are solid, your portfolio would benefit from production cloud deployment and system design case studies.\n\n"
                f"RECOMMENDATIONS:\n"
                "1. Deepen Data Structures & Algorithms practice on LeetCode/Codeforces with focus on Graphs and Dynamic Programming.\n"
                "2. Deploy your projects with containerization and CI/CD pipelines to demonstrate cloud infrastructure proficiency.\n"
                f"3. Refine resume impact metrics with quantifiable outcomes for key projects{doc_cite}."
            )
            return LLMResponse(
                content=content,
                model=self.model,
            )

        # 10. Document-only query fallback
        if "[DOCUMENT SOURCES]" in prompt and source_tags:
            return LLMResponse(
                content=f"Based on the provided documents ({tags_str}), the technical competencies include Python, TypeScript, FastAPI, PostgreSQL, and pgvector [Source 1].",
                model=self.model,
            )

        # 11. Empty / Missing context fallback
        return LLMResponse(
            content="Based on your personal profile and uploaded documents, there is not enough information to answer this question.",
            model=self.model,
        )
