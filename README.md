# RxOS

RxOS is an AI-assisted inventory operations application for independent pharmacies. The current MVP imports batch-level inventory from CSV, identifies low stock and expiry risk, and lets authenticated users ask inventory questions in plain English.

## Current status

The recovered prototype has been stabilized on the `codex/recovery-hardening` branch. Backend tests and the frontend production build pass. Docker is the intended local stack, but Docker Desktop must be installed separately on Windows.

Implemented:

- FastAPI API with PostgreSQL storage
- Next.js dashboard
- JWT authentication and admin/user roles
- Live account status and role validation
- Tenant-scoped products, batches, and suppliers
- Validated, idempotent CSV inventory import
- AI morning briefing through Groq
- Tenant-validated, read-only natural-language inventory queries
- Backend unit tests and GitHub Actions CI

Not yet production-ready:

- Password reset still exposes a development token instead of sending email
- No real-database integration tests
- No inventory CRUD UI, stock ledger, purchasing, or sales/POS
- No cloud deployment, backups, monitoring, or alert delivery

## Local setup with Docker

1. Install Docker Desktop and ensure `docker` is available in the terminal.
2. Copy `.env.example` to `.env`.
3. Set a strong `POSTGRES_PASSWORD` and `JWT_SECRET`, plus a valid `GROQ_API_KEY`.
4. Run:

```powershell
docker compose up --build
```

Open the dashboard at `http://localhost:3000`. The API is at `http://localhost:8000`, with interactive documentation at `http://localhost:8000/docs`.

## Local setup without Docker

Use PostgreSQL 16 and create a database/user matching `backend/.env`.

Backend on Windows:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Frontend in another terminal:

```powershell
cd frontend
npm ci
npm run dev
```

## Verification

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q

cd ..\frontend
npm run lint -- --max-warnings=0
npm run build
```

Current verified baseline: 27 backend tests pass, ESLint passes with zero warnings, and the Next.js production build succeeds.

## Inventory CSV format

Required columns:

```text
product_name,generic_name,category,batch_number,quantity,cost_price,retail_price,expiry_date
```

`min_stock_level` is optional and defaults to 10. Dates must use `YYYY-MM-DD`. Imports are capped at 5 MB and 5,000 rows. Re-importing the same product and batch updates it instead of duplicating its stock.

See `mock_inventory.csv` for an example.

## Product direction

The next milestone is a dependable pharmacy inventory MVP: inventory list and editing, expiry/low-stock dashboards, stock adjustments, supplier management, valuation, and reorder suggestions. Sales/POS should follow only after the inventory ledger is reliable and audited.
