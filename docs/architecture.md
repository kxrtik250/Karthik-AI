# Karthik AI — Architecture

## Tech Stack

| Layer      | Technology                  |
|------------|-----------------------------|
| Frontend   | React 19 + Vite             |
| Backend    | Python 3.13 + FastAPI       |
| Database   | PostgreSQL 16 + pgvector    |
| Container  | Docker + Docker Compose     |

## Design Principles

1. **Modular** — Each feature is an independent service module.
2. **Clean separation** — Frontend and backend communicate only via REST API.
3. **Pluggable AI** — AI provider is behind an abstract interface (future phase).
4. **Docker-first data** — Database runs in Docker; no local DB install needed.
5. **Incremental** — Features are added in phases without breaking existing ones.

## Phase 1 — Foundation

- Project skeleton with clean folder structure
- FastAPI backend with health check endpoint
- React + Vite frontend shell
- PostgreSQL + pgvector running in Docker
- Environment variable templates
- No AI integration, no authentication, no business logic
