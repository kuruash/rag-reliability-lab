from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables or .env."""

    app_name: str = "RAG Reliability Lab"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/rag_lab"

    model_config = SettingsConfigDict(env_file=".env", env_prefix="RAG_LAB_", extra="ignore")


settings = Settings()
