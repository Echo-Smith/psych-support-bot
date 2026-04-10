from psych_support_bot.infra.db.base import Base
from psych_support_bot.infra.db.session import engine


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
