from typing import Any, Dict, List, Optional
import httpx

from app.config import settings
from app.services.llm.base import BaseLLMProvider, ChatMessage, LLMResponse


class OllamaProvider(BaseLLMProvider):
    """Local LLM Provider using Ollama HTTP API."""

    def __init__(
        self,
        base_url: str = settings.ollama_base_url,
        model: str = settings.ollama_model,
        timeout: float = 60.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    async def is_healthy(self) -> bool:
        """Check if Ollama server is up and responsive."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(f"{self.base_url}/api/tags")
                return res.status_code == 200
        except Exception:
            return False

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        history: Optional[List[ChatMessage]] = None,
        temperature: float = 0.2,
    ) -> LLMResponse:
        """
        Calls Ollama's /api/chat endpoint with messages array.
        """
        messages: List[Dict[str, str]] = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        if history:
            for msg in history:
                messages.append({"role": msg.role, "content": msg.content})

        messages.append({"role": "user", "content": prompt})

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(f"{self.base_url}/api/chat", json=payload)
                if res.status_code != 200:
                    raise RuntimeError(
                        f"Ollama returned HTTP {res.status_code}: {res.text}"
                    )
                data = res.json()
                message_content = data.get("message", {}).get("content", "").strip()
                return LLMResponse(
                    content=message_content,
                    model=self.model,
                    usage={
                        "total_duration": data.get("total_duration"),
                        "prompt_eval_count": data.get("prompt_eval_count"),
                        "eval_count": data.get("eval_count"),
                    },
                    raw_response=data,
                )
        except httpx.ConnectError:
            raise RuntimeError(
                f"Could not connect to Ollama at '{self.base_url}'. "
                "Ensure Ollama is running and accessible."
            )
        except Exception as e:
            raise RuntimeError(f"Ollama generation failed: {str(e)}")
