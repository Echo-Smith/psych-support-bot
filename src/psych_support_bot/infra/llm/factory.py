from functools import lru_cache

from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from psych_support_bot.infra.config.settings import get_settings


@lru_cache(maxsize=1)
def build_chat_model() -> ChatOpenAI:
    settings = get_settings()
    key = SecretStr(settings.openai_api_key) if settings.openai_api_key else None
    return ChatOpenAI(
        model=settings.openai_model,
        api_key=key,
        base_url=settings.openai_base_url or None,
        temperature=0.0,
        default_headers={"api-key": settings.openai_api_key},
    )
