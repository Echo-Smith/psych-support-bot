from psych_support_bot.infra.queue.celery_app import celery_app


@celery_app.task(name="psych_support_bot.ping")
def ping() -> str:
    return "pong"
