# Free-hosting warm-up and session retries

## Repository inspection

- Frontend: React/TypeScript, TanStack Start/Router, Vite.
- Backend: FastAPI, `services/api/uranium/main.py`, module entry `uranium.main:app`.
- Supabase database: SQLAlchemy with Psycopg, configured in `services/api/uranium/config.py` and `db.py`. There is no Supabase JS database client or Supabase Auth migration in this change.
- Cookie-authenticated API helper: `src/features/api.ts`.
- Session check, sign-in and sign-out: `src/lib/backend-session.tsx`, using `/me` and `/auth/session` under `/api/v1`.
- Login page: `src/routes/login.tsx`.
- Initial browser warm-up: `src/routes/__root.tsx`.
- Hosted proxy: `vercel.json`. Development proxy: `vite.config.ts`.

## What changed

`GET /health` is public and returns HTTP 200 with `{ "ok": true, "db": true }` after `SELECT 1`. If the database query fails, it returns HTTP 200 with `{ "ok": true, "db": false }`. It does not reveal database details, change data or require a session. PostgreSQL connection/pool wait limits and a local statement timeout bound ordinary DB failures. Dead connections are checked on checkout using `pool_pre_ping`.

The existing `/api/v1/health` still reports database/migration readiness and can return 503. It was not weakened to always return 200.

CORS allows explicit configured origins with credentials, required methods and the CSRF header. Authentication, sample credentials, cookie flags, institution/assignment checks and CSRF logic are retained. CORS is not permission to read an institution's records.

`warmUp()` makes one non-blocking public GET when the browser app mounts. It omits cookies, catches errors, and cancels its own request after ten seconds. If a later session request encounters a gateway/network failure, it can initiate another deduplicated direct wake-up request. This is traffic triggered by opening/using the site, not an endless browser keepalive timer.

`fetchWithRetry(url, options, tries=6, delay=10000)` retries network errors and HTTP 502/503/504. A request has a ten-second timeout, waits ten seconds between attempts, and honors caller cancellation. There are at most six attempts; if every attempt stalls, the total budget can approach 110 seconds. Consequently the UI says a minute **or longer**, rather than promising an exact 60-second deadline.

HTTP 401/403, validation errors, rate limits and other application statuses are returned immediately, without retries. The helper is used only for `/me` and `/auth/session`, including sign-in and sign-out. Ordinary application submissions, uploads and report mutations are not automatically replayed. A lost response to a session mutation can still mean the server received that attempt; the feature is a bounded session retry, not a general exactly-once transaction mechanism.

During connection/retry work the login page announces its status, displays a small reduced-motion-aware spinner, disables sign-in, suppresses stale errors, and offers Try again after exhaustion. Try again rechecks the session/availability; it does not silently resubmit credentials.

## Vercel environment variables

Set these in the frontend Vercel project, for both Production and the Preview environments you use:

| Key                 | Value                                     |
| ------------------- | ----------------------------------------- |
| `VITE_API_URL`      | `https://uranium-verify-api.onrender.com` |
| `VITE_API_BASE_URL` | `/api/v1`                                 |

`VITE_API_URL` is the **direct backend origin used for public wake-up**. `VITE_API_BASE_URL` is the **authenticated request prefix** and deliberately remains relative, using the existing Vercel rewrite. Do not put the Render origin into `VITE_API_BASE_URL` for this cookie setup: `SameSite=Strict` and same-origin credential behavior are preserved. Browser-facing VITE_ values contain no secrets.

Trailing slashes are trimmed before joining paths. Do not append `/health` or `/api/v1` to `VITE_API_URL`.

Vite reads these values at build time: saving Vercel environment variables requires a new frontend deployment. Pushing a branch may create a Preview; merge/redeploy the production branch to change the public website.

If the direct origin is unset, warm-up falls back to same-origin `/health`, which is now proxied by Vercel/Vite. For the specific observed direct-versus-proxy recovery behavior, **set the direct Render origin explicitly**.

## Render environment variables and settings

Add:

```dotenv
CORS_ALLOWED_ORIGINS=https://uraniumverify.vercel.app,http://localhost:5174,http://127.0.0.1:5174,http://localhost:5184,http://127.0.0.1:5184
```

For a particular Vercel Preview URL, append its exact HTTPS origin to this comma-separated list when testing direct warm-up. No paths, quotes or wildcard origins. The code supplies the stable production origin and common local ports as defaults when this setting is absent.

Keep existing `DATABASE_URL`, `DATABASE_SCHEMA`, `APP_ENV`, `AUTH_ADAPTER`, `COOKIE_SECURE=true`, `STORAGE_BACKEND`, Supabase storage settings and other working server values. Do not share credentials or add them to Vercel's VITE_ variables.

The backend start command stays:

```bash
python -m uvicorn uranium.main:app --app-dir services/api --host 0.0.0.0 --port $PORT
```

Render currently follows `backend/supabase-setup`; confirm the deployed service receives this backend commit. Vercel Production follows `main`. Do not assume a push updates both production services at once.

Leave Render's existing readiness health-check path `/api/v1/health` unchanged unless you deliberately choose a different operational health policy. Use the new `/health` for the external pinger.

## Exact pinger URL

```text
https://uranium-verify-api.onrender.com/health
```

Method: GET. No credentials, cookies or custom headers are needed. A five-minute interval is the free monitoring option discussed earlier; check the monitoring provider's current free limits. Always-200 liveness does not certify database health: a more capable monitor can also inspect `db` if desired.

Opening health creates database activity; it is not a contractual guarantee that Supabase will never pause a free project, that Render will never evict/restart a service, or that uptime is unlimited. This change handles transient failures and direct warm-up; it cannot guarantee uninterrupted free hosting or repair a sustained process crash.

## Local development

Optional local frontend values:

```dotenv
VITE_API_URL=http://127.0.0.1:8014
VITE_API_BASE_URL=/api/v1
```

Keep local `COOKIE_SECURE=false` for HTTP development. Restart Vite after changing VITE_ values. Local `/api` and `/health` both have development proxies to port 8014.

## Verification before calling it fixed

1. Deploy the backend commit; direct `/health` must return JSON and a successful DB should give `db:true`.
2. Set the frontend environment values and deploy the frontend update.
3. Test incorrect credentials once: 401 must be shown immediately, without a retry loop.
4. Test valid sample institution/officer login, session persistence after refresh, sign-out and attachment access.
5. Let the free backend go idle without a pinger or manual Render visit. Open the main website first. Observe the direct `/health` request, any bounded session retries and the visible waiting state. Confirm sign-in recovers without opening the Render tab manually.
6. If errors persist, preserve Network logs and inspect Render runtime logs; do not label a sustained crash a normal cold start.

Local fake-timer tests simulate gateway/network failures, retry exhaustion, cancellation, unchanged POST methods, no retry on real auth errors, and a stalled request. Component tests exercise the waiting/error/retry interface. Isolated SQLite tests cover public health, database failure, retained strict readiness behavior and CORS. These are not a real idle-to-awake Render test; that remains a deployment acceptance check.

No worker was hosted, no monitoring account was created, and no credentials were changed. New report generation still needs the separately configured worker.

## Changed files

Application and configuration:

```text
.env.example
eslint.config.js
services/api/migrations/env.py
services/api/uranium/config.py
services/api/uranium/db.py
services/api/uranium/main.py
src/features/api.ts
src/lib/api-connection.ts
src/lib/backend-session.tsx
src/routes/__root.tsx
src/routes/login.tsx
vercel.json
vite.config.ts
```

Tests and deployment notes:

```text
src/lib/api-connection.test.ts
src/test/login-connection.test.tsx
tests/api/test_wake_health.py
COLD_START_SETUP.md
```

The unrelated existing README.md edits were left intact. The migration runner change only removes an unused import found by Ruff; it does not add or apply a database migration. ESLint now ignores the Python virtual environment and Python test/bytecode caches, preventing traversal of Windows-locked cache directories.

Observed local validation: 62 frontend tests passed; 33 backend foundation and health/CORS tests passed against isolated SQLite; TypeScript and the production frontend build passed; Ruff passed; ESLint reported zero errors and 24 pre-existing component Fast Refresh warnings. No cloud database mutation or live login test was performed for this patch. The idle-to-awake deployment check remains pending.
