# Project Status: AI-Powered Pharmacy Operating System (RxOS)

## Overview
A full-stack application that combines a Python/FastAPI backend with a Next.js/React frontend to provide AI-powered inventory management, conversational database querying, and operational analytics for independent medical stores.

---

## Tech Stack

### Backend
- **Framework:** FastAPI (Python)
- **Database:** PostgreSQL (via Supabase) with `psycopg2`
- **AI Engine:** Groq API (Llama 3.3 70B Versatile)
- **Data Processing:** Pandas
- **Env Management:** `python-dotenv`

### Frontend
- **Framework:** Next.js 16.2.9 (React 19.2.4)
- **Styling:** Tailwind CSS 4
- **Compiler:** React Compiler (babel-plugin-react-compiler)
- **Utilities:** react-markdown (for rendering AI briefing output)
- **Voice Input:** Web Speech API (browser-native)

---

## Architecture

```
pharmacy/
├── backend/
│   ├── .env                    # Secrets (DATABASE_URL, GROQ_API_KEY)
│   ├── requirements.txt
│   └── app/
│       ├── main.py             # FastAPI entrypoint, CORS, router mounting
│       ├── database.py         # PostgreSQL connection via psycopg2
│       ├── routes/
│       │   ├── inventory.py    # POST /inventory/upload-csv
│       │   ├── analytics.py    # GET /analytics/morning-briefing
│       │   └── query.py        # GET /query/ask?q=...
│       └── services/
│           ├── ai_service.py   # Morning briefing generation (Llama 3.3)
│           └── query_service.py # Natural language → SQL translation
├── frontend/
│   └── src/app/
│       ├── layout.js           # Root layout (Geist fonts, dark mode)
│       ├── globals.css         # Tailwind + theme variables
│       └── page.js             # Single-page UI (upload, search, briefing)
└── mock_inventory.csv          # Sample 5-record inventory dataset
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Health check — returns system status |
| POST | `/inventory/upload-csv` | Accepts CSV file, parses with Pandas, upserts into Product/Supplier/Batch tables |
| GET | `/analytics/morning-briefing` | Aggregates stock/expiry data, sends to Llama 3.3 for operational summary |
| GET | `/query/ask?q=` | Translates natural language question to SQL via LLM, executes, returns results |

---

## Features

### 1. CSV Inventory Import
- Upload `.csv` files with columns: `product_name`, `generic_name`, `category`, `batch_number`, `quantity`, `cost_price`, `retail_price`, `expiry_date`
- Auto-creates `Product`, `Supplier`, and `Batch` records in PostgreSQL
- Validates required columns before processing

### 2. AI Morning Briefing
- Pulls total SKU count, low-stock items (below `minStockLevel`), and items expiring within 90 days
- Sends structured data to Llama 3.3 via Groq for a concise markdown briefing
- Rendered in the frontend with `react-markdown`

### 3. Conversational Database Explorer
- User types or speaks a plain English question
- LLM translates it to a safe `SELECT`-only SQL query
- Results displayed in a dynamic table
- Voice input via Web Speech API (Chrome/Edge)

---

## Database Schema (Supabase PostgreSQL)

| Table | Key Columns |
|-------|-------------|
| `Product` | id (UUID), name, genericName, category, minStockLevel |
| `Batch` | id (UUID), batchNumber, productId (FK), supplierId (FK), quantity, costPrice, retailPrice, expiryDate |
| `Supplier` | id (UUID), name |

---

## Current Status: MVP / Early Development

| Area | Status |
|------|--------|
| Backend API | Functional — 3 route groups wired up |
| Frontend UI | Single-page prototype with all 3 features wired |
| Database | Supabase PostgreSQL (connection via env `DATABASE_URL`) |
| AI Integration | Groq + Llama 3.3 active for briefing & NL-to-SQL |
| Voice Input | Implemented via Web Speech API |
| Authentication | Not implemented |
| Testing | None |
| Deployment | Not configured (localhost `127.0.0.1:8000` / Next.js dev) |
| Error Handling | Basic try/catch with HTTP exceptions |
| Documentation | None (this file is the first) |

---

## Environment Variables Required

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Supabase PostgreSQL connection string |
| `GROQ_API_KEY` | API key for Groq (Llama 3.3 access) |

---

## Sample Data
`mock_inventory.csv` contains 5 sample records:
- Amoxicillin 500mg (150 units, exp 2026-12-15)
- Lipitor 20mg (5 units, exp 2026-07-10)
- Panadol 500mg (500 units, exp 2027-03-01)
- Augmentin 625mg (8 units, exp 2026-06-30)
- Zithromax 250mg (40 units, exp 2026-08-05)

---

## Known Gaps / Next Steps
1. No user authentication or role-based access control
2. No tests (unit or integration)
3. No CI/CD or deployment pipeline
4. Hardcoded backend URL (`http://127.0.0.1:8000`) in frontend — needs env-based config
5. No input sanitization on LLM-generated SQL beyond SELECT-only rule
6. No logging or monitoring
7. `layout.js` still has default "Create Next App" metadata
