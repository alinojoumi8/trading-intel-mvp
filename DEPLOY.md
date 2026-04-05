# signaLayer.ai Production Deployment Guide

This guide covers deploying signaLayer.ai to production using Vercel (frontend) and Railway (backend) with PostgreSQL.

---

## Architecture Overview

```
Browser → Vercel (Next.js) → Railway (FastAPI) → PostgreSQL + External APIs
                ↓
         Cloudflare DNS
         (signaLayer.ai → Vercel)
         (api.signaLayer.ai → Railway)
```

---

## 1. GitHub Repository Setup

Create two repositories under your GitHub account (`alinojoumi8`):

1. **signalaLayer-frontend** — Next.js application
2. **signalaLayer-backend** — FastAPI application

Push your code:
```bash
# Frontend
cd frontend
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/alinojoumi8/signalaLayer-frontend.git
git push -u origin main

# Backend
cd backend
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/alinojoumi8/signalaLayer-backend.git
git push -u origin main
```

---

## 2. Railway Backend Deployment

### 2.1 Create Railway Project

1. Go to [railway.app](https://railway.app) and sign in with GitHub
2. Click **New Project** → **Deploy from GitHub repo**
3. Select `signalaLayer-backend`
4. Railway will auto-detect Python/Nixpacks

### 2.2 Add PostgreSQL Database

1. In your Railway project, click **New** → **Database** → **Add PostgreSQL**
2. Wait for provisioning to complete
3. Copy the **Connection URL** (will look like `postgresql://user:password@host:5432/trading_intel`)

### 2.3 Configure Environment Variables

In Railway project settings, add all variables from `backend/.env.production`:

| Variable | Description | Where to Get |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | Railway PostgreSQL plugin |
| `STRIPE_SECRET_KEY` | Stripe secret key | Stripe Dashboard → Developers → API keys |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signing secret | Stripe Dashboard → Webhooks |
| `STRIPE_PRICE_ID` | Stripe price ID for subscriptions | Stripe Dashboard → Products |
| `ALPHA_VANTAGE_API_KEY` | Alpha Vantage API key | alphavantage.co |
| `MINIMAX_API_KEY` | MiniMax API key | Minimax dashboard |
| `FRED_API_KEY` | FRED API key | St. Louis Fed |
| `JWT_SECRET` | 64-char random secret | Generate with `openssl rand -hex 32` |
| `ENVIRONMENT` | Set to `production` | - |
| `DEBUG` | Set to `false` | - |

### 2.4 Set Start Command

In Railway deployment settings, set the start command:
```
web: cd backend && . venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Or use the `Procfile` in the root of the project (Railway auto-detects it).

### 2.5 Railway JSON Configuration

The `railway.json` file in the project root configures the deployment:

```json
{
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "numReplicas": 1,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

### 2.6 Get Backend URL

After deployment, your backend URL will be something like:
```
https://signalaLayer-backend.up.railway.app
```

Note this — you'll need it for the frontend and DNS configuration.

---

## 3. Vercel Frontend Deployment

### 3.1 Create Vercel Project

1. Go to [vercel.com](https://vercel.com) and sign in with GitHub
2. Click **Add New** → **Project**
3. Import `signalaLayer-frontend`
4. Vercel auto-detects Next.js

### 3.2 Configure Environment Variables

In Vercel project settings, add:

| Variable | Value |
|---|---|
| `NEXT_PUBLIC_API_URL` | `https://api.signaLayer.ai` |
| `NEXT_PUBLIC_APP_URL` | `https://signaLayer.ai` |

**Important:** These must be set before first deployment. Set them under **Environment Variables**.

### 3.3 Framework Preset

Vercel auto-detects Next.js. No custom build command needed.

### 3.4 Root Directory

Set root directory to `./` (the monorepo root), with `frontend` as the project directory.

### 3.5 Build Command

```
cd frontend && npm install && npm run build
```

### 3.6 Output Directory

Leave as default (`/.next`).

---

## 4. Domain Configuration (Cloudflare)

### 4.1 Register Domain

Register `signaLayer.ai` through Cloudflare or any registrar.

### 4.2 Add Domain to Cloudflare

1. Log in to Cloudflare dashboard
2. Go to **Websites** → **Add a site**
3. Enter `signaLayer.ai`
4. Choose a plan (Free tier is sufficient)
5. Update nameservers at your registrar to Cloudflare's nameservers

### 4.3 Configure DNS Records

In Cloudflare DNS settings for `signaLayer.ai`:

#### Frontend (Vercel)
| Type | Name | Content | Proxy |
|---|---|---|---|
| CNAME | `@` | `cname.vercel-dns.com` | Proxied (orange) |
| CNAME | `www` | `cname.vercel-dns.com` | Proxied (orange) |

#### Backend API (Railway)
| Type | Name | Content | Proxy |
|---|---|---|---|
| CNAME | `api` | `signalaLayer-backend.up.railway.app` | DNS only (grey) |

> **Note:** Railway uses dynamic IPs, so we use a CNAME to the Railway-provided hostname. Railway may also provide a static IP — check Railway dashboard.

#### Alternative: A Record for Railway
If Railway provides a static IP for your project:
| Type | Name | IPv4 | Proxy |
|---|---|---|---|
| A | `api` | `<railway-static-ip>` | DNS only (grey) |

### 4.4 SSL/TLS Settings

In Cloudflare **SSL/TLS** settings:
- Set mode to **Full** (or **Full Strict**)
- This encrypts traffic between Cloudflare and both Vercel and Railway

### 4.5 Cloudflare Pages (Optional)

If you want Cloudflare as CDN in front of Vercel:
1. Create a Cloudflare Pages project
2. Connect to your Vercel deployment
3. Use Cloudflare's CNAME targeting

---

## 5. SQLite → PostgreSQL Migration

If you have existing SQLite data:

### 5.1 Dump SQLite Data

```bash
cd backend
sqlite3 trading_intel.db ".dump" > dump.sql
```

### 5.2 Convert to PostgreSQL

The main differences in the dump:
- Remove `BEGIN TRANSACTION` and `COMMIT`
- Replace `sqlite_autoindex` with serial columns
- Remove `INTEGER PRIMARY KEY` → use `SERIAL PRIMARY KEY`
- `DATETIME` → `TIMESTAMP`
- `BOOLEAN` values (`0`/`1`) → `TRUE`/`FALSE`

### 5.3 Import to PostgreSQL

```bash
# Via psql
psql $DATABASE_URL -f dump.sql

# Or via pg_dump
pg_restore -d $DATABASE_URL dump.sql
```

### 5.4 Update Database URL

Make sure your `DATABASE_URL` in Railway points to PostgreSQL (not SQLite):
```
DATABASE_URL=postgresql://user:password@host:5432/trading_intel
```

### 5.5 Verify Migration

```bash
curl https://api.signaLayer.ai/api/health/live
```

Should return `{"status": "ok"}`.

---

## 6. Stripe Configuration

### 6.1 Get API Keys

1. Go to [dashboard.stripe.com](https://dashboard.stripe.com)
2. Navigate to **Developers** → **API keys**
3. Copy your **Secret key** (`sk_live_...`)
4. Never expose the secret key in frontend code

### 6.2 Configure Webhooks

1. Go to **Developers** → **Webhooks**
2. Click **Add endpoint**
3. Endpoint URL: `https://api.signaLayer.ai/api/webhooks/stripe`
4. Select events:
   - `checkout.session.completed`
   - `customer.subscription.deleted`
   - `invoice.payment_failed`
5. Copy the **Webhook Secret** (`whsec_...`)

### 6.3 Create a Product/Price

1. Go to **Products** → **Add product**
2. Set name, description, price
3. Copy the **Price ID** (`price_...`)

---

## 7. Environment Variables Reference

### Backend (Railway)

```
DATABASE_URL=postgresql://user:password@host:5432/trading_intel
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_ID=price_...
ALPHA_VANTAGE_API_KEY=...
MINIMAX_API_KEY=...
FRED_API_KEY=...
JWT_SECRET=generate_random_64_char_string
ENVIRONMENT=production
DEBUG=false
```

### Frontend (Vercel)

```
NEXT_PUBLIC_API_URL=https://api.signaLayer.ai
NEXT_PUBLIC_APP_URL=https://signaLayer.ai
```

---

## 8. Post-Deployment Checklist

- [ ] Verify `https://signaLayer.ai` loads correctly
- [ ] Verify `https://api.signaLayer.ai/api/health/live` returns `{"status": "ok"}`
- [ ] Test user registration/login flow
- [ ] Verify Stripe checkout works
- [ ] Check Cloudflare SSL certificate is active
- [ ] Monitor Railway logs for any errors
- [ ] Set up Railway automatic deployments from `main` branch

---

## 9. Monitoring & Logs

### Railway Logs
- Go to Railway project → **Deployments** → **Logs**
- Or use Railway CLI: `railway logs`

### Vercel Logs
- Go to Vercel dashboard → **Functions** → **Logs**
- Or use Vercel CLI: `vercel logs`

### Health Check
```bash
curl https://api.signaLayer.ai/api/health/live
curl https://api.signaLayer.ai/api/health/ready
```

---

## 10. Troubleshooting

### Backend not starting
- Check `DEBUG=false` is set
- Verify `DATABASE_URL` is correct
- Check Railway logs for import errors

### CORS errors
- Ensure backend has `NEXT_PUBLIC_APP_URL` in CORS allowed origins
- Check that frontend is calling `NEXT_PUBLIC_API_URL`, not localhost

### Stripe webhooks not working
- Verify webhook URL is accessible
- Check Stripe webhook logs in Stripe Dashboard
- Ensure `STRIPE_WEBHOOK_SECRET` matches

### DNS not resolving
- Wait 24-48 hours for DNS propagation
- Check Cloudflare DNS records are correct
- Verify CNAME target is correct
