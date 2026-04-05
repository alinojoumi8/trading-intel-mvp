# Trading Intelligence Platform — QWEN Context

## Project Overview

A full-stack **AI-powered trading intelligence platform** that generates and publishes AI-driven market briefings, trade setups, macro analysis, and news aggregation for active retail traders. The platform uses LLM (MiniMax) to analyze market data from multiple external APIs and produce structured trading content.

**Brand name in deployment docs:** signaLayer.ai

### Architecture

- **Backend:** FastAPI (Python 3.10+) — REST API with SQLAlchemy ORM
- **Frontend:** Next.js 16 App Router (React 19, TypeScript) with Tailwind CSS 4
- **Database:** SQLite (dev) / PostgreSQL (production)
- **External APIs:** Alpha Vantage (market data), MiniMax LLM (AI generation), Finnhub, NewsAPI, FRED, CFTC Socrata (COT data), RSS feeds (130+ news sources)
- **Deployment:** Railway (backend) + Vercel (frontend) + Cloudflare DNS

### Content Types

| Type | Description | Frequency |
|------|-------------|-----------|
| Morning Briefing | Market mover summary, key levels, risk-on/risk-off bias | Daily (06:00 UTC) |
| Trade Setup | Entry zone, SL, TP, R:R, confidence, rationale | 2-5x daily |
| Macro Roundup | Top macro events, COT analysis, week ahead | Weekly (Friday) |
| Contrarian Alert | Extreme crowd positioning signals | Ad-hoc |
| Signals | Multi-stage AI trading signals (6-stage pipeline) | Ongoing |
| News Aggregation | 130+ RSS feeds across 10 categories | Every 30 min |

---

## Building and Running

### Quick Start

```bash
./run.sh start    # Start backend (port 8000) + frontend (port 3000)
./run.sh stop     # Stop both servers
./run.sh status   # Check running status
```

### Backend

```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Seed the database with instruments and sample content
python seed.py

# Run the API server
uvicorn app.main:app --reload --port 8000
```

API documentation available at `http://localhost:8000/docs` (Swagger UI) and `http://localhost:8000/redoc` (ReDoc).

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Run the development server
npm run dev
```

Frontend runs on `http://localhost:3000`.

### Manual Content Generation (Backend CLI)

```bash
cd backend

# Generate morning briefing
python admin_cli.py generate briefing
python admin_cli.py generate briefing EURUSD

# Generate trade setup
python admin_cli.py generate setup EURUSD

# Generate macro roundup
python admin_cli.py generate roundup

# Generate contrarian alert
python admin_cli.py generate contrarian EURUSD

# Run full daily pipeline
python admin_cli.py generate full

# List content / instruments / status
python admin_cli.py list content --type setup --limit 10
python admin_cli.py list instruments
python admin_cli.py status
```

### Cron Scheduler

```bash
cd backend
python cron_scheduler.py
```

Scheduling is **disabled by default**. To enable, uncomment lines in `cron_scheduler.py`:
- `schedule_morning_briefing(hour=6, minute=0)` — daily 06:00 UTC
- `schedule_weekly_roundup(day="Friday", hour=17, minute=0)` — weekly Friday 17:00 UTC

### Tests

**No test suite currently exists.** If adding tests:
- Backend: use `pytest`
- Frontend: use Jest + React Testing Library

---

## Project Structure

```
trading-intel-mvp/
├── backend/
│   ├── app/
│   │   ├── core/              # Config (config.py), database (database.py)
│   │   ├── models/            # SQLAlchemy models (models.py)
│   │   ├── routers/           # API endpoints (17 routers)
│   │   ├── schemas/           # Pydantic schemas
│   │   ├── services/          # Business logic
│   │   │   ├── content_pipeline.py      # LLM content generation orchestration
│   │   │   ├── data_aggregator.py       # Data aggregation for generation
│   │   │   ├── llm_service.py           # MiniMax API integration
│   │   │   ├── alpha_vantage_service.py # Market data
│   │   │   ├── cot_service.py           # CFTC positioning data
│   │   │   ├── rss_news_service.py      # RSS news aggregation
│   │   │   ├── signals_*.py             # Multi-stage AI signal pipeline
│   │   │   └── ...
│   │   └── main.py            # FastAPI app entry point
│   ├── admin_cli.py           # CLI for manual content generation
│   ├── cron_scheduler.py      # Scheduled pipeline runner
│   ├── seed.py                # Database seeding (instruments + feeds)
│   └── requirements.txt       # Python dependencies
├── frontend/
│   ├── app/                   # Next.js App Router pages (17+ routes)
│   ├── components/            # React components
│   ├── lib/                   # API client (api.ts) — ALL backend API calls
│   └── package.json
├── run.sh                     # Start/stop script for both servers
├── Procfile                   # Heroku/Railway process definition
├── railway.json               # Railway deployment config
├── SPEC.md                    # RSS News Aggregation spec
├── AI_Trading_System_Spec_V3_Full.md  # Full AI trading system spec (1155 lines)
└── DEPLOY.md                  # Production deployment guide (Vercel + Railway)
```

---

## Key Backend Patterns

- **App structure:** FastAPI app defined in `app/main.py`. All routers imported and registered there with CORS allowing all origins.
- **Database:** Auto-creates tables on startup via `Base.metadata.create_all(bind=engine)`.
- **Async services:** Services use `async/await` with `asyncio.to_thread()` for synchronous HTTP calls.
- **Content pipeline:** `content_pipeline.py` → `data_aggregator.py` → `llm_service.py` (MiniMax API).
- **COT data:** Fetched from CFTC Socrata API (`cot_service.py`), smart sync (bulk on first run, incremental after).
- **External APIs:** Alpha Vantage (market data), MiniMax (LLM), Finnhub, NewsAPI, FRED — all optional except Alpha Vantage + MiniMax.
- **Admin API protection:** `/admin/generate/*` endpoints require `X-Admin-Key` header matching `ADMIN_API_KEY` env var.

### Backend Routers (17 total)

| Router | Purpose |
|--------|---------|
| `content.py` | Content browsing & filtering |
| `instruments.py` | Instrument reference data |
| `tags.py` | Reusable content tags |
| `pipeline.py` | AI content generation triggers |
| `news.py` | RSS news items & sources CRUD |
| `news_analysis.py` | News analysis endpoints |
| `signals.py` | AI trading signals |
| `trade_outcomes.py` | Trade outcome tracking |
| `cot_history.py` | CFTC positioning history |
| `regime.py` | Market regime data |
| `multi_timeframe.py` | Multi-timeframe analysis |
| `alerts.py` | Trading alerts |
| `correlation.py` | Asset correlation data |
| `economic_calendar.py` | Economic calendar events |
| `auth.py` | Authentication (JWT) |
| `billing.py` | Stripe billing/subscriptions |

### Key Backend Services

| Service | Purpose |
|---------|---------|
| `content_pipeline.py` | Orchestrates LLM content generation |
| `data_aggregator.py` | Aggregates market data for generation |
| `llm_service.py` | MiniMax LLM API integration |
| `alpha_vantage_service.py` | Alpha Vantage market data |
| `cot_service.py` | CFTC COT data from Socrata |
| `rss_news_service.py` | RSS feed fetching & storage |
| `signals_stages.py` | 6-stage AI signal pipeline |
| `signals_technicals.py` | Technical analysis for signals |
| `signals_data_fetcher.py` | Data fetching for signals |
| `signals_service.py` | Signal service orchestration |
| `news_service.py` | News management |
| `finnhub_service.py` | Finnhub API integration |
| `fredapi` | FRED economic data |
| `kraken_service.py` | Kraken crypto data |
| `crypto_service.py` | Crypto data aggregation |
| `alert_service.py` | Alert management |
| `regime.py` | Market regime classification |

---

## Key Frontend Patterns

- **Next.js 16** with App Router. All pages use `"use client"` pattern (client components).
- **API client:** `lib/api.ts` contains ALL backend API calls and type definitions. Backend sends `content_type`/`instrument_symbol`; frontend normalizes to `type`/`instrument` via `normalizeContentItem()`.
- **Navigation:** Sidebar in `components/Sidebar.tsx` — icon keys must match the `icons` record.
- **Page pattern:** `app/<route>/page.tsx` (metadata + dynamic import) → `app/<route>/<Name>PageContent.tsx` (client component with state).
- **Charts:** Use Recharts library.
- **Auth:** NextAuth 5 (Credentials provider, JWT strategy), route handler at `app/api/auth/[...nextauth]/route.ts`.

### Frontend Routes (17+)

| Route | Purpose |
|-------|---------|
| `/` | Landing page / public content feed |
| `/instrument/[symbol]` | Instrument-specific pages |
| `/briefing` | Morning briefings |
| `/alerts` | Trading alerts |
| `/news` | RSS news aggregation (130+ feeds) |
| `/signals` | AI trading signals |
| `/regime` | Market regime dashboard |
| `/multi-timeframe` | Multi-timeframe analysis |
| `/correlation` | Asset correlation |
| `/economic-calendar` | Economic calendar |
| `/cot` | CFTC positioning history |
| `/leaderboard` | Trade performance leaderboard |
| `/performance` | System performance metrics |
| `/pricing` | Subscription pricing page |
| `/sitemap.xml` | SEO sitemap |
| `/landing` | Landing page content |
| `/auth` | Authentication pages |

### Next.js 16 Warning

> This Next.js version has breaking changes from training data. Read `node_modules/next/dist/docs/` before writing Next.js code. The `middleware.ts` convention is deprecated in favor of `proxy`. See `frontend/AGENTS.md` and `frontend/CLAUDE.md` for agent-specific guidance.

---

## Environment Variables

### Backend (`.env` in `backend/`)

| Variable | Purpose | Required? |
|----------|---------|-----------|
| `DATABASE_URL` | Database connection (SQLite dev / PostgreSQL prod) | Yes |
| `JWT_SECRET` | JWT signing secret | Yes |
| `ADMIN_API_KEY` | Admin API key for content generation | Yes |
| `ALPHA_VANTAGE_API_KEY` | Forex/equity market data | Yes |
| `MINIMAX_API_KEY` | AI content generation | Yes |
| `MINIMAX_MODEL` | LLM model (default: MiniMax-Text-01) | Yes |
| `STRIPE_SECRET_KEY` | Stripe payments | Prod only |
| `STRIPE_PRICE_ID` | Subscription price ID | Prod only |
| `STRIPE_WEBHOOK_SECRET` | Webhook verification | Prod only |
| `FRONTEND_URL` | CORS origin | Yes |
| `CORS_ORIGINS` | Comma-separated CORS origins | Yes |
| `FINNHUB_API_KEY` | News & sentiment | Optional |
| `NEWSAPI_KEY` | Macro news | Optional |
| `FRED_API_KEY` | Economic data | Optional |
| `ENVIRONMENT` | `development` or `production` | Yes |
| `DEBUG` | Debug mode | Yes |

### Frontend (`.env.local` in `frontend/`)

| Variable | Purpose |
|----------|---------|
| `NEXTAUTH_SECRET` | NextAuth JWT secret |
| `AUTH_SECRET` | Auth secret (NextAuth 5) |
| `NEXTAUTH_URL` | Auth URL |
| `NEXT_PUBLIC_API_URL` | Backend API URL |
| `NEXT_PUBLIC_BASE_URL` | Frontend base URL |

---

## Development Conventions

- **Backend:** Python with FastAPI, Pydantic schemas for validation, SQLAlchemy for ORM. Services are async-first with `asyncio.to_thread()` for sync operations.
- **Frontend:** TypeScript, React 19, Next.js 16 App Router, Tailwind CSS 4, Recharts for visualization. All pages are client components.
- **API style:** Backend sends `content_type`/`instrument_symbol`; frontend normalizes to `type`/`instrument`.
- **Code organization:** Routers in `app/routers/`, services in `app/services/`, models in `app/models/`, config in `app/core/`.
- **No tests:** No test suite exists. Add pytest (backend) or Jest + RTL (frontend) when adding features.
- **Database:** Auto-creates tables on startup. Seed data via `seed.py`.

---

## Deployment

### Backend (Railway)
- Deploy via `railway up` or GitHub auto-deploy
- PostgreSQL database via Railway addon
- Start command: `web: cd backend && . venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- `railway.json` in project root configures Nixpacks build

### Frontend (Vercel)
- Deploy via `vercel deploy` or GitHub auto-deploy
- Environment variables: `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_APP_URL`

### Production Architecture
```
Browser → Vercel (Next.js) → Railway (FastAPI) → PostgreSQL + External APIs
                ↓
         Cloudflare DNS
         (signaLayer.ai → Vercel)
         (api.signaLayer.ai → Railway)
```

See `DEPLOY.md` for full deployment checklist.

---

## Key Files Reference

| File | Purpose |
|------|---------|
| `backend/app/main.py` | FastAPI app entry, registers all routers, CORS, health checks |
| `backend/app/core/config.py` | Settings management (pydantic-settings) |
| `backend/app/core/database.py` | SQLAlchemy engine & session |
| `backend/app/models/models.py` | All SQLAlchemy models |
| `backend/seed.py` | Database seeding (instruments, RSS feeds, sample content) |
| `backend/admin_cli.py` | CLI for manual content generation |
| `backend/cron_scheduler.py` | Scheduled pipeline (uses threading.Timer) |
| `frontend/lib/api.ts` | ALL frontend API calls + type definitions |
| `frontend/components/Sidebar.tsx` | Main navigation component |
| `run.sh` | Start/stop script for local development |
| `Procfile` | Process definition for Heroku/Railway |
| `rss.txt` | 130+ RSS feed URLs (seeded into NewsSource table) |

---

## AI Trading Signal Pipeline (6-Stage)

The platform implements a sophisticated 6-stage AI trading signal pipeline (detailed in `AI_Trading_System_Spec_V3_Full.md`):

1. **Stage 0 — Asset Pre-Screen:** Confirms asset is tradeable (floating regime, meaningful volatility)
2. **Stage 1 — Market Regime Classifier:** Bull/Bear + VIX + Volatility Mode classification
3. **Stage 2 — Growth/Inflation Grid:** 4-Quadrant framework (Expansion/Reflation/Disinflation/Stagflation)
4. **Stage 3 — Asset-Class Deep Dive:** 3-Step Analysis (Baseline → Surprise → Bigger Picture)
5. **Stage 4 — Gatekeeping:** COT positioning + IV ranges + 14-Point Technical Traffic Light
6. **Stage 5 — Final Signal Aggregator:** Combines all stages into trade plan output

Each stage = a separate LLM call, output chaining as JSON into the next stage.

---

## RSS News Aggregation

The platform aggregates 130+ RSS feeds across 10 categories (Forex, Crypto, General, etc.). News is fetched every 30 minutes via the cron scheduler, stored in the database, and made available both to human users via the `/news` frontend page and to the AI content generation pipeline.

Key implementation details in `SPEC.md`.
