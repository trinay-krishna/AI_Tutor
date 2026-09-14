# Development Guide

## Prerequisites

- Docker Desktop (recommended path — see below), or:
- Python 3.11 + [`uv`](https://docs.astral.sh/uv/) for the backend, and [`bun`](https://bun.sh) for the frontend, plus a local Postgres 17 with the `pgvector` extension available.
- An OpenAI API key with access to a chat model and an embeddings model.

## Quick start (Docker Compose)

```bash
cp .env.example .env      # fill in OPENAI_API_KEY at minimum
docker compose up --build
docker compose exec backend uv run python -m src.scripts.create_admin --email you@example.com
```

- Frontend: http://localhost:5173
- Backend directly: http://localhost:8000 (e.g. http://localhost:8000/api/health)
- Postgres: `localhost:5432` (`postgres`/`postgres` by default — see `.env.example`)

Alembic migrations run automatically on backend startup. The `backend` volume mounts your local source into the container for live reload (`uvicorn --reload`); `frontend` does the same via Vite's dev server.

**After adding a frontend dependency** (`bun add ...`), the container's `node_modules` volume goes stale — refresh it with:
```bash
docker compose up -d --build -V frontend
```

## Environment variables (`.env`)

See `.env.example` for the full annotated list. The ones you're most likely to touch:

| Variable | Default | Notes |
|---|---|---|
| `OPENAI_API_KEY` | – | Required for anything beyond `/api/health`. |
| `OPENAI_CHAT_MODEL` | `gpt-4o` | Main generation model. |
| `OPENAI_FAST_MODEL` | `gpt-4o-mini` | Scope classifier — keep this cheap, it runs on every message. |
| `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small` | Changing this changes vector dimension — see [Changing the embedding model](#changing-the-embedding-model). |
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@db:5432/ai_tutor` | Use `localhost` instead of `db` when running the backend outside Docker. |
| `RAG_MIN_SIMILARITY` | `0.35` | Below this, retrieval is treated as "nothing found" (general-knowledge mode). Tune with the admin "Test retrieval" box against real scores before changing. |
| `COOKIE_SECURE` | `false` | Set `true` once the app is served over HTTPS — cookies otherwise won't be sent by browsers. |

## Backend development (without Docker)

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn src.main:app --host 0.0.0.0 --port 80 --reload
```

Set `DATABASE_URL` to point at a Postgres you control (with `CREATE EXTENSION vector` available/run — the first Alembic migration does this for you as long as the connecting role can `CREATE EXTENSION`).

### Running tests

```bash
cd backend
# Point at a *separate* database from your dev DB -- tests drop and recreate all tables.
DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/ai_tutor_test" uv run pytest
```

Tests never call OpenAI: the LLM and embeddings are replaced with LangChain test doubles (`FakeListChatModel`, a hand-rolled structured-output fake, `DeterministicFakeEmbedding`) via `monkeypatch`/`app.dependency_overrides`, and the ingestion background-task trigger is stubbed out so HTTP-level tests never touch the network or the app's own DB engine pool. See `backend/tests/conftest.py`.

If you see `RuntimeError: Event loop is closed` from asyncpg during a test run: some service (ingestion, study-plan outline building) opens its own session via the process-wide `src.db.engine`, whose connection pool doesn't survive pytest-asyncio's per-test event loop. The `_dispose_global_engine_pool` autouse fixture in `conftest.py` handles this already — if you add a new service that opens its own `AsyncSessionLocal()`, no extra work is needed, but if the error reappears, that fixture is where to look first.

### Scope classifier eval

```bash
uv run python -m src.scripts.eval_scope
```

Runs the real fast model against `backend/evals/scope_cases.yaml` (40 labelled cases) and prints per-category accuracy and a confusion matrix. Exits non-zero if any case confuses `unrelated` with `technology` in either direction — that's the one mistake the classifier must never make. Needs a real `OPENAI_API_KEY`; add cases to the YAML file as you find real-world misclassifications.

### Creating/promoting admins

```bash
uv run python -m src.scripts.create_admin --email you@example.com   # prompts for a password, or creates the account if it doesn't exist / promotes it if it does
uv run python -m src.scripts.promote_user --email x@example.com --role admin   # or --role learner to demote
```

## Frontend development (without Docker)

```bash
cd frontend
bun install
bun run dev
```

By default the Vite dev server proxies `/api` to `http://localhost:8000` (see `vite.config.js` — override with the `API_PROXY_TARGET` env var, which is how Docker Compose points it at `http://backend:80` instead).

```bash
bun run lint      # ESLint (JS/JSX, react-hooks + react-refresh rules)
bun run build     # production build
bun run preview   # preview the production build
```

## Database migrations

```bash
cd backend
uv run alembic revision --autogenerate -m "describe the change"
uv run alembic upgrade head
```

The `chunks` table is **not** auto-generated by `langchain_postgres` — it's a normal Alembic-managed table with real foreign keys (see `docs/ARCHITECTURE.md`), so autogenerate picks up changes to it like any other model. One thing autogenerate won't catch: the HNSW vector index (`CREATE INDEX ... USING hnsw (embedding vector_cosine_ops)`) needs to be added by hand in the migration (see the initial migration for the pattern) if you ever recreate the `chunks` table from scratch.

## Troubleshooting

### `SSL: CERTIFICATE_VERIFY_FAILED: self-signed certificate in certificate chain` calling OpenAI

Seen when the backend runs inside the Docker container and calls the OpenAI API — `example.com` and other plain HTTPS sites work fine, but `api.openai.com` specifically fails, even though the certificate itself is a normal, publicly-trusted one (issued by Google Trust Services).

Cause: the `openai` SDK's HTTP client verifies TLS via the `truststore` package (the OS-native certificate store) by default, and that lookup is unreliable in this container image for this specific host. `docker-compose.yaml` already works around it by pointing `SSL_CERT_FILE` at `certifi`'s bundle before starting the backend:
```bash
export SSL_CERT_FILE=$(uv run python -m certifi) && uv run uvicorn ...
```
If you run the backend outside Docker and hit the same error, set `SSL_CERT_FILE` the same way in your shell before starting uvicorn. This does **not** weaken certificate verification — it just points verification at a well-maintained CA bundle instead of a broken OS-store lookup.

### Ingestion fails with a `chunks_document_id_fkey` foreign-key violation

This was a real bug (fixed) where the pipeline only `flush()`ed the new `documents` row instead of `commit()`ing it before `PGVectorStore` wrote chunks referencing it through its own, separate database connection — an uncommitted row on one connection isn't visible to another. If you're extending the ingestion pipeline and see this again, the fix is the same: commit any row another connection needs to see, don't just flush it. See `backend/src/services/ingestion/pipeline.py`.

### A resource is stuck in `processing`

Usually means the backend restarted mid-ingestion (e.g. `--reload` picked up a file change). It self-heals on the next backend startup (`recover_interrupted_resources`), or you can just hit "Retry" in the admin UI / `POST /api/resources/{id}/reingest`.

### The backend container can't find its own virtualenv / behaves like a fresh install

The `backend` service bind-mounts your local `backend/` directory over `/app` for live reload, which would otherwise shadow the image's `/app/.venv` with your host's (likely nonexistent, or wrong-OS) one. `docker-compose.yaml` adds an anonymous volume at `/app/.venv` specifically to prevent this — don't remove it. If you do end up with a broken venv, `docker compose up -d --build -V backend` recreates that volume from the image.

### Changing the embedding model

Embeddings from different models (or even different dimensions of the same family) aren't comparable, so switching `OPENAI_EMBEDDING_MODEL` means:
1. Update `EMBEDDING_DIM` in `.env` to match.
2. Write and run an Alembic migration to `ALTER COLUMN embedding TYPE vector(<new_dim>)` on `chunks` (and recreate the HNSW index, which is dimension-specific).
3. Re-run ingestion for every resource (`POST /api/resources/{id}/reingest`) — `documents.content` still has the cleaned markdown, so this re-chunks and re-embeds without re-scraping anything.
