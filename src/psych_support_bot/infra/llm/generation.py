from langchain_core.messages import HumanMessage, SystemMessage

from psych_support_bot.ai.prompts.templates import (
    build_boundary_prompt,
    build_context_prompt,
    build_output_prompt,
    build_role_prompt,
)
from psych_support_bot.infra.llm.factory import build_chat_model


def generate_clinically_bounded_reply(
    user_message: str,
    mode: str,
    risk_level: str,
    memory_summary: str,
    knowledge_context: str,
) -> str:
    model = build_chat_model()
    system_prompt = "\n\n".join(
        [
            build_role_prompt(),
            build_boundary_prompt(risk_level=risk_level),
            build_context_prompt(
                memory_summary=memory_summary,
                knowledge_context=knowledge_context,
            ),
            build_output_prompt(mode=mode, risk_level=risk_level),
        ]
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
