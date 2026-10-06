from app.config import settings
from app.services.llm.base import BaseLLMProvider
from app.services.llm.mock_provider import MockLLMProvider
from app.services.llm.ollama_provider import OllamaProvider


def get_llm_provider() -> BaseLLMProvider:
    """Factory returning the configured LLM provider."""
    provider_name = settings.llm_provider.lower().strip()
    if provider_name == "ollama":
        return OllamaProvider(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
        )
    elif provider_name in ["mock", "test"]:
        return MockLLMProvider()
    raise ValueError(f"Unsupported LLM provider: '{settings.llm_provider}'")
