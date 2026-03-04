from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Note: dotfiles may be blocked in this environment; prefer `env.local` in the repo root.
    model_config = SettingsConfigDict(env_file=("env.local", ".env"), env_file_encoding="utf-8", extra="ignore")

    app_env: str = "dev"
    database_url: str = "sqlite:///./keytruda.dev.db"

    # External integrations (keys provided via env.local / environment)
    claude_api_key: str | None = None
    # Use the currently recommended Claude Sonnet model for messages API.
    claude_extraction_model: str = "claude-sonnet-4-6"
    claude_reasoning_model: str = "claude-sonnet-4-6"
    claude_stub: bool = False  # real Claude API by default; set true only for offline stubbing
    
    # OpenAI for embeddings
    openai_api_key: str | None = None
    embedding_model: str = "text-embedding-3-small"  # 1536 dimensions
    
    # Pinecone vector database
    pinecone_api_key: str | None = None
    pinecone_index: str = "pubmedembeding"  # Your Pinecone index name
    pinecone_environment: str = "us-east-1"
    pinecone_cloud: str = "aws"
    pinecone_host: str | None = None  # Optional: direct host URL if needed

    # PubMed
    pubmed_email: str | None = None
    pubmed_tool: str = "keytruda-safety-signal"
    pubmed_api_key: str | None = None  # optional: increases E-utilities rate limit when set


settings = Settings()


