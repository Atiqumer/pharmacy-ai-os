# RxOS

RxOS is an AI-assisted inventory operations application for independent pharmacies. The current MVP imports batch-level inventory from CSV, identifies low stock and expiry risk, and lets authenticated users ask inventory questions in plain English.

## Current status

The recovered prototype has been stabilized on the `recovery-hardening` branch. Backend tests and the frontend production build pass. Docker is the intended local stack, but Docker Desktop must be installed separately on Windows.

Implemented:

- FastAPI API with PostgreSQL storage
- Next.js dashboard
- JWT authentication and admin/user roles
- Live account status and role validation
- Tenant-scoped products, batches, and suppliers
- Validated, idempotent CSV inventory import
- Searchable inventory dashboard with stock, expiry, and valuation KPIs
- Manual batch creation, controlled stock adjustments, and auditable movement history
- Supplier directory, multi-line purchase orders, and atomic goods receiving
- Reorder suggestions based on minimum-stock targets and previous supplier/cost
- Versioned Alembic migrations and real-PostgreSQL CI tests
- Hashed password-reset tokens and session invalidation (email delivery disabled for this pilot)
- AI morning briefing through Groq
- Tenant-validated, read-only natural-language inventory queries
- Editable product and batch details with safe zero-stock archival
- Pilot sales checkout with FEFO batch allocation, discounts, and exact-batch returns
- Sales and inventory CSV exports plus 30-day operational reporting
- Editable/cancellable draft purchasing and supplier editing
- Backend unit tests and GitHub Actions CI
- First-login pharmacy onboarding and an editable single-pharmacy workspace profile
- In-app low-stock and expiry notifications with configurable alert preferences

Intentionally outside the current pilot scope:

- Email/SMTP password-reset delivery remains disabled
- Multi-staff accounts and multi-branch organizations are not planned for this pilot
- Automated backup infrastructure is not part of this free pilot deployment
- Purchase orders and receipts are not yet printable
- Patient, prescription, payment-card, and regulated medicine data are outside the pilot scope

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

Current verified baseline: 60 backend tests pass locally, two PostgreSQL integration tests pass against the migrated database and run in CI, ESLint passes with zero warnings, and the Next.js production build succeeds.

## Inventory CSV format

Required columns:

```text
product_name,generic_name,category,batch_number,quantity,cost_price,retail_price,expiry_date
```

`min_stock_level` is optional and defaults to 10. Dates must use `YYYY-MM-DD`. Imports are capped at 5 MB and 5,000 rows. Re-importing the same product and batch updates it instead of duplicating its stock.

See `mock_inventory.csv` for an example.

## Product direction

See `DEPLOYMENT.md` for migration, health-check, secret-safety, and deployment guidance. The next milestone is controlled validation with one or two pharmacy testers using the onboarding, alert, inventory, purchasing, and sales workflows.
