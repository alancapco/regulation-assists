from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

# Repo root .env is the single source of truth (not backend/.env).
_REPO_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILE = _REPO_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    neo4j_uri: str = "bolt://localhost:7688"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "capco-graph-change-me"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    log_level: str = "INFO"
    total_count: int = 1174
    graph_max_nodes: int = 500  # Increased to show more of the graph
    graph_reg_limit: int = 200  # Increased to show more regulations
    llm_timeout_test: float = 10.0
    llm_timeout_ask: float = 30.0

    # Postgres (content store + pgvector)
    postgres_host: str = "localhost"
    postgres_port: int = 5433
    postgres_user: str = "capco"
    postgres_password: str = "capco-regulation-change-me"
    postgres_db: str = "regulation_assistant"

    # OpenAI (for embeddings — reuses same key as LLM if set)
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
