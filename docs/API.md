# API Reference

All endpoints are under `/api`. The backend serves these directly on `:8000`; the frontend dev server proxies the same paths from `:5173` (see `frontend/vite.config.js`).

**Auth:** session-cookie based (`ai_tutor_session`, httpOnly). Send credentials with every request (`fetch(..., { credentials: "include" })`); there is no separate bearer-token flow. Endpoints marked **admin** require `role: admin`; everything else marked **user** just requires being logged in.

## Health

| Method & path | Auth | Description |
|---|---|---|
| `GET /api/health` | – | `{"status": "ok"\|"degraded", "db": bool}` |

## Auth

| Method & path | Auth | Body | Description |
|---|---|---|---|
| `POST /api/auth/register` | – | `{email, password}` (password ≥ 8 chars) | Creates a `learner` account, sets the session cookie. `409` if the email is taken. |
| `POST /api/auth/login` | – | `{email, password}` | Sets the session cookie. `401` on bad credentials. |
| `POST /api/auth/logout` | user | – | Clears just the current session (`204`). |
| `GET /api/auth/me` | user | – | Current user. `401` if not logged in. |

`UserOut`: `{id, email, role: "admin"|"learner", created_at}`.

Admins are never created via the API — use `uv run python -m src.scripts.create_admin --email you@example.com` (or `promote_user`) so account elevation always goes through someone with shell access.

## Technologies

| Method & path | Auth | Body | Description |
|---|---|---|---|
| `GET /api/technologies` | user | – | All technologies, each with `ready_resource_count`. |
| `POST /api/technologies` | admin | `{name, description?}` | Creates one; slug is derived from `name` (deduplicated with a `-2` suffix if needed). `409` on a duplicate name. |
| `GET /api/technologies/{id}` | user | – | One technology. `404` if missing. |
| `PATCH /api/technologies/{id}` | admin | `{name?, description?}` | Partial update; renaming re-derives the slug. |
| `DELETE /api/technologies/{id}` | admin | – | Cascades to its resources, documents, and chunks. |

`TechnologyOut`: `{id, name, slug, description, ready_resource_count, created_at}`.

## Resources (per technology)

| Method & path | Auth | Body | Description |
|---|---|---|---|
| `GET /api/technologies/{id}/resources` | admin | – | All resources for the technology, with ingestion status. |
| `POST /api/technologies/{id}/resources` | admin | `{urls: string[]}` (1–50, valid URLs) | Creates a `pending` row per new URL and kicks off background ingestion for each. URLs already onboarded (by normalized form) are reported back as skipped, not re-added. |
| `POST /api/resources/{id}/reingest` | admin | – | Resets the resource to `pending` and re-runs the pipeline (also the retry action for a `failed` resource). |
| `DELETE /api/resources/{id}` | admin | – | Removes the resource and its indexed chunks. |
| `POST /api/technologies/{id}/search` | admin | `{query, k?}` (k default 8, max 20) | Debug endpoint: runs retrieval directly and returns scored chunks. Used by the admin "Test retrieval" box, not by the learner chat. |

`ResourceOut`: `{id, technology_id, url, title, status: "pending"|"processing"|"ready"|"failed", error, chunk_count, last_ingested_at, created_at}`.

`ResourceBatchResult`: `{created: ResourceOut[], skipped: [{url, reason: "duplicate"}]}`.

`RetrievalHit`: `{chunk_id, resource_id, title, url, heading_path, content, score}` (`score` is cosine similarity in `[0, 1]`).

## Conversations & chat

| Method & path | Auth | Body | Description |
|---|---|---|---|
| `GET /api/conversations?technology_id=` | user | – | The caller's own conversations, newest first. `technology_id` filter is optional. |
| `POST /api/conversations` | user | `{technology_id}` | Starts a new, empty conversation. |
| `GET /api/conversations/{id}` | owner | – | Conversation plus its full message history. `404` for another user's conversation (never `403` — existence isn't revealed). |
| `POST /api/conversations/{id}/messages` | owner | `{content}` (1–4000 chars) | Runs the tutor graph. Returns `{user_message, assistant_message}`. `503` if the LLM/embedding call fails — the user's message is still saved, so nothing is lost. |
| `DELETE /api/conversations/{id}` | owner | – | Deletes the conversation and its messages. |

`ConversationOut`: `{id, technology_id, title, created_at, updated_at}`. `GET /{id}` additionally returns `messages: MessageOut[]`.

`MessageOut`:
```jsonc
{
  "id": "uuid",
  "role": "user" | "assistant",
  "content": "markdown text",
  "scope": "technology" | "related" | "unrelated" | null,   // null on user messages
  "intent": "question" | "study_plan" | null,
  "mode": "grounded" | "general" | "refusal" | null,
  "sources": [                                              // null when nothing was cited
    {
      "n": 1, "chunk_id": "uuid", "resource_id": 8,
      "url": "https://react.dev/...", "title": "...", "heading_path": "...",
      "score": 0.55, "cited": true                          // cited = the model actually used [n]
    }
  ],
  "created_at": "2026-01-01T00:00:00Z"
}
```

A study-plan response is a normal `MessageOut` with `intent: "study_plan"`; the rendered plan is in `content` as markdown, and the full structured plan (weeks, topics, `resource_refs`, `coverage_gaps`) is stored server-side in `messages.metadata.study_plan` (not currently exposed on `MessageOut` — read it via a DB query or extend the schema if the frontend needs the structured form directly).

## Error shape

Every error response is FastAPI's default `{"detail": "..."}` (a string for a single message, or a list of `{loc, msg, type}` objects for a Pydantic validation `422`).
