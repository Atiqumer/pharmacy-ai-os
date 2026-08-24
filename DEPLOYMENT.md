# RxOS production deployment

## Required services

- PostgreSQL 16 or newer
- Backend container built from `backend/Dockerfile`
- Frontend container built from `frontend/Dockerfile`
- SMTP provider for password-reset email
- Groq API access

The application does not commit or embed secrets. Configure all sensitive values through the deployment platform's encrypted environment-variable controls.

## Required backend environment

```text
APP_ENV=production
DATABASE_URL=postgresql://...
GROQ_API_KEY=...
JWT_SECRET=...                 # random, at least 32 bytes
JWT_EXPIRY_HOURS=24
CORS_ORIGINS=https://rxos.example.com
FRONTEND_URL=https://rxos.example.com
PASSWORD_RESET_DELIVERY=smtp
SMTP_HOST=...
SMTP_PORT=587
SMTP_USERNAME=...
SMTP_PASSWORD=...
SMTP_FROM_EMAIL=...
SMTP_USE_SSL=false
```

The backend container runs `alembic upgrade head` before starting the API. A migration failure prevents the service from accepting traffic.

## Frontend build variable

`NEXT_PUBLIC_API_URL` is a build-time variable and must contain the public HTTPS backend URL. Rebuild the frontend whenever this URL changes.

```text
NEXT_PUBLIC_API_URL=https://api.rxos.example.com
```

## First deployment

1. Provision PostgreSQL and require TLS connections.
2. Configure backend secrets and deploy the backend container.
3. Confirm `GET /health/live` returns 200.
4. Confirm `GET /health/ready` returns 200 and the current migration revision.
5. Build the frontend with the public backend URL.
6. Configure the frontend domain in backend `CORS_ORIGINS` and `FRONTEND_URL`.
7. Test signup, login, password-reset email, CSV import, stock adjustment, purchase ordering, and goods receiving with a non-production pharmacy account.

## Existing pre-Alembic database

Do not run the initial migration blindly against an existing RxOS database. Take a verified backup first. Compare its schema with `backend/migrations/versions/20260825_0001_initial_schema.py`, apply any missing columns/tables in a controlled migration, and then stamp the verified revision:

```text
alembic stamp 20260825_0001
```

For a new deployment, use `alembic upgrade head` normally.

## Operational requirements

- Automated daily PostgreSQL backups with restore drills
- HTTPS only; never expose PostgreSQL publicly
- Application error monitoring and centralized logs
- Uptime checks against `/health/ready`
- Groq and SMTP usage/error monitoring
- Regular secret rotation
- A staging environment that runs migrations before production
