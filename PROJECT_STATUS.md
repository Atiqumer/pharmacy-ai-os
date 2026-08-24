# Project Status: AI-Powered Pharmacy Operating System (RxOS)

## Overview
A full-stack application that combines a Python/FastAPI backend with a Next.js/React frontend to provide AI-powered inventory management, conversational database querying, and operational analytics for independent medical stores.

---

## Tech Stack

### Backend
- **Framework:** FastAPI (Python 3.13)
- **Database:** PostgreSQL 16 with `psycopg2`
- **AI Engine:** Groq API (Llama 3.3 70B Versatile)
- **Data Processing:** Pandas
- **Auth:** JWT (PyJWT) with PostgreSQL `pgcrypto` password hashing
- **RBAC:** Role-based access control (admin/user)
- **SQL Validation:** `sqlparse` for injection protection
- **Rate Limiting:** `slowapi` (per-endpoint limits)
- **Testing:** `pytest` + `httpx`
- **Env Management:** `python-dotenv`
- **Deployment:** Docker + Docker Compose

### Frontend
- **Framework:** Next.js 16.2.9 (React 19.2.4)
- **Styling:** Tailwind CSS 4
- **Compiler:** React Compiler (babel-plugin-react-compiler)
- **Utilities:** react-markdown (for rendering AI briefing output)
- **Voice Input:** Web Speech API (browser-native)
- **Auth:** Custom AuthContext with JWT token management
- **Routing:** App Router with `/login`, `/admin`, `/forgot-password` pages
- **Deployment:** Docker (standalone output)

---

## Architecture

```
pharmacy/
├── .github/
│   └── workflows/
│       └── ci.yml                  # GitHub Actions CI (pytest + npm build)
├── .env.example                    # Root env template for Docker Compose
├── docker-compose.yml              # Production stack (db + backend + frontend)
├── backend/
│   ├── Dockerfile                  # Python 3.13-slim container
│   ├── .env                        # Secrets
│   ├── .env.example                # Backend env template
│   ├── .dockerignore
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── pyproject.toml
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   └── test_api.py             # 30 unit tests
│   └── app/
│       ├── main.py                 # FastAPI entrypoint, lifespan, CORS, rate limiting
│       ├── database.py             # PostgreSQL connection + auto table init
│       ├── middleware/
│       │   ├── __init__.py
│       │   └── logging.py          # Request/response logging
│       ├── routes/
│       │   ├── __init__.py
│       │   ├── auth.py             # signup, login, me, password reset
│       │   ├── admin.py            # User management (admin-only)
│       │   ├── inventory.py        # CSV upload (auth-protected)
│       │   ├── analytics.py        # Morning briefing (auth-protected)
│       │   └── query.py            # NL→SQL query (auth-protected)
│       └── services/
│           ├── auth.py             # JWT, RBAC, get_current_user, require_role
│           ├── ai_service.py       # Briefing generation (owner-scoped)
│           └── query_service.py    # NL→SQL with sqlparse validation
├── frontend/
│   ├── Dockerfile                  # Multi-stage Node.js 20 build
│   ├── .dockerignore
│   ├── next.config.mjs             # Standalone output for Docker
│   ├── .env.local
│   ├── .env.example
│   └── src/
│       ├── contexts/
│       │   └── AuthContext.js      # Auth state + isAdmin flag
│       ├── components/
│       │   └── ErrorBoundary.js
│       └── app/
│           ├── layout.js
│           ├── globals.css
│           ├── page.js             # Main dashboard (auth-gated, admin badge)
│           ├── login/page.js       # Login/signup + forgot password link
│           ├── forgot-password/page.js  # Password reset flow
│           └── admin/page.js       # Admin panel (user management)
└── mock_inventory.csv
```

---

## API Endpoints

| Method | Endpoint | Auth | Role | Rate Limit | Description |
|--------|----------|------|------|------------|-------------|
| GET | `/` | No | - | 30/min | Health check |
| POST | `/auth/signup` | No | - | - | Create account |
| POST | `/auth/login` | No | - | - | Sign in |
| GET | `/auth/me` | Yes | any | - | Get current user |
| POST | `/auth/password-reset-request` | No | - | - | Request password reset |
| POST | `/auth/password-reset-confirm` | No | - | - | Confirm password reset |
| GET | `/admin/users` | Yes | admin | 30/min | List all users |
| PUT | `/admin/users/role` | Yes | admin | 10/min | Update user role |
| PUT | `/admin/users/active` | Yes | admin | 10/min | Activate/deactivate user |
| DELETE | `/admin/users/{id}` | Yes | admin | 5/min | Delete user |
| POST | `/inventory/upload-csv` | Yes | any | 10/min | Upload CSV inventory |
| GET | `/inventory/summary` | Yes | any | 30/min | Stock, expiry, and valuation KPIs |
| GET | `/inventory/items` | Yes | any | 30/min | Searchable/filterable batch inventory |
| GET | `/analytics/morning-briefing` | Yes | any | 5/min | AI briefing |
| GET | `/query/ask?q=` | Yes | any | 15/min | NL→SQL query |

---

## Features

### 1. User Authentication & RBAC
- JWT-based auth with `pgcrypto` password hashing
- Two roles: `user` (default) and `admin`
- Admin can manage users: list, change roles, activate/deactivate, delete
- Password reset flow with token-based confirmation
- Deactivated users cannot log in

### 2. Multi-Tenancy
- All data (Product, Batch, Supplier) scoped to owner via `ownerId` FK
- Admin can view all data across users
- Active status and current role are revalidated from PostgreSQL on each protected request

### 3. CSV Inventory Import
- Upload `.csv` with columns: `product_name`, `generic_name`, `category`, `batch_number`, `quantity`, `cost_price`, `retail_price`, `expiry_date`
- Optional: `min_stock_level` (defaults to `10`)
- Validates size, row count, text, dates, quantities, and prices before writing
- Safely upserts Product, Supplier, and Batch records scoped to the user

### 4. Inventory Operations Dashboard
- Tenant-scoped batch inventory with server-side search and pagination
- Low-stock, in-stock, expiring, expired, and valid filters
- Product/unit totals, inventory cost, retail value, and potential margin
- Automatic dashboard refresh after a successful import

### 5. AI Morning Briefing
- Pulls SKU count, low-stock items, items expiring within 90 days
- Owner-scoped data sent to Llama 3.3 via Groq
- Markdown briefing rendered with react-markdown

### 6. Conversational Database Explorer
- Plain English question → LLM → validated SQL → results
- Voice input via Web Speech API (Chrome/Edge)

### 7. Security
- **SQL Injection:** `sqlparse` parsing + SELECT-only + keyword blocklist + table allowlist + mandatory per-table tenant filters
- **Query Safety:** read-only transactions, five-second statement timeout, and 100-row response cap
- **Auth:** JWT with configurable expiry plus live database account validation
- **RBAC:** Admin-only routes with `require_role()` dependency
- **CORS:** Configurable via env var
- **Rate Limiting:** Per-endpoint via slowapi
- **Logging:** Structured request/response logging

---

## Database Schema

| Table | Key Columns |
|-------|-------------|
| `User` | id (UUID), email (unique), password_hash, full_name, role (user/admin), is_active, created_at |
| `Product` | id (UUID), name, genericName, category, minStockLevel, ownerId (FK→User) |
| `Batch` | id (UUID), batchNumber, productId (FK), supplierId (FK), quantity, costPrice, retailPrice, expiryDate, ownerId (FK→User) |
| `Supplier` | id (UUID), name, ownerId (FK→User) |
| `PasswordReset` | id (UUID), userId (FK→User), token, expires_at, used |

Tables auto-create on startup via `init_db()`.

---

## Deployment

### Docker Compose (Recommended)
```bash
# 1. Create .env from template
cp .env.example .env
# Edit .env with your GROQ_API_KEY and JWT_SECRET

# 2. Start the stack
docker-compose up -d

# 3. Access
# Frontend: http://localhost:3000
# Backend:  http://localhost:8000
# Database: localhost:5432
```

### Local Development
```bash
# Backend
cd backend
cp .env.example .env
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

---

## Environment Variables

### Backend
| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `DATABASE_URL` | Yes | - | PostgreSQL connection string |
| `GROQ_API_KEY` | Yes | - | Groq API key |
| `JWT_SECRET` | Yes | dev-secret | JWT signing secret (32+ chars) |
| `JWT_EXPIRY_HOURS` | No | 24 | Token lifetime |
| `CORS_ORIGINS` | No | http://localhost:3000 | Allowed origins |

### Frontend
| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `NEXT_PUBLIC_API_URL` | No | http://127.0.0.1:8000 | Backend API URL |

---

## Testing

**30 tests passing** across 7 test classes:

| Class | Tests | Coverage |
|-------|-------|----------|
| `TestHealthEndpoint` | 1 | Root endpoint |
| `TestSQLValidation` | 11 | SELECT-only, keywords, tables, tenant filters, edge cases |
| `TestJWTAuth` | 5 | Token validation, protected endpoints |
| `TestUploadCSVValidation` | 2 | File type and column validation |
| `TestInventoryReporting` | 3 | Summary, list filters, and tenant-scoped query parameters |
| `TestAuthSignupValidation` | 3 | Password length, fields, login flow |
| `TestRBAC` | 5 | Admin access, user denial, live role/status enforcement |

Run: `cd backend && .venv/Scripts/python -m pytest -v` on Windows, or `.venv/bin/python -m pytest -v` on Linux/macOS.

---

## CI/CD

GitHub Actions (`.github/workflows/ci.yml`):
- **Backend:** Python 3.11, pip install, pytest
- **Frontend:** Node.js 20, npm ci, lint, build

---

## Known Gaps / Next Steps
1. Password-reset delivery is development-only and returns the token in the response
2. No email verification on signup
3. No frontend tests (Jest/Playwright)
4. No integration tests with real PostgreSQL in CI
5. No manual inventory CRUD, stock ledger, purchasing, or sales/POS workflow yet
6. No production hosting configuration or monitoring
