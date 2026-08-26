# Project Progress Tracker

## Current Status

- Project state: P1 complete, P2 (product usability) ready to start
- Delivery focus: AI framework foundation and execution-ready roadmap
- Recommended stack locked for first implementation:
  - `FastAPI`
  - `LangGraph`
  - `Pydantic`
  - `PostgreSQL`
  - `pgvector`
  - `Redis`
  - `Celery`
  - `Langfuse`
- Current implementation status:
  - Git repository initialized
  - Python project initialized with `uv`
  - FastAPI app scaffolded
  - LangGraph conversation workflow implemented with risk-first routing
  - Multi-school consultation planner added for diagnosis/treatment-style turns
  - Base config, DB, Redis, Celery, and tracing modules scaffolded
  - SQLite-backed persistence added for local MVP development
  - Assessment, check-in, plan, and weekly report APIs added
  - Alembic migration baseline added
  - Basic integration and evaluation tests added

## Milestones

| Milestone | Goal | Status | Target Output |
| --- | --- | --- | --- |
| M0 | Confirm scope and architecture | Done | Project plan and progress tracker |
| M1 | Initialize backend project skeleton | Done | Running FastAPI app and base folders |
| M2 | Implement AI workflow skeleton | Done | LangGraph flow with risk and routing nodes |
| M3 | Implement persistence layer | Done | DB models, migrations, repository layer |
| M4 | Implement core domain APIs | Done | Conversation, assessment, check-in APIs |
| M5 | Implement safety and observability | Done | Risk logs, Langfuse trace_span on 8 nodes, A/B/C 3-layer eval harness |
| M6 | MVP integration complete | Done | End-to-end support flow, intervention plans, release checklist |
| M7 | Phase 2: Product usability | Not started | pgvector, model routing, async tasks, Chinese KB |

## Workstreams

### 1. Foundation

| Task | Priority | Status | Notes |
| --- | --- | --- | --- |
| Create repository structure | High | Done | src package, docs, tests scaffolded |
| Set up Python environment and dependency management | High | Done | Using `uv` |
| Create FastAPI app entrypoint | High | Done | Health route and config loading |
| Add environment configuration | High | Done | `.env.example` and settings module added |

### 2. AI Orchestration

| Task | Priority | Status | Notes |
| --- | --- | --- | --- |
| Define graph state schema | High | Done | Shared LangGraph state object |
| Build risk classifier node | High | Done | Safety-first gate |
| Build intent router node | High | Done | support, assessment, intervention, planning, crisis |
| Build multidisciplinary consultation planner | High | Done | CBT, psychodynamic, humanistic, ACT, DBT orchestration |
| Build memory retrieval node | Medium | Done | Placeholder memory loading |
| Build response generator node | High | Done | Initial scaffolded reply generation |
| Build safety reviewer node | High | Done | Post-generation review hook |
| Build summary writer node | Medium | Done | Summary string scaffold |

### 3. Domain and Data

| Task | Priority | Status | Notes |
| --- | --- | --- | --- |
| Design core DB schema | High | Done | users, sessions, messages, assessments, checkins, risks, reports |
| Add migration tool | High | Done | Alembic baseline added |
| Implement repositories/services | Medium | Done | Conversation and domain repositories added |
| Add pgvector support | Medium | Not started | Keep for future memory retrieval/RAG phase |

### 4. Safety and Evaluation

| Task | Priority | Status | Notes |
| --- | --- | --- | --- |
| Define risk levels and contracts | High | Done | Low/elevated/high/critical scaffold added |
| Create risk regression dataset | High | Done | 22 cases in cases.json covering 9 scenario types, Chinese + English |
| Build evaluation runner | High | Done | B-layer runner with 4-dimension checks; A-layer 54 regex tests; C-layer LLM-as-judge |
| Add Langfuse tracing | Medium | Done | Node-level trace_span instrumentation on all 8 nodes |
| Create release safety checklist | High | Done | `docs/technical/RELEASE_CHECKLIST.md` with 6-gate strict standard |
| Add LLM-as-judge evaluation layer | High | Done | C-layer DeepSeek-V4-Flash judge with 4-dimension scoring |
| Fill intervention plan daily content | High | Done | 3 plan templates with daily actions and reflection prompts |

### 5. Product Logic

| Task | Priority | Status | Notes |
| --- | --- | --- | --- |
| Implement PHQ-9, GAD-7, ISI schemas | High | Done | Assessment schema and severity service added |
| Implement daily check-in model | Medium | Done | API and persistence added |
| Implement intervention plan templates | Medium | Done | Starter plan service added |
| Implement weekly report generator | Medium | Done | Summary generation and report endpoint added |

## Suggested Execution Order

1. Repository skeleton and dependency setup
2. FastAPI app and config system
3. Pydantic contracts and AI state schemas
4. LangGraph workflow skeleton
5. Risk classifier and crisis routing
6. Persistence layer and migrations
7. Core conversation API
8. Assessments and check-ins
9. Tracing and evaluation harness
10. Weekly summaries and intervention plans

## Definition of Done for MVP Foundation

- FastAPI service starts locally
- Conversation endpoint runs through LangGraph
- Risk classification always executes before normal response generation
- Crisis mode blocks normal support flow when required
- Core entities persist to PostgreSQL
- Basic tracing is visible in Langfuse
- Offline evaluation command can run predefined safety cases

## Immediate Next Actions (P2)

- [ ] pgvector semantic retrieval — improve metaphor expression matching (#15)
- [ ] LLM model routing + fallback strategy — lightweight model for simple support, strong model for complex consultation (#16)
- [ ] Knowledge base Chinese sources — supplement authoritative Chinese psychology content (#17)
- [ ] Redis/Celery async tasks — async summary write, scheduled weekly report generation (#18)
- [ ] Exhaustion subtype differentiation — physical/emotional/relationship/anticipatory (#19)
- [ ] Semantic memory retrieval — prevent context loss beyond 3 sessions (#20)

## Progress Log

### 2026-04-10

- Created `PROJECT_PLAN.md`
- Created `PROJECT_PROGRESS.md`
- Locked recommended AI framework and first-stage stack
- Recorded execution order for implementation
- Initialized git repository
- Initialized Python project with `uv`
- Added FastAPI app scaffold and core routes
- Added LangGraph workflow scaffold with risk-first routing
- Added settings, DB, cache, queue, and tracing scaffolds
- Added initial assessment, check-in, and plan schema files
- Added basic integration tests
- Added SQLite-backed persistence and repositories
- Added assessment, check-in, plan, and weekly report APIs
- Added Alembic baseline migration files
- Added LLM-backed response generation with safe fallback
- Added API and risk evaluation tests

### 2026-08-26 (P1 Complete)

- Moved `index.html` to `dev/index.html` (development version retained)
- Created `docs/technical/RELEASE_CHECKLIST.md` — strict 6-gate release standard (100% pass required)
- Added Langfuse `trace_span` instrumentation on all 8 LangGraph nodes (risk_classifier, intent_router, consultation_planner, memory_loader, knowledge_loader, response_generator, safety_reviewer, summary_writer)
- Created `src/psych_support_bot/evals/judge.py` — LLM-as-judge C-layer evaluation:
  - 4 dimensions: attribution_safety, boundary, empathy, action_appropriateness (1-5 scale)
  - Judge model: DeepSeek-V4-Flash via dedicated API endpoint
  - `score_reply()` — single-case judge scoring with JSON output parsing
  - `run_judge_eval()` — batch judge over B-layer results
  - `export_human_judge_table()` — Markdown scorecard for manual review
  - Langfuse trace span `judge.llm_invoke` for observability
- Created `tests/evals/test_judge.py` — 5 basic tests + 1 smoke test (all passing)
- Updated `EVAL_GUIDE.md` with C-layer documentation (positioning, 4 dimensions, judge config, execution flow, relationship to B-layer)
- Created `EVAL_REPORT_JUDGE.md` — C-layer evaluation report template (pending first run)
- Filled 3 intervention plan templates in `domain/plans/templates.py`:
  - `anxiety_management_7day` — CBT-based daily actions + reflection prompts
  - `sleep_hygiene_7day` — ISI-aligned daily sleep routines
  - `mood_monitoring_7day` — PHQ-9 tracking + behavioral activation
- Implemented `PlanEnrollment` DB model + plans service + API routes (enrollment, progress query, daily completion toggle)
- All 54 unit tests + 6 judge tests passing; lint clean
