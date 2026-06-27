# Deploying UrbanCool AI to Render

This guide covers deploying the full-stack UrbanCool AI application (FastAPI backend + React frontend) to [Render](https://render.com).

---

## Architecture Overview

Render deploys as two separate services:

```
┌─────────────────────────┐     ┌─────────────────────────────┐
│   Frontend (Static)     │────▶│   Backend (Python Web)      │
│   urban-cool-frontend/  │     │   urban-cool/               │
│   React + Vite          │     │   FastAPI + UVicorn         │
└─────────────────────────┘     └─────────────────────────────┘
```

The frontend calls `/api/*` which Render's routing forwards to the backend service.

---

## Prerequisites

- A [Render account](https://dashboard.render.com)
- Your code pushed to a GitHub repository (e.g., `Heetisk/Urban-cool-polished-`)
- Render CLI (optional, for local testing): `npm install -g @anthropic-ai/render`

---

## Step 1: Deploy the Backend (Python Web Service)

### 1.1 Create a new Web Service

1. Go to [Render Dashboard](https://dashboard.render.com) → **New** → **Web Service**
2. Connect your GitHub repo: `Heetisk/Urban-cool-polished-`
3. Configure the service:

| Field | Value |
|-------|-------|
| **Name** | `urbancool-api` |
| **Region** | Singapore (or closest to your users) |
| **Branch** | `master` |
| **Runtime** | Python 3 |
| **Build Command** | `pip install -r urban-cool/backend/requirements.txt` |
| **Start Command** | `cd urban-cool && python run_server.py` |

### 1.2 Set Environment Variables

Go to **Environment** tab and add:

| Key | Value | Notes |
|-----|-------|-------|
| `PORT` | `8000` | Render auto-sets this; explicit for clarity |
| `CORS_ORIGINS` | `https://urbancool-frontend.onrender.com` | Your frontend URL (update after deploying frontend) |
| `PYTHON_VERSION` | `3.11.9` | Pin to avoid surprises |

> **Note:** The `CORS_ORIGINS` variable tells the backend which frontend URLs are allowed to make API requests. You'll get the frontend URL after deploying it in Step 2.

### 1.3 Deploy

Click **Create Web Service**. Render will:
1. Clone your repo
2. Run `pip install -r urban-cool/backend/requirements.txt`
3. Start `python run_server.py` which runs uvicorn on port 8000

Your backend will be live at: `https://urbancool-api.onrender.com`

### 1.4 Verify Backend

Open `https://urbancool-api.onrender.com/cities` in your browser. You should see a JSON response listing available cities.

> **First request may be slow** (30-60s) due to Render's free tier cold start. The backend loads ML models into memory on startup.

---

## Step 2: Deploy the Frontend (Static Site)

### 2.1 Create a new Static Site

1. Go to [Render Dashboard](https://dashboard.render.com) → **New** → **Static Site**
2. Connect the same GitHub repo: `Heetisk/Urban-cool-polished-`
3. Configure:

| Field | Value |
|-------|-------|
| **Name** | `urbancool-frontend` |
| **Branch** | `master` |
| **Build Command** | `cd urban-cool-frontend && npm install && npm run build` |
| **Output Directory** | `urban-cool-frontend/dist` |

### 2.2 Set Environment Variables

| Key | Value |
|-----|-------|
| `VITE_API_URL` | `https://urbancool-api.onrender.com` |

> This tells the frontend where to find the backend API in production.

### 2.3 Add SPA Rewrites

Go to **Settings** → **Build & Deploy** → **Add Rewrite Rule**:

| Source | Destination |
|--------|-------------|
| `/*` | `/index.html` |

This ensures React Router handles client-side routing correctly.

### 2.4 Deploy

Click **Create Static Site**. Render will:
1. Install Node.js dependencies
2. Run `vite build` (outputs to `dist/`)
3. Serve the static files via CDN

Your frontend will be live at: `https://urbancool-frontend.onrender.com`

---

## Step 3: Update CORS Origins

After the frontend is deployed:

1. Go to **urbancool-api** → **Environment**
2. Update `CORS_ORIGINS` to include your frontend URL:
   ```
   https://urbancool-frontend.onrender.com
   ```
3. The service will auto-redeploy

---

## Step 4: Configure Custom Domains (Optional)

### Backend API
1. Go to **urbancool-api** → **Settings** → **Custom Domains**
2. Add your domain (e.g., `api.urbancool.yourdomain.com`)
3. Update `CORS_ORIGINS` to include the new domain

### Frontend
1. Go to **urbancool-frontend** → **Settings** → **Custom Domains**
2. Add your domain (e.g., `urbancool.yourdomain.com`)
3. Update DNS CNAME to point to `urbancool-frontend.onrender.com`

---

## Render Configuration Files

For automated deployments, you can add these files to your repo root:

### `render.yaml` (Blueprint)

```yaml
services:
  # Backend API
  - type: web
    name: urbancool-api
    runtime: python
    buildCommand: pip install -r urban-cool/backend/requirements.txt
    startCommand: cd urban-cool && python run_server.py
    envVars:
      - key: PYTHON_VERSION
        value: "3.11.9"
      - key: CORS_ORIGINS
        sync: false  # Set manually after frontend deploy
    healthCheckPath: /cities

  # Frontend Static Site
  - type: static
    name: urbancool-frontend
    buildCommand: cd urban-cool-frontend && npm install && npm run build
    staticPublishPath: urban-cool-frontend/dist
    envVars:
      - key: VITE_API_URL
        value: https://urbancool-api.onrender.com
    routes:
      - type: rewrite
        source: /*
        destination: /index.html
```

### `urban-cool-frontend/.env.production`

Create this file so the frontend uses the correct API URL in production:

```env
VITE_API_URL=https://urbancool-api.onrender.com
```

### Update `urban-cool-frontend/src/api.js`

Modify the API base URL to use the environment variable:

```javascript
const API_BASE = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL}/api`
  : '/api';
```

---

## Render Free Tier Limitations

| Limit | Free Tier | Paid Tier |
|-------|-----------|-----------|
| **Spin-up time** | 30-60s cold start | Instant |
| **RAM** | 512 MB | 2 GB+ |
| **CPU** | Shared | Dedicated |
| **Bandwidth** | 100 GB/month | Unlimited |
| **Build time** | 900s max | 1800s max |
| **Services** | 1 web + 1 static | Unlimited |

> **Tip:** The backend loads ML models (~50MB) into memory on startup. On free tier, this causes a cold start delay. Consider upgrading to Starter ($7/mo) for faster response times.

---

## Troubleshooting

### Backend won't start

**Check logs:** Go to **urbancool-api** → **Logs**

Common issues:
- **ModuleNotFoundError:** Ensure `buildCommand` includes `pip install -r urban-cool/backend/requirements.txt`
- **FileNotFoundError (data files):** The `urban-cool/data/` directory must be in your repo
- **Port error:** Render sets `$PORT` automatically; ensure `run_server.py` uses it

### Frontend shows "Failed to fetch"

**Cause:** CORS or wrong API URL

**Fix:**
1. Verify `CORS_ORIGINS` includes your frontend URL
2. Check `VITE_API_URL` environment variable
3. Ensure the backend is running (check logs)

### Build fails on npm install

**Cause:** Node.js version mismatch

**Fix:** Add `NODE_VERSION=18` to frontend environment variables.

### Static site shows blank page

**Cause:** Missing SPA rewrite rule

**Fix:** Add rewrite rule `/* → /index.html` in Static Site settings.

---

## Updating the Deployment

Push changes to your `master` branch. Render auto-deploys on push.

To deploy manually:
1. Go to the service dashboard
2. Click **Manual Deploy** → **Deploy latest commit**

---

## Cost Estimate

For a demo/hackathon project on Render:

| Service | Plan | Monthly Cost |
|---------|------|--------------|
| Backend | Free | $0 |
| Frontend | Free | $0 |
| **Total** | | **$0** |

> The free tier is sufficient for demos. For production, budget ~$14/month (Starter backend + Static site).

---

## Quick Reference

| Resource | URL |
|----------|-----|
| Frontend | `https://urbancool-frontend.onrender.com` |
| Backend API | `https://urbancool-api.onrender.com` |
| API Docs | `https://urbancool-api.onrender.com/docs` |
| Health Check | `https://urbancool-api.onrender.com/cities` |

---

## Alternative: Single Service Deployment

If you prefer one service serving both frontend and backend:

### Backend serves static files

Add to `urban-cool/backend/main.py`:

```python
from fastapi.staticfiles import StaticFiles

# After all API routes, serve the frontend build
frontend_build = os.path.join(os.path.dirname(__file__), "..", "..", "urban-cool-frontend", "dist")
if os.path.exists(frontend_build):
    app.mount("/", StaticFiles(directory=frontend_build, html=True), name="frontend")
```

### Render config

| Field | Value |
|-------|-------|
| **Build Command** | `pip install -r urban-cool/backend/requirements.txt && cd urban-cool-frontend && npm install && npm run build` |
| **Start Command** | `cd urban-cool && python run_server.py` |

This approach:
- ✅ Single URL (no CORS issues)
- ✅ Simpler deployment
- ❌ Slower builds (installs both Python + Node)
- ❌ No CDN for static assets

---

*Last updated: June 2026*
