# AI Tutor

An AI tutor for learning software technologies. Admins onboard a technology (React, FastAPI, Docker, ...) with documentation URLs; the app ingests them into a technology-scoped knowledge base. Learners pick a technology and chat with a RAG-powered tutor that:

- answers from that technology's onboarded resources, with citations,
- falls back to general knowledge for other software/programming topics (clearly labelled as such),
- politely declines anything unrelated to software or learning, and
- can generate a study plan grounded in the onboarded resources on request.

## Stack

FastAPI (Python) + LangChain/LangGraph backend, React + Vite frontend, Postgres + pgvector for both relational data and the vector store, OpenAI for chat/embeddings. See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full design and rationale.

## Quick start

```bash
cp .env.example .env   # fill in OPENAI_API_KEY at minimum
docker compose up --build
docker compose exec backend uv run python -m src.scripts.create_admin --email you@example.com
```

Open http://localhost:5173, log in as the admin you just created, add a technology and some resource URLs, and start a chat once ingestion finishes (the resource list polls its own status).

## Documentation

- [**Architecture**](docs/ARCHITECTURE.md) — services, data model, ingestion pipeline, the LangGraph tutor graph, scope classification, study-plan generation, prompt-injection posture.
- [**API reference**](docs/API.md) — every endpoint, request/response shapes, auth rules.
- [**Development guide**](docs/DEVELOPMENT.md) — local setup (with and without Docker), environment variables, running tests and the scope-classifier eval, database migrations, and troubleshooting for issues we've actually hit (a TLS/certificate quirk calling OpenAI from Docker, an ingestion foreign-key bug, changing the embedding model).
- [`backend/README.md`](backend/README.md) / [`frontend/README.md`](frontend/README.md) — short per-service pointers.

## Project structure

```
backend/    FastAPI app (src/main.py) — routers, services, the LangGraph tutor graph, Alembic migrations, tests
frontend/   React + Vite app — pages, auth context, API client
docs/       Architecture, API reference, development guide
docker-compose.yaml   db (Postgres+pgvector) + backend + frontend
```
