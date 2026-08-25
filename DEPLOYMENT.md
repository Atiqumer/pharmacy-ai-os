# RxOS free deployment guide

This guide deploys the current `recovery-hardening` branch using:

- **Supabase Free** for PostgreSQL
- **Vercel Hobby** for the FastAPI backend
- **Netlify Free** for the Next.js frontend
- **Groq** for the existing AI features

The application keeps its own PostgreSQL access, Alembic migrations, and JWT authentication. Supabase is used as the PostgreSQL host only; do not enable Supabase Auth for this deployment.

> This free stack is suitable for development, demos, and low-traffic evaluation. Supabase Free can pause inactive projects and does not include automatic database backups. Do not use it for real patient or regulated production data without reviewing security, privacy, backup, availability, and compliance requirements.

## 1. Before you begin

Create free accounts for:

1. [Supabase](https://supabase.com/)
2. [Vercel](https://vercel.com/)
3. [Netlify](https://www.netlify.com/)
4. [Groq](https://console.groq.com/) if you do not already have an API key

The GitHub repository must contain the latest `recovery-hardening` branch. Never put a real password, connection string, JWT secret, Groq key, or SMTP credential in GitHub. Enter secrets only in the hosting dashboards or a local ignored `.env` file.

## 2. Create the Supabase database

1. In Supabase, select **New project**.
2. Choose the Free plan and a region close to the expected users and Vercel region.
3. Generate and save a strong database password in a password manager.
4. Wait until the project finishes provisioning.
5. Open the project and select **Connect**.

You need two connection strings from the Connect dialog:

| Purpose | Supabase connection | Port |
| --- | --- | --- |
| Vercel backend runtime | Shared Pooler, **Transaction mode** | `6543` |
| Alembic migrations from your computer | Shared Pooler, **Session mode** | `5432` |

They will look similar to:

```text
postgresql://postgres.PROJECT_REF:PASSWORD@aws-0-REGION.pooler.supabase.com:6543/postgres?sslmode=require
postgresql://postgres.PROJECT_REF:PASSWORD@aws-0-REGION.pooler.supabase.com:5432/postgres?sslmode=require
```

Use the exact values shown by Supabase. Replace the password placeholder locally. If the password contains URL-reserved characters such as `@`, `:`, `/`, `?`, `#`, or `%`, percent-encode the password before placing it in a URL.

Do not use the Supabase `anon` key or service-role key as `DATABASE_URL`. This backend requires a PostgreSQL connection string.

## 3. Apply the database migrations

Run this once from PowerShell on your computer before deploying the backend:

```powershell
cd D:\Pharmcay-ai-os\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:DATABASE_URL='PASTE_THE_SESSION_POOLER_5432_URL_HERE'
python -m alembic -c alembic.ini upgrade head
python -m alembic -c alembic.ini current
Remove-Item Env:DATABASE_URL
```

Expected current revision:

```text
20260825_0002 (head)
```

If the migration fails, do not deploy or manually create random tables. Check that:

- the Supabase project is running;
- the URL is the **Session mode** pooler URL on port `5432`;
- the password is correct and URL-encoded;
- `?sslmode=require` is present.

For a brand-new Supabase project, use `upgrade head` exactly as above. The `alembic stamp` command is only for an older database whose schema has already been independently verified to match the migration.

## 4. Deploy the FastAPI backend to Vercel

### Import the project

1. In Vercel, select **Add New > Project**.
2. Import the GitHub repository.
3. Select `recovery-hardening` as the production branch. If the import screen does not offer it, import first and then change **Settings > Git > Production Branch**.
4. Set **Root Directory** to `backend`.
5. Let Vercel detect the FastAPI/Python project.
6. Do not set a frontend build command and do not deploy the repository root as a Next.js project.

The backend application is exported as `app` from `backend/app/main.py`, and `backend/requirements.txt` contains its Python dependencies.

### Add backend environment variables

In **Project Settings > Environment Variables**, add the following for Production. Paste values without surrounding quotes.

```text
APP_ENV=production
DATABASE_URL=PASTE_THE_TRANSACTION_POOLER_6543_URL_HERE
GROQ_API_KEY=PASTE_YOUR_GROQ_KEY_HERE
GROQ_MODEL=openai/gpt-oss-20b
JWT_SECRET=PASTE_A_RANDOM_SECRET_OF_AT_LEAST_32_BYTES_HERE
JWT_EXPIRY_HOURS=24
CORS_ORIGINS=https://temporary.invalid
FRONTEND_URL=https://temporary.invalid
PASSWORD_RESET_DELIVERY=disabled
```

Generate `JWT_SECRET` locally; do not reuse the database password or Groq key:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Important:

- Use the Supabase **Transaction mode** URL on port `6543` for `DATABASE_URL`.
- Include `?sslmode=require`.
- Do not add spaces around values.
- `JWT_SECRET` must remain stable. Changing it logs out every user.
- Start with password-reset delivery disabled. Configure SMTP later using the optional section below.

Select **Deploy**. When it completes, copy the production URL, for example:

```text
https://rxos-api.vercel.app
```

Do not add a trailing slash when using this as `NEXT_PUBLIC_API_URL`.

### Verify the backend

Open these URLs in a browser:

```text
https://YOUR-BACKEND.vercel.app/
https://YOUR-BACKEND.vercel.app/health/live
https://YOUR-BACKEND.vercel.app/health/ready
https://YOUR-BACKEND.vercel.app/docs
```

`/health/live` should return `{"status":"alive"}`. `/health/ready` should return status `ready` and migration `20260825_0002`.

If `/health/ready` returns `503`, inspect **Vercel > Project > Logs**. The usual causes are an incorrect pooler URL, incorrect password, missing `sslmode=require`, or migrations that were not applied.

### Vercel build troubleshooting

If an older deployment reports this error:

```text
No `project` table found in: /vercel/path0/backend/pyproject.toml
```

confirm Vercel is building a commit that contains the `[project]` section in `backend/pyproject.toml`, then select **Redeploy** with **Use existing Build Cache** turned off. The current repository declares its runtime dependencies in both `pyproject.toml` for Vercel/uv and `requirements.txt` for pip and Docker. Keep those lists synchronized when adding or removing a backend dependency.

## 5. Deploy the Next.js frontend to Netlify

1. In Netlify, select **Add new project > Import an existing project**.
2. Choose GitHub and select this repository.
3. Select the `recovery-hardening` branch.
4. Netlify will read the committed root-level `netlify.toml`, which defines:

```text
Base directory: frontend
Build command: npm run build
Publish directory: frontend/out
```

The dashboard can display `frontend/out` as a repository-relative resolved path. That is expected. The source value in `netlify.toml` is `out`, relative to the `frontend` base directory. The frontend uses Next.js static export, so the deployment does not require a Netlify server function or the OpenNext adapter.

5. Add this environment variable before the first production build:

```text
NEXT_PUBLIC_API_URL=https://YOUR-BACKEND.vercel.app
```

6. Select **Deploy**.
7. Copy the final Netlify production URL, for example:

```text
https://rxos.netlify.app
```

`NEXT_PUBLIC_API_URL` is included during the frontend build. If it changes, update the variable and trigger a new Netlify deployment.

## 6. Connect the frontend and backend

Return to the Vercel backend project and replace the two temporary values:

```text
CORS_ORIGINS=https://YOUR-SITE.netlify.app
FRONTEND_URL=https://YOUR-SITE.netlify.app
```

Use the exact Netlify origin: HTTPS, hostname, and no trailing slash or path. For multiple permanent origins, use a comma-separated list with no spaces:

```text
CORS_ORIGINS=https://rxos.netlify.app,https://app.example.com
```

After changing environment variables, redeploy the Vercel production deployment so the new values take effect.

Netlify deploy-preview URLs are different origins. The safest initial deployment is to test through the permanent `*.netlify.app` production URL rather than adding wildcard CORS access.

## 7. Production smoke test

Test in this order from the permanent Netlify URL:

1. Open the application and confirm there is no browser CORS error.
2. Create a test account and log in.
3. Log out and log back in.
4. Import `mock_inventory.csv` or create a small batch manually.
5. Verify the inventory dashboard and reorder suggestions.
6. Make a stock adjustment and confirm the audit ledger entry.
7. Create a supplier and purchase order.
8. Receive goods and confirm the stock quantity changes.
9. Test an AI query and inspect Vercel logs if Groq returns an error.
10. Confirm that password reset returns a controlled `503` configuration response while delivery is disabled.

Also recheck:

```text
https://YOUR-BACKEND.vercel.app/health/ready
```

### Replace an expired or invalid Groq key

Groq keys do not belong in GitHub, Netlify, or frontend variables. If either AI feature reports an authentication failure:

1. Open the Groq console and create a new API key.
2. Open the **backend** project in Vercel.
3. Go to **Settings > Environment Variables** and edit `GROQ_API_KEY` for Production.
4. Paste the new key without quotes or spaces and save it.
5. Redeploy the backend so the running function receives the new value.
6. Delete or revoke the old key in Groq after the new deployment works.
7. Test both **Conversational Database Explorer** and **AI Operations Briefing** again.

Never paste the key into a support message, Vercel build log, source file, or any variable beginning with `NEXT_PUBLIC_`. If the UI reports a quota/rate-limit or model-availability error instead, inspect **Vercel > Backend project > Logs** and the Groq console; rotating a valid key will not solve those cases.

`GROQ_MODEL` is optional because the backend defaults to `openai/gpt-oss-20b`, a production model available on Groq's Developer plan. Keeping it in Vercel makes future model changes possible without changing source code. Do not select a model marked **Enterprise** for a free Groq project, and avoid preview model IDs because they can disappear without notice.

## 8. Optional SMTP password-reset email

Leave `PASSWORD_RESET_DELIVERY=disabled` until a real SMTP provider and sender address are ready. Then add these Vercel variables:

```text
PASSWORD_RESET_DELIVERY=smtp
SMTP_HOST=YOUR_SMTP_HOST
SMTP_PORT=587
SMTP_USERNAME=YOUR_SMTP_USERNAME
SMTP_PASSWORD=YOUR_SMTP_PASSWORD
SMTP_FROM_EMAIL=YOUR_VERIFIED_SENDER
SMTP_USE_SSL=false
```

For a provider that requires implicit TLS on port `465`, set:

```text
SMTP_PORT=465
SMTP_USE_SSL=true
```

Redeploy Vercel and test password reset with a non-production account. Never expose SMTP credentials through `NEXT_PUBLIC_*` variables or Netlify frontend variables.

## 9. Updating the deployed application

After changes are committed and pushed to `recovery-hardening`:

- Vercel automatically rebuilds the backend when backend files change.
- Netlify automatically rebuilds the frontend when frontend files change.
- New Alembic migrations must be applied to Supabase before code that depends on them is released.

Apply future migrations with the Session pooler URL:

```powershell
cd D:\Pharmcay-ai-os\backend
.\.venv\Scripts\Activate.ps1
$env:DATABASE_URL='PASTE_THE_SESSION_POOLER_5432_URL_HERE'
python -m alembic -c alembic.ini upgrade head
Remove-Item Env:DATABASE_URL
```

For a schema-changing release, take a backup first, apply the migration, check `/health/ready`, and then promote or redeploy the application code.

## 10. Backup and free-tier limitations

Supabase Free does not provide automatic backups. Before an important migration or demo, create and verify a logical backup with a PostgreSQL client such as `pg_dump`. Store it somewhere private and encrypted.

Also remember:

- Supabase Free projects may pause after low activity; resume the project from Supabase before testing.
- A paused database makes `/health/ready` return `503` until it resumes.
- Vercel Python functions are serverless and can have cold starts and execution limits.
- Free hosting is not an uptime guarantee.
- Never store real patient, prescription, payment, or regulated health information in this free demo deployment.

## 11. Secret-safety checklist

Before every push, confirm:

- `.env`, `backend/.env`, and `frontend/.env.local` are not tracked;
- only `.env.example` templates contain placeholder values;
- Vercel holds backend secrets;
- Netlify contains only `NEXT_PUBLIC_API_URL` for this project;
- no browser-visible variable contains a database password, JWT secret, Groq key, Supabase service-role key, or SMTP password;
- logs and screenshots do not reveal connection strings or tokens.

Useful checks:

```powershell
git status --short
git ls-files | Select-String -Pattern '(^|/)(\.env|\.env\.local)$'
git grep -n -E 'gsk_[A-Za-z0-9]|postgres(ql)?://[^ ]+:[^ ]+@|SUPABASE_SERVICE_ROLE_KEY='
```

The last two commands should not reveal a tracked real secret. If a secret was ever committed, removing it from the latest file is not enough: rotate it immediately and then clean the Git history separately.

## Official platform references

- [FastAPI on Vercel](https://vercel.com/docs/frameworks/backend/fastapi)
- [Netlify monorepo configuration](https://docs.netlify.com/build/configure-builds/monorepos/)
- [Netlify Next.js support](https://docs.netlify.com/build/frameworks/framework-setup-guides/nextjs/overview/)
- [Supabase PostgreSQL connection modes](https://supabase.com/docs/guides/database/connecting-to-postgres)
- [Supabase pricing and Free limits](https://supabase.com/pricing)
- [Supabase Free project pausing](https://supabase.com/docs/guides/platform/free-project-pausing)
