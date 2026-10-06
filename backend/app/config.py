"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """App settings. Values are read from environment variables or .env file."""

    database_url: str = "postgresql+asyncpg://karthik_ai:karthik_ai_dev@localhost:5432/karthik_ai_db"
    app_name: str = "Karthik AI"
    debug: bool = True

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
