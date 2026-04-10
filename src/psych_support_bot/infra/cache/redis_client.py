from redis import Redis

from psych_support_bot.infra.config.settings import get_settings


def get_redis_client() -> Redis:
    settings = get_settings()
    return Redis.from_url(settings.redis_url)
