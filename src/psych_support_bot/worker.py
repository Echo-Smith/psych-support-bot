from psych_support_bot.infra.queue.celery_app import celery_app
from psych_support_bot.workers.report_tasks import generate_weekly_report, ping

celery_app.autodiscover_tasks(["psych_support_bot.workers"])
