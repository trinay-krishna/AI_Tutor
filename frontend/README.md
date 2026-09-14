# AI Tutor — Frontend

React 19 + Vite, plain JSX (no TypeScript), managed with [`bun`](https://bun.sh).

See the repo root for full docs: [Architecture](../docs/ARCHITECTURE.md) · [API reference](../docs/API.md) · [Development guide](../docs/DEVELOPMENT.md).

## Layout

```
src/
  api.js           fetch wrapper (same-origin via the Vite dev proxy, credentials included)
  main.jsx, App.jsx  entry point, router + layout
  auth/            session context, RequireAuth / RequireAdmin route guards
  pages/           Technologies, Chat, Login, Register, admin/*
  components/      MessageBubble, SourceList, NavBar
```

## Commands

```bash
bun install
bun run dev       # dev server; proxies /api to API_PROXY_TARGET (default http://localhost:8000)
bun run lint
bun run build
bun run preview
```

Normally you'd run this via Docker Compose from the repo root instead — see the [quick start](../README.md#quick-start). After adding a dependency, refresh the container's `node_modules` volume: `docker compose up -d --build -V frontend`.
