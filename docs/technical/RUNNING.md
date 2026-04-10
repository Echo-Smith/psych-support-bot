# Running The Backend

## Local

```bash
uv sync
uv run alembic upgrade head
uv run uvicorn psych_support_bot.app:app --reload
```

## Tests

```bash
uv run pytest
uv run psych-support-bot-evals
```

## Docker

```bash
docker compose up --build
```

The API starts on `http://localhost:8000`.
