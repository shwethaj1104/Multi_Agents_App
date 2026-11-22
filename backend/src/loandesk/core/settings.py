from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIRECTORY = Path(__file__).resolve().parents[3]
ReviewMode = Literal["single_agent", "multi_agent"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LOANDESK_",
        env_file=BACKEND_DIRECTORY / ".env",
        extra="ignore",
        populate_by_name=True,
    )
    review_mode: ReviewMode = "single_agent"
    storage_backend: Literal["auto", "sqlite", "mongodb"] = "auto"
    runtime_directory: Path = BACKEND_DIRECTORY.parent / ".runtime"
    mongodb_uri: SecretStr = Field(default=SecretStr(""), validation_alias="MONGODB_URI")
    mongodb_database: str = Field(default="loandesk", validation_alias="MONGODB_DATABASE")
    openai_api_key: SecretStr = Field(default=SecretStr(""), validation_alias="OPENAI_API_KEY")
    live_model_calls_enabled: bool = False
    model: str = "gpt-5.6-luna"
    reasoning_effort: Literal["none", "low", "medium"] = "low"
    max_output_tokens: int = Field(default=2048, ge=256, le=8192)
    max_model_calls_per_review: int = Field(default=10, ge=5, le=30)
    max_follow_up_rounds: int = Field(default=1, ge=0, le=3)
    model_max_retries: int = Field(default=1, ge=0, le=2)
    review_budget_usd: float = Field(default=0.10, gt=0, le=2)
    session_budget_usd: float = Field(default=2.0, gt=0, le=20)
    langsmith_tracing: bool = Field(default=False, validation_alias="LANGSMITH_TRACING")
    langsmith_api_key: SecretStr = Field(
        default=SecretStr(""), validation_alias="LANGSMITH_API_KEY"
    )
    langsmith_endpoint: str = Field(
        default="https://api.smith.langchain.com", validation_alias="LANGSMITH_ENDPOINT"
    )
    langsmith_agent_id: str = Field(default="", validation_alias="LANGSMITH_AGENT_ID")
    langsmith_agent_environment: str = Field(
        default="local", validation_alias="LANGSMITH_AGENT_ENVIRONMENT"
    )
    langsmith_project: str = Field(default="", validation_alias="LANGSMITH_PROJECT")
    access_token: SecretStr = SecretStr("")

    # Resolve the storage adapter explicitly; never silently fall back after a MongoDB failure.
    @property
    def resolved_storage(self) -> str:
        if self.storage_backend != "auto":
            return self.storage_backend
        return "mongodb" if self.mongodb_uri.get_secret_value() else "sqlite"


# Cache one private server configuration; credentials are never returned through the API.
@lru_cache
def get_settings() -> Settings:
    return Settings()
