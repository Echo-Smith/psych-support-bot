from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from psych_support_bot.infra.config.settings import get_settings


def build_chat_model() -> ChatOpenAI:
    settings = get_settings()
    key = SecretStr(settings.openai_api_key) if settings.openai_api_key else None
    return ChatOpenAI(
        model=settings.openai_model,
        api_key=key,
        temperature=0.2,
    )
