from langchain_openai import ChatOpenAI

from psych_support_bot.infra.config.settings import get_settings


def build_chat_model() -> ChatOpenAI:
    settings = get_settings()
    return ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key or None,
        temperature=0.2,
    )
