import re
from typing import List, Optional

from app.services.llm.base import BaseLLMProvider, ChatMessage, LLMResponse


class MockLLMProvider(BaseLLMProvider):
    """Deterministic local testing provider for RAG verification."""

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
        # Extract sources from prompt
        source_tags = re.findall(r"\[Source \d+\]", prompt)
        tags_str = ", ".join(sorted(set(source_tags))) if source_tags else "No sources provided"

        # Check if context was provided
        if "Retrieved Document Context:" in prompt and source_tags:
            content = (
                f"Based on the provided documents ({tags_str}), the technical competencies include "
                f"Python, TypeScript, FastAPI, PostgreSQL, and pgvector [Source 1]."
            )
        else:
            content = "Based on your uploaded documents, there is not enough information to answer this question."

        return LLMResponse(
            content=content,
            model=self.model,
            usage={"prompt_tokens": 50, "completion_tokens": 20},
        )
