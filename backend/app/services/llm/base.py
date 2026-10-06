from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ChatMessage:
    role: str  # "system", "user", "assistant"
    content: str


@dataclass
class LLMResponse:
    content: str
    model: str
    usage: Dict[str, Any] = field(default_factory=dict)
    raw_response: Any = None


class BaseLLMProvider(ABC):
    """Abstract interface for LLM providers (Ollama, Gemini, etc.)."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        history: Optional[List[ChatMessage]] = None,
        temperature: float = 0.2,
    ) -> LLMResponse:
        """Generate a completion for the given prompt, optional system instruction, and history."""
        pass

    @abstractmethod
    async def is_healthy(self) -> bool:
        """Check if the LLM provider service is available and ready."""
        pass
