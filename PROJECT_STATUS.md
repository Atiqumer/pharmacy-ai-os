# Pharmacy AI OS — Project Status

**Updated:** 2 September 2026

**Branch:** `recovery-hardening`

**Stage:** Production-readiness hardening for 1–2 independent pharmacy testers

## What this project is

Pharmacy AI OS is a lightweight, owner-operated pharmacy management SaaS. It brings inventory, suppliers, purchasing, sales, returns, reports, low-stock/expiry alerts, and AI-assisted stock analysis into one web application.

The current product is deliberately focused on a single pharmacy owner/operator. It is not intended to replace a regulated clinical, prescription, patient-record, or enterprise ERP system.

## Problem being solved

Small pharmacies often manage stock in spreadsheets or disconnected tools. This creates four practical problems:

- stockouts are noticed too late;
- expiring medicine is difficult to identify early;
- purchasing, receiving, sales, and returns do not share one auditable stock history;
- owners cannot quickly turn inventory data into useful operational answers.

Pharmacy AI OS gives the operator one source of truth and converts its data into alerts, summaries, reports, and plain-language answers.

## Production architecture

| Layer | Technology | Current deployment |
|---|---|---|
| Frontend | Next.js 16, React 19, Tailwind CSS 4 | Netlify — `https://pharmacy-ai-os.netlify.app` |
| Backend API | FastAPI, Python, Uvicorn | Vercel — `https://pharmacy-ai-os.vercel.app` |
| Database | PostgreSQL with Alembic migrations | Supabase |
| AI | Groq API | Called only by the backend |
| CI | GitHub Actions | Backend tests, PostgreSQL integration tests, frontend lint and build |

Secrets are supplied through local `.env` files or hosting-provider environment variables. They must never be committed to GitHub. The browser receives only the public backend URL.

## Implemented and working

### Account and pharmacy setup

- Email/password signup and login with JWT authentication.
- Optional persistent login, plus a 30-minute inactivity timeout.
- Live account-status validation on protected backend requests.
- Admin role and account activation/archive controls.
- First-login pharmacy onboarding.
- Editable pharmacy name, owner/contact details, address, currency, low-stock threshold, and expiry-warning window.
- Owner-scoped business data: each account sees only its own pharmacy records.

### Inventory

- CSV inventory import with validation and safe product/batch upserts.
- Manual product and batch creation.
- Search, pagination, and stock/expiry filters.
- Product and batch editing/archiving.
- Atomic stock adjustments with negative-stock protection.
- Stock movement audit history with before/after quantities, reason, note, user, and timestamp.
- Cost value, retail value, potential margin, low-stock, expired, and expiring KPIs.

### Notifications

- In-app low-stock notifications.
- In-app expiry and expired-stock notifications.
- Notification thresholds come from pharmacy settings.
- Frontend refreshes notification data every two minutes while the app is open.
- Alerts are computed from current inventory, so they cannot become stale stored records.
- Alerts refresh immediately after stock-changing actions, with the two-minute poll retained as a fallback.

### Suppliers and purchasing

- Supplier creation and editing.
- Multi-line purchase-order drafts.
- Draft editing, submission, and cancellation.
- Ordered, partially received, received, and cancelled states.
- Partial/full goods receiving with supplier reference and notes.
- Batch creation/upsert, inventory increase, goods receipt, and stock-ledger entry in one transaction.
- Over-receipt prevention and ownership checks.

### Sales and returns

- Multi-item checkout.
- FEFO batch allocation (first expiry, first out).
- Atomic stock deductions and movement entries.
- Sale history and detail view.
- Partial and full returns to the exact original batch.
- Return audit records and refunded-state handling.

### Reports and AI

- 30-day sales, completed-sales, and estimated-gross-profit summary.
- Inventory CSV and sales CSV downloads.
- AI morning briefing using owner-scoped operational metrics.
- AI expiry guidance uses each pharmacy's configured warning window and exact database-calculated days remaining.
- Plain-language inventory questions converted to validated, read-only SQL.
- Query table allowlist, mandatory owner filters, timeout, row limit, and transaction safeguards.
- Browser voice input where the Web Speech API is supported.

### User experience

- Responsive SaaS shell with desktop collapse and mobile drawer navigation.
- Light glassmorphism used as a restrained surface treatment.
- Dashboard, inventory, purchasing, sales, reports, settings, onboarding, login/signup, admin, notifications, and error states share one visual system.
- Accessible disabled button states, keyboard focus indicators, responsive forms, and horizontally scrollable data tables.
- Empty, loading, success, and error states for core workflows.
- Report exports show progress and a clear success or error result.
- Core read requests recover from brief serverless/network failures with bounded retries; transaction writes are never retried automatically.

## Database and migrations

The Supabase PostgreSQL schema is managed by Alembic. Current migration head:

`20260826_0003_pharmacy_workspace.py`

The schema covers users, pharmacy profiles, products, batches, suppliers, stock movements, purchase orders/items, goods receipts/items, sales/items, and returns/items. Referential constraints and transactional writes protect inventory integrity.

## Security and operational controls

- Password hashes are stored with PostgreSQL `pgcrypto`.
- JWT secrets, database credentials, and Groq credentials remain backend-only.
- CORS is environment-configured for approved frontend origins.
- Per-endpoint rate limiting is enabled.
- Admin routes enforce backend role checks.
- SQL generated from natural language is SELECT-only, owner-scoped, table-limited, time-limited, and row-limited.
- Accounts are archived/deactivated instead of deleting their business history.
- Warm backend instances reuse a small, thread-safe PostgreSQL connection pool to reduce repeated Supabase connection overhead.
- API datetimes are serialized as explicit UTC ISO 8601 values so browsers display the correct local time.

## Verification baseline

- **63 backend unit/API tests** cover authentication, authorization, inventory, stock ledger, suppliers, purchasing, sales, returns, reports, notifications, settings, AI query safety, expiry-window accuracy, and timezone serialization.
- **2 live PostgreSQL integration tests** verify migrations and database constraints.
- Frontend ESLint and production build are required by CI.
- There is currently no automated frontend component or browser end-to-end test suite.

## Intentionally out of scope for the current release

These are product decisions, not unfinished tasks:

- SMTP/email alerts or password-reset email delivery;
- multiple staff accounts per pharmacy;
- multiple branches;
- a custom automated backup system;
- patient records, prescriptions, insurance, online payments, or regulated clinical workflows.

Supabase platform recovery/backup options remain the hosting provider's responsibility; the application will not build its own backup scheduler for the initial release.

## Remaining before testing with 1–2 pharmacies

### Required

1. Run a complete real-data acceptance test: setup → import/create stock → supplier → purchase order → receive → sale → return → reports → alerts.
2. Test on the pharmacy's actual desktop/tablet and the browsers it will use.
3. Verify production environment variables and allowed origins after every hosting change.
4. Prepare a small clean demo CSV and a one-page operator guide.
5. Record tester feedback and fix workflow blockers before adding more features.
6. Measure production latency after deployment of connection reuse; consolidate workspace endpoints only if the warm-path target is still missed.

### Valuable after tester feedback

- Printable purchase orders, goods receipts, and sales receipts.
- Barcode-scanner support if testers confirm it is important.
- Automated frontend browser tests for the critical inventory-to-sale journey.
- Basic uptime/error monitoring supplied by the hosting platforms or a free external monitor.

## Current readiness assessment

The core functional scope for a single-owner release is implemented. A production acceptance pass on 2 September 2026 verified authentication, settings, notifications, purchasing data, sale and exact-batch return, report feedback, AI briefing, local-time display, movement audit, and responsive desktop/tablet/mobile behavior. A transient first-load Sales request was reproduced and fixed with bounded GET-only retries; the deployed fix passed retesting.

The remaining risk is usability on a real pharmacy's daily data rather than a missing core backend module. The next major phase should be observed use by the pharmacy tester, Aronium import validation, and only then barcode/printing work based on evidence.
