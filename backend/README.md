# AI Tutor — Backend

FastAPI app managed with [`uv`](https://docs.astral.sh/uv/). Entry point: `src/main.py` (`src.main:app`).

See the repo root for full docs: [Architecture](../docs/ARCHITECTURE.md) · [API reference](../docs/API.md) · [Development guide](../docs/DEVELOPMENT.md).

## Layout

```
src/
  main.py          FastAPI app, router registration, startup recovery
  config.py        Settings (env vars / .env)
  db.py            Async SQLAlchemy engine/session
  models.py        ORM models
  schemas.py       Pydantic request/response models
  deps.py          FastAPI dependencies (auth, DB session, tutor graph)
  routers/         auth, technologies, resources, retrieval, conversations, health
  services/
    security.py, slugs.py, llm.py, vector_store.py, retrieval.py, chat.py,
    prompts.py, study_plan.py, lookups.py
    ingestion/     fetcher, extractor, splitter, pipeline
    tutor_graph/   state, schemas, nodes, graph (LangGraph)
  scripts/         create_admin, promote_user, eval_scope
alembic/           DB migrations
evals/             scope_cases.yaml (classifier eval set)
tests/             pytest suite
```

## Commands

```bash
uv sync                                                        # install dependencies
uv run alembic upgrade head                                    # apply migrations
uv run uvicorn src.main:app --host 0.0.0.0 --port 80 --reload  # dev server
uv run pytest                                                   # tests (needs Postgres+pgvector; see DEVELOPMENT.md)
uv run python -m src.scripts.create_admin --email you@example.com
uv run python -m src.scripts.eval_scope                        # needs a real OPENAI_API_KEY
```

Normally you'd run this via Docker Compose from the repo root instead — see the [quick start](../README.md#quick-start).
