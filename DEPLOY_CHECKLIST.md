# signaLayer.ai Deployment Checklist

## Pre-Deployment

- [ ] Register `signaLayer.ai` domain
- [ ] Create GitHub account (alinojoumi8)
- [ ] Push frontend code to `signalaLayer-frontend` repo
- [ ] Push backend code to `signalaLayer-backend` repo

## Infrastructure Setup

- [ ] Create Vercel account + connect frontend repo
- [ ] Create Railway account + connect backend repo
- [ ] Set up PostgreSQL on Railway
- [ ] Add all environment variables to Railway
- [ ] Add all environment variables to Vercel

## External Services

- [ ] Configure Stripe API keys (secret key, webhook secret, price ID)
- [ ] Get Alpha Vantage API key
- [ ] Get MiniMax API key
- [ ] Get FRED API key

## DNS & Domain

- [ ] Configure Cloudflare DNS for `signaLayer.ai` → Vercel
- [ ] Configure Cloudflare DNS for `api.signaLayer.ai` → Railway
- [ ] Enable Cloudflare SSL/TLS (Full mode)
- [ ] Wait for DNS propagation (24-48 hours)

## Deployment & Testing

- [ ] Trigger first Vercel deployment
- [ ] Trigger first Railway deployment
- [ ] Test `/api/health/live` endpoint
- [ ] Test `/api/health/ready` endpoint
- [ ] Run first content generation pipeline
- [ ] Verify Stripe webhook is working
- [ ] Send first test email/Slack notification
- [ ] Test full user registration/login flow
- [ ] Test Stripe checkout flow

## Post-Deployment Verification

- [ ] Verify HTTPS is working on signaLayer.ai
- [ ] Verify HTTPS is working on api.signaLayer.ai
- [ ] Check Vercel function logs for errors
- [ ] Check Railway deployment logs for errors
- [ ] Monitor PostgreSQL connection stability
- [ ] Enable Railway automatic deployments from main branch
