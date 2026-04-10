# Initial Backend Notes

## Current Stack

- FastAPI
- LangGraph
- Pydantic
- PostgreSQL
- Redis
- Celery
- Langfuse

## Initial API Endpoints

- `GET /health`
- `GET /system/info`
- `POST /v1/conversations/respond`

## First Workflow Behavior

- Risk classification runs first
- High-risk messages go to crisis mode
- Non-high-risk messages are routed to support, assessment, intervention, or planning mode
- Response is produced through a graph-based workflow scaffold
- A summary string is generated for future persistence hooks

## Current Limitation

- Main LLM generation is scaffolded and rule-backed for now
- Persistence and retrieval are not wired into runtime endpoints yet
- Safety classification is heuristic and must be replaced or augmented later
