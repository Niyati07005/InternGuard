# InternGuard

InternGuard is a full-stack app for screening job and internship postings, recruitment messages, offer letters, and URLs for potential risk indicators.

## Features

- React + Vite frontend with responsive light-first design and a working dark-mode toggle.
- FastAPI backend and SQLite scan history.
- Private per-browser guest workspaces plus optional account registration, login, signed sessions, and per-user scan history.
- Explainable rule-based checks combined with TF-IDF and logistic regression.
- Licensed real-world job posting dataset with a stratified holdout evaluation.
- PDF text extraction with OCR fallback for scanned pages; downloadable PDF reports.
- Dashboard statistics, charts, search, filters, scan details, and delete actions.
- New guest workspaces can be seeded with clearly labeled low/medium/high sample job scans for previewing the dashboard; samples are private to the workspace and removable from history.
- Bounded DNS, RDAP, and TLS checks, with optional VirusTotal reputation data.

## Run locally

Prerequisites: Node.js 20+ and Python 3.11+.

Backend, from the project root:

```powershell
Copy-Item .env.example .env
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

For persistent local sessions, replace `SESSION_SECRET` in `.env` with a long random value. Set `SESSION_COOKIE_SECURE=true` only when serving over HTTPS. VirusTotal is optional; set `VIRUSTOTAL_API_KEY` to enable it. Without a key, that source is explicitly reported as not configured.

Frontend, in a second terminal from the project root:

```powershell
cd frontend
npm install
npm run dev
```

Open the Vite address (typically http://localhost:5173). The API documentation is at http://127.0.0.1:8000/docs.

## Detection notes

The model uses the Real / Fake Job Posting Prediction dataset, distributed under CC0 1.0, with source and attribution recorded in [`backend/data/DATASET_ATTRIBUTION.txt`](backend/data/DATASET_ATTRIBUTION.txt). If that dataset is unavailable, the application clearly switches to the included synthetic baseline. The dashboard shows measured precision, recall, F1-score, and a confusion matrix from a fixed, stratified 80/20 holdout split; these are not external validation results. The combined score uses transparent rules and a smaller classifier contribution; the classifier output is not presented as a probability that fraud occurred.

URL verification checks DNS records and RDAP registration where available, and validates TLS certificates on standard HTTPS port 443. Requests have timeouts and do not follow redirects or open the submitted page. VirusTotal results are optional and only queried when configured. Unavailable data is not treated as a clean result, and HTTPS does not establish company authenticity.

PDF text is extracted directly when available; pages without enough selectable text use local RapidOCR. Uploads are limited to 10 MB and 100 pages. OCR may fail on faint, rotated, or low-quality scans; unreadable content is reported rather than silently treated as a complete review.

Scores are preliminary indicators: 0–30 LOW, 31–60 MEDIUM, and 61–100 HIGH. This tool cannot prove an opportunity fraudulent or legitimate. Independently verify before acting.

The app opens directly into a private guest workspace; sign-in is optional. Guest scans are tied to the browser's signed session, and guest history is transferred to the account when registering or signing in from that workspace. Registered scan records are private to that account. Existing records from a pre-authentication database are left unassigned and are not exposed to new users.

## Tests

From `backend` with its environment active:

```powershell
pytest
```

Frontend production build:

```powershell
cd frontend
npm run build
```

## Production deployment: Vercel + Render

The deployment files are [`frontend/vercel.json`](frontend/vercel.json) and [`render.yaml`](render.yaml). Vercel serves the Vite frontend; Render runs FastAPI and a managed PostgreSQL database. The production backend refuses to start without a persistent PostgreSQL `DATABASE_URL`, a strong session secret, and an explicit CORS origin.

### 1. Push the project to GitHub

Create a GitHub repository and push this project. Do not commit `.env` files, API keys, passwords, database files, or generated model artifacts. The checked-in `.env.example` files contain placeholders only. The `VITE_API_URL` value is a public API address, not a secret.

### 2. Create the Vercel frontend

1. Import the GitHub repository into Vercel.
2. Set **Root Directory** to `frontend` and use the Vite framework preset.
3. Add `VITE_API_URL` as a Production environment variable after the Render API has deployed. Its value must be the Render service origin followed by `/api`, for example `https://internguard-api.onrender.com/api` (use the actual URL Render assigns).
4. Deploy. Until the API URL is set, the frontend may load but its API-backed features will not work.

`frontend/vercel.json` configures `npm ci`, the production build, static output, and a single-page-app fallback. For Vercel Preview deployments, configure `VITE_API_URL` there too and add each preview origin explicitly to the backend CORS list if previews need API access.

### 3. Create the Render backend and database

1. In Render, create a **Blueprint** from the same GitHub repository; Render reads the root `render.yaml`.
2. When prompted for `CORS_ORIGINS`, enter the exact Vercel Production origin, with no path or trailing slash (for example `https://internguard.vercel.app`). Add any other required frontend origins as comma-separated exact origins; do not use `*`.
3. Apply the Blueprint. It creates the FastAPI web service and a managed PostgreSQL database, and generates `SESSION_SECRET` in Render. Wait for the service health check at `/api/health`.
4. In the Render service's environment settings, optionally add `VIRUSTOTAL_API_KEY`. Never add it as a `VITE_` variable or commit it to source control.
5. Copy the actual Render service URL and set Vercel's `VITE_API_URL` to `<render-service-url>/api`, then redeploy the Vercel frontend.

The Blueprint uses a 2 GB Render web plan because the classifier trains from the bundled licensed dataset when the service starts. It uses a persistent PostgreSQL plan for user accounts and scan history; no production records are written to the web service's ephemeral filesystem. Both plans may incur charges. Vercel's static hosting can use its free tier. Render's free web service sleeps when idle and has limited memory; Render's free PostgreSQL expires 30 days after creation, so the free database is not suitable for permanent user data. Review current provider pricing before applying the Blueprint.

PDFs are processed in memory. InternGuard stores extracted text and analysis/report data in PostgreSQL, not the uploaded original PDF. PDF extraction/OCR, model training and report generation run on the Render backend. The bundled CSV and attribution notice are deployed with the backend source.

### Production settings and browser sessions

The Render Blueprint sets `ENVIRONMENT=production`, `SESSION_COOKIE_SECURE=true`, and `SESSION_COOKIE_SAMESITE=none`; it wires `DATABASE_URL` to the managed Postgres instance and generates `SESSION_SECRET`. The backend accepts only the configured `CORS_ORIGINS` and requires credentialed requests. The Vercel API URL is baked into the frontend at build time, so redeploy after changing it.

For browsers that block third-party cookies between `*.vercel.app` and `*.onrender.com`, use custom domains under the same registered domain (for example `app.example.com` and `api.example.com`), then update `VITE_API_URL` and `CORS_ORIGINS` to those exact HTTPS origins. The frontend already sends session cookies with API requests.

### What must be configured manually

- A GitHub repository connected to both providers.
- The Vercel project root directory (`frontend`) and its `VITE_API_URL`.
- The exact Vercel origin entered for Render `CORS_ORIGINS`.
- Optional VirusTotal key in Render only.
- Provider billing/plan selection and (optionally) custom domains.

Deployment is not complete until both provider builds succeed, `https://<render-service>/api/health` returns `{"status":"ok","service":"InternGuard"}`, and the Vercel app can register/sign in, analyze a posting, upload a PDF, verify a URL, and download a report.
