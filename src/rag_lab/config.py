from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables or .env."""

    app_name: str = "RAG Reliability Lab"
    database_url: str = "postgresql+psycopg://rag_lab:rag_lab_dev@localhost:55433/rag_lab"
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    qdrant_timeout_seconds: float = 5.0
    minio_endpoint: str = "http://localhost:9000"
    minio_root_user: str = "rag_lab_minio"
    minio_root_password: str = "rag_lab_minio_dev"
    minio_bucket: str = "rag-lab-documents"
    minio_secure: bool = False
    minio_region: str = "us-east-1"
    max_upload_size_bytes: int = 10 * 1024 * 1024

    model_config = SettingsConfigDict(env_file=".env", env_prefix="RAG_LAB_", extra="ignore")


settings = Settings()
