from contextlib import asynccontextmanager

from fastapi import FastAPI

from psych_support_bot.api.routes.analytics import router as analytics_router
from psych_support_bot.api.routes.assessments import router as assessments_router
from psych_support_bot.api.routes.checkins import router as checkins_router
from psych_support_bot.api.routes.conversation import router as conversation_router
from psych_support_bot.api.routes.exercises import router as exercises_router
from psych_support_bot.api.routes.health import router as health_router
from psych_support_bot.api.routes.plans import router as plans_router
from psych_support_bot.api.routes.reports import router as reports_router
from psych_support_bot.api.routes.system import router as system_router
from psych_support_bot.api.routes.users import router as users_router
from psych_support_bot.infra.db.init_db import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Psychological Support Bot API",
        version="0.1.0",
        description="Safety-first backend for a workflow-driven psychological support bot.",
        lifespan=lifespan,
    )

    app.include_router(health_router)
    app.include_router(system_router)
    app.include_router(conversation_router)
    app.include_router(assessments_router)
    app.include_router(checkins_router)
    app.include_router(plans_router)
    app.include_router(reports_router)
    app.include_router(users_router)
    app.include_router(analytics_router)
    app.include_router(exercises_router)
    return app


app = create_app()
