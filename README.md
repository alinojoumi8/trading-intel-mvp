# Trading Intelligence Platform

AI-powered trading intelligence platform that publishes AI-generated briefings, trade setups, and macro analysis for active retail traders.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Frontend (Next.js)                          │
│                                                                      │
│   /                      Public content feed with filters           │
│   /instrument/[symbol]    Instrument-specific pages                │
│   /sitemap.xml             SEO sitemap                              │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ REST API (:3000)
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       Backend (FastAPI)                              │
│                                                                      │
│   /content         Content browsing & filtering                       │
│   /instruments     Instrument reference data                         │
│   /admin/generate  AI content generation triggers                     │
│   /health          Health checks                                     │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ SQLAlchemy
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Database (SQLite/PostgreSQL)                    │
│                                                                      │
│   content_items   Published briefings, setups, alerts                 │
│   instruments     Trading instruments (EURUSD, XAUUSD, BTC, etc.)    │
│   tags            Reusable content tags                              │
└─────────────────────────────────────────────────────────────────────┘
                                │
                    ┌───────────┴───────────┐
                    ▼                       ▼
           ┌──────────────┐       ┌──────────────────┐
           │   Alpha Vantage │       │  MiniMax LLM     │
           │  (market data)  │       │  (AI generation) │
           └──────────────┘       └──────────────────┘
```

## Prerequisites

- Python 3.10+
- Node.js 18+
- npm or yarn

## Local Setup

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

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Run the development server
npm run dev
```

The frontend runs on `http://localhost:3000` and the backend API on `http://localhost:8000`.

## API Documentation

Once the backend is running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Environment Variables

Create a `.env` file in the `backend/` directory:

```env
# Database
DATABASE_URL=sqlite:///./trading_intel.db

# Auth
JWT_SECRET=replace_with_a_long_random_secret

# Alpha Vantage (forex/equity data)
ALPHA_VANTAGE_API_KEY=your_key_here

# MiniMax LLM (AI content generation)
MINIMAX_API_KEY=your_key_here
MINIMAX_MODEL=MiniMax-Text-01

# Billing
STRIPE_SECRET_KEY=your_key_here
STRIPE_PRICE_ID=price_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx

# Frontend/backend integration
FRONTEND_URL=http://localhost:3000
CORS_ORIGINS=http://localhost:3000

# Admin API protection
ADMIN_API_KEY=replace_with_a_second_random_secret

# Optional: Finnhub (news, sentiment)
FINNHUB_API_KEY=your_key_here

# Optional: NewsAPI (macro news)
NEWSAPI_KEY=your_key_here

# Environment
ENVIRONMENT=development
DEBUG=true
```

If you use the `/admin/generate/*` HTTP endpoints, send the configured admin key as an `X-Admin-Key` header.

## Manual Content Generation

Use the admin CLI to manually trigger content generation:

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

# List content
python admin_cli.py list content --type setup --limit 10

# List instruments
python admin_cli.py list instruments

# System status
python admin_cli.py status
```

## Cron Scheduling

The `cron_scheduler.py` script provides scheduling using Python's built-in `threading.Timer`:

```bash
cd backend
python cron_scheduler.py
```

By default, scheduling is commented out. To enable:
- Uncomment `schedule_morning_briefing(hour=6, minute=0)` for daily 06:00 UTC briefings
- Uncomment `schedule_weekly_roundup(day="Friday", hour=17, minute=0)` for weekly Friday roundups

## Deployment

### Backend Deployment Options
- **Railway**: `railway up`
- **Render**: Connect GitHub repo with Render
- **VPS**: `uvicorn app.main:app --host 0.0.0.0 --port 8000`

### Frontend Deployment Options
- **Vercel**: `vercel deploy`
- **Netlify**: Connect GitHub repo

### Database
- Development: SQLite (default)
- Production: PostgreSQL (set `DATABASE_URL` environment variable)

## Content Types

| Type | Description | Frequency |
|------|-------------|-----------|
| Morning Briefing | Market mover summary, key levels, risk-on/risk-off bias | Daily (06:00 UTC) |
| Trade Setup | Entry zone, SL, TP, R:R, confidence, rationale | 2-5x daily |
| Macro Roundup | Top macro events, COT analysis, week ahead | Weekly (Friday) |
| Contrarian Alert | Extreme crowd positioning signals | Ad-hoc |

## Project Structure

```
trading-intel-mvp/
├── backend/
│   ├── app/
│   │   ├── core/          # Config, database
│   │   ├── models/         # SQLAlchemy models
│   │   ├── routers/        # API endpoints
│   │   ├── schemas/        # Pydantic schemas
│   │   └── services/       # Business logic (data aggregator, content generators)
│   ├── admin_cli.py        # CLI for manual content generation
│   ├── cron_scheduler.py   # Scheduled pipeline runner
│   ├── seed.py             # Database seeding
│   └── requirements.txt
├── frontend/
│   ├── app/                # Next.js app router pages
│   ├── components/         # React components
│   └── lib/                # API client
├── SPEC.md                 # Project specification
└── README.md
```
