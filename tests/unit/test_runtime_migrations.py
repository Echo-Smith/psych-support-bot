"""Exercise upgrade paths for databases created by the upstream main app."""

from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from psych_support_bot.infra.db.base import Base
from psych_support_bot.infra.db.migration_runner import run_migrations


def test_fresh_database_and_repeat_startup(tmp_path):
    url = f"sqlite:///{tmp_path / 'fresh.db'}"
    run_migrations(url)
    run_migrations(url)
    engine = sa.create_engine(url)
    try:
        _assert_current_schema(engine)
    finally:
        engine.dispose()


def test_main_create_all_database_keeps_existing_user(tmp_path):
    url = f"sqlite:///{tmp_path / 'legacy.db'}"
    engine = sa.create_engine(url)
    try:
        cfg = Config()
        cfg.set_main_option(
            "script_location", str(Path(__file__).parents[2] / "src/psych_support_bot/infra/db/migrations")
        )
        with engine.begin() as conn:
            cfg.attributes["connection"] = conn
            command.upgrade(cfg, "20260820_0001")
            conn.execute(sa.text("DROP TABLE alembic_version"))
        with engine.begin() as conn:
            conn.execute(sa.text("INSERT INTO users (id, created_at) VALUES ('legacy-user', '2026-01-01')"))
        run_migrations(url)
        with engine.connect() as conn:
            assert conn.execute(sa.text("SELECT id FROM users")).scalar_one() == "legacy-user"
    finally:
        engine.dispose()


def test_versioned_main_database_adds_questionnaire_fields(tmp_path):
    url = f"sqlite:///{tmp_path / 'versioned.db'}"
    cfg = Config()
    cfg.set_main_option("script_location", str(Path(__file__).parents[2] / "src/psych_support_bot/infra/db/migrations"))
    cfg.set_main_option("sqlalchemy.url", url)
    engine = sa.create_engine(url)
    try:
        with engine.begin() as conn:
            cfg.attributes["connection"] = conn
            command.upgrade(cfg, "20260410_0002")
        run_migrations(url)
        columns = {column["name"] for column in sa.inspect(engine).get_columns("assessments")}
        assert "needs_safety_followup" in columns
        _assert_current_schema(engine)
    finally:
        engine.dispose()


def test_unknown_unversioned_database_is_not_stamped(tmp_path):
    url = f"sqlite:///{tmp_path / 'unknown.db'}"
    engine = sa.create_engine(url)
    try:
        with engine.begin() as conn:
            conn.execute(sa.text("CREATE TABLE users (id TEXT PRIMARY KEY)"))
        with pytest.raises(RuntimeError, match="refusing to stamp"):
            run_migrations(url)
        assert "alembic_version" not in sa.inspect(engine).get_table_names()
    finally:
        engine.dispose()


def _assert_current_schema(engine):
    inspector = sa.inspect(engine)
    assert set(Base.metadata.tables).issubset(inspector.get_table_names())
    for name, table in Base.metadata.tables.items():
        expected = {column.name for column in table.columns}
        actual = {column["name"] for column in inspector.get_columns(name)}
        assert expected.issubset(actual), (name, expected - actual)


def test_database_url_with_percent_is_supported(tmp_path, monkeypatch):
    from psych_support_bot.infra.config.settings import get_settings

    url = f"sqlite:///{tmp_path / 'percent%database.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()
    try:
        run_migrations(url)
        engine = sa.create_engine(url)
        try:
            _assert_current_schema(engine)
        finally:
            engine.dispose()
    finally:
        get_settings.cache_clear()


def test_upgrade_keeps_preexisting_plan_enrollment(tmp_path):
    from datetime import UTC, datetime

    url = f"sqlite:///{tmp_path / 'existing-plan.db'}"
    engine = sa.create_engine(url)
    cfg = Config()
    cfg.set_main_option("script_location", str(Path(__file__).parents[2] / "src/psych_support_bot/infra/db/migrations"))
    try:
        with engine.begin() as conn:
            cfg.attributes["connection"] = conn
            command.upgrade(cfg, "c1d3dc0400bd")
        table = Base.metadata.tables["plan_enrollments"]
        table.create(engine)
        now = datetime.now(UTC)
        with engine.begin() as conn:
            conn.execute(
                table.insert().values(
                    id="existing-plan",
                    user_id="legacy-user",
                    plan_id="grounding",
                    enrolled_at=now,
                    updated_at=now,
                    completed_days_json="[1]",
                    current_day=2,
                    status="active",
                )
            )
        run_migrations(url)
        with engine.connect() as conn:
            assert (
                conn.execute(sa.text("SELECT current_day FROM plan_enrollments WHERE id='existing-plan'")).scalar_one()
                == 2
            )
        _assert_current_schema(engine)
    finally:
        engine.dispose()
