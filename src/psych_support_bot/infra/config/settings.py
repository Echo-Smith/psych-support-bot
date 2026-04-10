from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "AI Psychological Support Bot"
    environment: str = "development"
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = "gpt-4.1-mini"
    database_url: str = "sqlite:///./psych_support_bot.db"
    redis_url: str = "redis://localhost:6379/0"
    langfuse_public_key: str = Field(default="", alias="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: str = Field(default="", alias="LANGFUSE_SECRET_KEY")
    langfuse_host: str = Field(
        default="https://cloud.langfuse.com", alias="LANGFUSE_HOST"
    )
    default_conversation_mode: str = "support"
    app_debug: bool = False


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
