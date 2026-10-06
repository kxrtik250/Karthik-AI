"""Application configuration loaded from environment variables."""

import os
from pathlib import Path
from pydantic_settings import BaseSettings

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent


class Settings(BaseSettings):
    """App settings. Values are read from environment variables or .env file."""

    database_url: str = "postgresql+asyncpg://karthik_ai:karthik_ai_dev@localhost:5432/karthik_ai_db"
    app_name: str = "Karthik AI"
    debug: bool = True

    # Document storage configuration
    upload_dir: str = str(PROJECT_ROOT / "uploads" / "documents")
    max_file_size_mb: int = 25  # 25 MB max limit

    # Embedding configuration
    embedding_model_name: str = "BAAI/bge-small-en-v1.5"
    embedding_dimension: int = 384

    # LLM configuration
    llm_provider: str = "ollama"  # ollama, gemini (future)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:1b"

    # RAG configuration (initial values, can be tuned with evaluation data)
    rag_top_k: int = 5
    rag_similarity_threshold: float = 0.50

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()

# Ensure upload directory exists
os.makedirs(settings.upload_dir, exist_ok=True)
