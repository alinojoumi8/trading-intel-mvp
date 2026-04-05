# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Start

```bash
./run.sh start    # Start backend (port 8000) + frontend (port 3000)
./run.sh stop     # Stop both
./run.sh status   # Check status
```

Manual start (separate terminals):
```bash
# Backend
cd backend && source venv/bin/activate && uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend && npm run dev -- --port 3000
```

Seed database: `cd backend && python seed.py`

Generate content via CLI: `cd backend && python admin_cli.py generate briefing`

## Architecture

Full-stack trading intelligence platform: FastAPI backend + Next.js 16 frontend + SQLite (dev) / PostgreSQL (prod).

**Backend** (`backend/`): FastAPI app defined in `app/main.py`. Routers in `app/routers/`, services in `app/services/`, models in `app/models/models.py`, config in `app/core/config.py`.

**Frontend** (`frontend/`): Next.js 16 App Router. All pages are client components using `"use client"` pattern. API client in `lib/api.ts` normalizes backend responses. Auth via NextAuth 5 (Credentials provider, JWT strategy) with route handler at `app/api/auth/[...nextauth]/route.ts`.

**Data flow**: Frontend `lib/api.ts` → FastAPI routers → services (fetch external APIs / query DB) → SQLAlchemy models → SQLite/PostgreSQL.

## Key Backend Patterns

- All routers registered in `app/main.py` with CORS allowing all origins
- Database auto-creates tables on startup via `Base.metadata.create_all()`
- Services use async/await with `asyncio.to_thread()` for sync HTTP calls
- Content generation pipeline: `content_pipeline.py` → `data_aggregator.py` → `llm_service.py` (MiniMax API)
- COT data: fetched from CFTC Socrata API (`cot_service.py`), smart sync (bulk on first run, incremental after)
- External APIs: Alpha Vantage (market data), MiniMax (LLM), Finnhub, NewsAPI, FRED (all optional except Alpha Vantage + MiniMax)

## Key Frontend Patterns

- `lib/api.ts` contains ALL backend API calls and type definitions. Backend sends `content_type`/`instrument_symbol`; frontend normalizes to `type`/`instrument` via `normalizeContentItem()`
- Sidebar navigation defined in `components/Sidebar.tsx` — icon keys must match the `icons` record
- Pages follow pattern: `app/<route>/page.tsx` (metadata + dynamic import) → `app/<route>/<Name>PageContent.tsx` (client component with state)
- Charts use Recharts library

## Frontend: Next.js 16 Warning

@frontend/AGENTS.md — This Next.js version has breaking changes from training data. Read `node_modules/next/dist/docs/` before writing Next.js code. The `middleware.ts` convention is deprecated in favor of `proxy`.

## Environment Variables

Backend (`.env` in `backend/`): `DATABASE_URL`, `ALPHA_VANTAGE_API_KEY`, `MINIMAX_API_KEY`, `MINIMAX_MODEL`, `JWT_SECRET`, `STRIPE_SECRET_KEY`, `ENVIRONMENT`, `DEBUG`

Frontend (`.env.local` in `frontend/`): `NEXTAUTH_SECRET`, `AUTH_SECRET`, `NEXTAUTH_URL`, `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_BASE_URL`

## No Test Suite

There are currently no tests. Backend would use pytest; frontend would use Jest + React Testing Library.
