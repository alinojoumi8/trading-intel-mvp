# GitHub Setup Guide for signaLayer.ai

This guide walks through creating GitHub repositories and connecting them to Vercel and Railway for automatic deployments.

---

## Step 1: Create GitHub Repositories

### Option A: Via GitHub Web UI

1. Go to [github.com](https://github.com) and log in as `alinojoumi8`
2. Click **New repository**
3. Create two repos:
   - **Repository name:** `signalaLayer-frontend`
   - **Repository name:** `signalaLayer-backend`
4. Both should be **Public** (or Private if you prefer)
5. Don't initialize with README (we'll push existing code)

### Option B: Via GitHub CLI

```bash
# Create repos
gh repo create signalaLayer-frontend --public --clone
gh repo create signalaLayer-backend --public --clone
```

---

## Step 2: Push Code to Repos

### Frontend Repository

```bash
cd /home/ali/projects/trading-intel-mvp/frontend

# Initialize git (if not already initialized)
git init

# Add all files
git add .

# Initial commit
git commit -m "Initial commit: signaLayer.ai frontend"

# Add remote
git remote add origin https://github.com/alinojoumi8/signalaLayer-frontend.git

# Push to main branch
git branch -M main
git push -u origin main
```

### Backend Repository

```bash
cd /home/ali/projects/trading-intel-mvp/backend

# Initialize git
git init

# Add all files (exclude venv, __pycache__, .db files)
echo "venv/" >> .gitignore
echo "__pycache__/" >> .gitignore
echo "*.db" >> .gitignore
echo "*.pyc" >> .gitignore
echo ".env" >> .gitignore

# Add all files
git add .

# Initial commit
git commit -m "Initial commit: signaLayer.ai backend"

# Add remote
git remote add origin https://github.com/alinojoumi8/signalaLayer-backend.git

# Push to main branch
git branch -M main
git push -u origin main
```

---

## Step 3: Connect Frontend to Vercel

### 3.1 Create Vercel Project

1. Go to [vercel.com](https://vercel.com)
2. Click **Sign Up** and authenticate with GitHub
3. Click **Add New** → **Project**
4. Find and select `signalaLayer-frontend` from the list
5. Click **Import**

### 3.2 Configure Project

Set the following in Vercel's project configuration:

| Setting | Value |
|---|---|
| **Framework Preset** | Next.js (auto-detected) |
| **Root Directory** | `./frontend` |
| **Build Command** | `npm install && npm run build` |
| **Output Directory** | `.next` (default) |

### 3.3 Add Environment Variables

Before deploying, add these under **Environment Variables**:

| Name | Value |
|---|---|
| `NEXT_PUBLIC_API_URL` | `https://api.signaLayer.ai` |
| `NEXT_PUBLIC_APP_URL` | `https://signaLayer.ai` |

Set environment to **Production** (and optionally also Preview/Development).

### 3.4 Deploy

Click **Deploy**. Vercel will:
1. Clone the GitHub repo
2. Run `npm install`
3. Run `npm run build`
4. Deploy to Vercel's CDN

### 3.5 Get Frontend URL

After deployment, Vercel provides a URL like:
```
https://signalaLayer-frontend.vercel.app
```

Note this for DNS configuration.

---

## Step 4: Connect Backend to Railway

### 4.1 Create Railway Project

1. Go to [railway.app](https://railway.app)
2. Click **Sign Up** and authenticate with GitHub
3. Click **New Project** → **Deploy from GitHub repo**
4. Select `signalaLayer-backend`
5. Railway will auto-detect Python via Nixpacks

### 4.2 Add PostgreSQL Database

1. In your Railway project, click **New** → **Database** → **Add PostgreSQL**
2. Wait for provisioning (1-2 minutes)
3. Click on the PostgreSQL plugin to view connection details
4. Copy the **Connection URL** — you'll use this for `DATABASE_URL`

### 4.3 Add Environment Variables

In Railway project settings → **Variables**, add:

```bash
DATABASE_URL=postgresql://user:password@host:5432/trading_intel
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_ID=price_...
ALPHA_VANTAGE_API_KEY=your_key
MINIMAX_API_KEY=your_key
FRED_API_KEY=your_key
JWT_SECRET=your_64_char_random_secret
ENVIRONMENT=production
DEBUG=false
```

To generate a JWT secret:
```bash
openssl rand -hex 32
```

### 4.4 Configure Start Command

Railway auto-detects the `Procfile` in the project root. If needed, set the start command under **Settings** → **Start Command**:
```
web: cd backend && . venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### 4.5 Deploy

Click **Deploy**. Railway will:
1. Clone the GitHub repo
2. Build with Nixpacks (installs Python, dependencies)
3. Start the uvicorn server

### 4.6 Get Backend URL

After deployment, your backend is available at:
```
https://signalaLayer-backend.up.railway.app
```

You can add a custom domain or use this Railway-provided URL.

---

## Step 5: Set Up Automatic Deployments

### Vercel (Frontend)

Automatic deployments are enabled by default when you connect a GitHub repo.

- On every push to `main`, Vercel auto-deploys
- Pull requests create preview deployments
- To disable: Project Settings → **Git** → **Ignores**

### Railway (Backend)

1. In Railway project settings, go to **Settings** → **Git**
2. Ensure your GitHub repo is connected
3. Enable **Automatic Deployments**
4. Set branch to `main`

Now every push to `main` on either repo triggers an automatic deployment.

---

## Step 6: Verify Deployments

### Test Backend Health
```bash
curl https://signalaLayer-backend.up.railway.app/api/health/live
```

### Test Frontend
Open the Vercel-provided URL in your browser.

### Monitor Deployments
- **Vercel**: Dashboard → Project → Deployments
- **Railway**: Dashboard → Project → Deployments → Logs

---

## Repository Structure Summary

```
GitHub (alinojoumi8)
├── signalaLayer-frontend    → Vercel
│   └── frontend/
│       ├── app/
│       ├── lib/api.ts
│       ├── components/
│       └── .env.production.local
│
└── signalaLayer-backend     → Railway
    └── backend/
        ├── app/
        ├── services/
        └── .env.production
```

---

## Troubleshooting

### "Repository not found" when connecting to Vercel/Railway
- Ensure the GitHub account `alinojoumi8` owns the repos
- Check the repo is public, or that you've granted Vercel/Railway access to private repos

### Deployment fails on Vercel
- Check build logs for errors
- Ensure `NEXT_PUBLIC_API_URL` is set in environment variables
- Verify root directory is set to `./frontend`

### Deployment fails on Railway
- Check Railway logs for Python import errors
- Verify `DEBUG=false` is set
- Ensure PostgreSQL is accessible with the provided `DATABASE_URL`
