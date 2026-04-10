from fastapi import FastAPI

from psych_support_bot.api.routes.conversation import router as conversation_router
from psych_support_bot.api.routes.health import router as health_router
from psych_support_bot.api.routes.system import router as system_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Psychological Support Bot API",
        version="0.1.0",
        description="Safety-first backend for a workflow-driven psychological support bot.",
    )

    app.include_router(health_router)
    app.include_router(system_router)
    app.include_router(conversation_router)
    return app


app = create_app()
