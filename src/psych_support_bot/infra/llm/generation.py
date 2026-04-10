from langchain_core.messages import HumanMessage, SystemMessage

from psych_support_bot.ai.prompts.templates import build_system_guidance
from psych_support_bot.infra.llm.factory import build_chat_model


def generate_clinically_bounded_reply(
    user_message: str,
    mode: str,
    risk_level: str,
    memory_summary: str,
) -> str:
    model = build_chat_model()
    system_prompt = (
        "You are a safety-first AI psychological support assistant. "
        "You support mild-to-moderate users only. "
        "Do not diagnose. Do not claim to replace therapists or doctors. "
        "Keep responses concise, grounded, and structured. "
        f"Mode guidance: {build_system_guidance(mode=mode, risk_level=risk_level)} "
        f"Known memory summary: {memory_summary or 'No prior memory.'}"
    )
    response = model.invoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ]
    )
    content = response.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(str(item) for item in content)
    return str(content)
