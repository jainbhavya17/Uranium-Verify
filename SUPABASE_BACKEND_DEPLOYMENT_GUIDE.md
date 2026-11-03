# Uranium Verify: database, backend and deployment explained

**Written for:** someone learning these tools for the first time.  
**Recorded on:** 4 November 2026, India time.  
**Purpose:** explain what we configured, why we did it, how to operate it, and what to learn next.

This is a record of the evaluator prototype we set up together. Commands marked as initial setup are not daily maintenance commands. Read the explanation before running them against the shared database.

No private passwords, database credentials or Supabase secret keys are included. Replace placeholders privately on your own machine or in the hosting dashboard.

## Contents

1. [What is online now](#1-what-is-online-now)
2. [The pieces in simple language](#2-the-pieces-in-simple-language)
3. [How a request travels](#3-how-a-request-travels)
4. [The project folder](#4-the-project-folder)
5. [Supabase project and database connection](#5-supabase-project-and-database-connection)
6. [The private database schema](#6-the-private-database-schema)
7. [Python environment and migrations](#7-python-environment-and-migrations)
8. [Sample users and applications](#8-sample-users-and-applications)
9. [Private cloud document storage](#9-private-cloud-document-storage)
10. [Local testing](#10-local-testing)
11. [Git and GitHub](#11-git-and-github)
12. [Render backend deployment](#12-render-backend-deployment)
13. [Connecting Vercel to Render](#13-connecting-vercel-to-render)
14. [Checks we completed](#14-checks-we-completed)
15. [The worker and reports](#15-the-worker-and-reports)
16. [Favicon and link-preview metadata](#16-favicon-and-link-preview-metadata)
17. [Files changed and their responsibilities](#17-files-changed-and-their-responsibilities)
18. [Troubleshooting](#18-troubleshooting)
19. [Current limitations and later work](#19-current-limitations-and-later-work)
20. [Routine operation and future changes](#20-routine-operation-and-future-changes)
21. [Learning path and official resources](#21-learning-path-and-official-resources)

## 1. What is online now

The existing React website was already deployed. We connected the existing Python backend to a cloud database, moved its referenced document originals into private cloud storage, hosted the API, and connected the website to that API.

We did not rewrite the whole backend. The repository already contained FastAPI routes, SQLAlchemy models, Alembic migrations, application workflows and a worker. We reused them.

| Component                                     | Location                                                                      | Current situation                                                                    |
| --------------------------------------------- | ----------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| Public website                                | [uraniumverify.vercel.app](https://uraniumverify.vercel.app/)                 | Hosted on Vercel; live workflows were tested                                         |
| Python API                                    | [uranium-verify-api.onrender.com](https://uranium-verify-api.onrender.com/)   | Hosted on Render's Free web-service plan                                             |
| Application database                          | Supabase PostgreSQL                                                           | Existing migrations applied in `uranium_private`                                     |
| Document originals and generated report files | Supabase Storage                                                              | Private bucket named `uranium-documents`                                             |
| Code                                          | [jainbhavya17/Uranium-Verify](https://github.com/jainbhavya17/Uranium-Verify) | Changes pushed and merged through pull requests                                      |
| Worker                                        | Your Windows computer                                                         | Started manually when queued processing is needed; cloud worker hosting was deferred |
| Authentication                                | Existing Python demo adapter                                                  | Sample accounts; this is not Supabase Auth                                           |

**You can close VS Code.** Hosted login, application data, original attachments and existing cloud reports do not need your computer to stay on. New queued work needs an active worker. Free hosting availability and usage limits still apply; this is not a guarantee of uninterrupted service.

## 2. The pieces in simple language

Think of the application as an office:

| Term         | Office analogy                                                           | In this project                                                     |
| ------------ | ------------------------------------------------------------------------ | ------------------------------------------------------------------- |
| Frontend     | The counter and forms visitors see                                       | React/TypeScript pages hosted on Vercel                             |
| Backend/API  | Staff who validate a request and decide which records someone may access | Python/FastAPI on Render                                            |
| Database     | Organized registers of applications, users, findings and statuses        | Supabase PostgreSQL                                                 |
| File storage | The document archive                                                     | A private Supabase Storage bucket                                   |
| Worker       | A back-office employee handling queued tasks                             | A separate Python process for reports, processing and notifications |
| Queue        | A waiting list of tasks                                                  | Existing database-backed jobs; adding Redis was not required        |
| Git          | A history of code changes on your computer                               | Local commits and branches                                          |
| GitHub       | A shared, hosted copy of that code history                               | Your repository                                                     |
| Deployment   | Putting a version of the program on a hosted server                      | Vercel deployments and Render deployments                           |

Some more useful terms:

- **API endpoint:** a URL that performs one defined operation, such as `/api/v1/health`.
- **HTTP request/response:** the browser asks for something; the server returns data or an error.
- **JSON:** a structured data format used between the frontend and backend. It is useful for programs but often too technical for a user-facing report.
- **Schema:** a named group of database tables, like a folder inside a database. It is different from a SQLAlchemy data model, although both are sometimes called a schema.
- **Migration:** a versioned instruction for creating or changing database structure.
- **Seed data:** initial example records and users. Seeding does not mean migrating database structure.
- **Environment variable:** a named configuration value provided to a program, such as `DATABASE_URL`.
- **`.env`:** a local text file containing environment settings. Our code explicitly loads supported names from it.
- **Virtual environment (`.venv`):** a private set of Python packages for this project. It is not a virtual server.
- **Session cookie:** a value used by the browser to continue an authenticated session.
- **CSRF token:** an additional value required by the backend for authenticated changes. It helps prevent another site from making unwanted changes through a signed-in browser.
- **Hash:** a fingerprint of file contents. We used SHA-256 to check whether the transferred bytes matched recorded originals.
- **Cache:** a disposable working copy used for speed or compatibility. The cloud original is the durable copy.
- **Localhost / `127.0.0.1`:** your own computer. A localhost address is not an evaluator's public website.
- **Port:** a number identifying which local server to contact. The API used `8014`; the working frontend used `5184`.

## 3. How a request travels

```mermaid
flowchart LR
    Person[Institution or officer] --> Site[React website on Vercel]
    Site -->|Same-origin /api request| Rewrite[Vercel external rewrite]
    Rewrite --> API[FastAPI on Render]
    API -->|Users, roles, applications and jobs| DB[(Supabase PostgreSQL)]
    API -->|Authorized original file access| Files[Private Supabase Storage]
    Worker[Local Python worker] -->|Claim jobs and save results| DB
    Worker -->|Read originals and write reports| Files
```

If your Markdown viewer does not render Mermaid, read it as:

```text
Browser -> Vercel website -> Render API -> Supabase database / private files
Local worker -> same Supabase database / private files
```

### Example: opening an attachment

1. The officer signs in through the website.
2. The browser requests a permitted attachment through `/api/v1/...`.
3. Vercel forwards that request to the Render API.
4. The API checks the session, role and case access, including the existing preview restrictions.
5. The backend uses its private server credential to retrieve the object from Supabase Storage.
6. The permitted response is returned to the browser.

The browser does not receive the Supabase secret key. Keeping a bucket private is only part of the protection: the API must still enforce which logged-in user may access each document. The server secret is privileged.

### Example: requesting a report

1. An officer requests a report.
2. The API records a queued job.
3. An active worker picks up the job.
4. The worker generates the report and stores its file in private cloud storage.
5. The website displays the report's resulting state and permits the authorized download.

If the worker is off, steps 3–4 wait. A functioning API health page does not prove that a worker is running.

## 4. The project folder

We worked in:

```text
C:\Users\Nishit\Downloads\screenshot-to-spark-4072\uranium-verify-redesign
```

There is also a parent project folder and a separate motion-video project. Running commands from the wrong folder can start the wrong application or use the wrong configuration.

The correct backend-enabled folder contains `services`, `src`, `alembic.ini`, `.env.example` and `requirements.lock`.

Useful VS Code actions:

- `Ctrl+P`: find a file by path.
- `Ctrl+N`: create a blank file; use Save As to choose its actual location.
- `Ctrl+S`: save the current file.
- **Terminal -> New Terminal:** open a separate command prompt.
- `Ctrl+C` inside a server terminal: stop that process.
- A server terminal staying occupied is normal. It is waiting for requests, not necessarily stuck.

## 5. Supabase project and database connection

### 5.1 Project creation

You created/opened a Supabase project, chose a nearby available region, and saved its database password privately. The project dashboard is the control panel for the hosted database and storage.

The Supabase integration was installed during the conversation, but its database-management tools did not become usable in the chat at that stage. The actual project setup was therefore done by you in the dashboard and terminal. We did not rely on an assistant-side cloud connection to make the database changes.

### 5.2 Three different connection values

These are easy to confuse:

| Value                   | Typical shape                                       | Used for                                         |
| ----------------------- | --------------------------------------------------- | ------------------------------------------------ |
| Database connection URL | `postgresql+psycopg://.../postgres?sslmode=require` | Python/SQLAlchemy talking directly to PostgreSQL |
| Project/API URL         | `https://PROJECT_REF.supabase.co`                   | Storage API requests                             |
| Server secret API key   | Begins with `sb_secret_`                            | The backend accessing private Storage            |

A publishable key is designed for public client use and was not the key selected for our server storage adapter. A database password is not an API key. Supabase Auth was not introduced merely by adding a Supabase database.

### 5.3 Find the Session pooler URL

In the project dashboard, you opened **Connect**, then the connection-string area. The dashboard you saw used tabs including **Framework**, **Server**, **Direct**, **ORM** and **MCP**. Under the database connection options you selected **Session pooler**.

We copied the actual username and host from your dashboard instead of guessing them. Session pooler addresses typically use a pooler host and port `5432`; use the exact values supplied for your project.

We changed the driver prefix from `postgresql://` to `postgresql+psycopg://`, because the project uses SQLAlchemy with Psycopg.

### 5.4 Encode special characters in the database password

Your password contained special characters. Characters such as `@` can have a structural meaning inside a URL, so we encoded the password before putting it into that URL.

You ran:

```powershell
python -c "from getpass import getpass; from urllib.parse import quote; print(quote(getpass('Database password (hidden): '), safe=''))"
```

The prompt hides your typing. The printed encoded value is still sensitive: encoding is not encryption. Paste the encoded value only into the password portion of the URL and keep your original password separately. Do not encode the whole connection URL or encode an already encoded password again.

### 5.5 Configure the local `.env`

We used `.env` beside `.env.example`, rather than editing the example file with private values.

The final database settings have this form:

```dotenv
DATABASE_URL=postgresql+psycopg://postgres.PROJECT_REF:ENCODED_PASSWORD@YOUR_POOLER_HOST:5432/postgres?sslmode=require
DATABASE_SCHEMA=uranium_private
```

`sslmode=require` requires an encrypted database connection. Certificate validation and least-privilege runtime database credentials are additional production hardening work; we did not claim a full production security audit.

Do not put the connection string in a variable beginning with `VITE_`, a frontend source file, a screenshot or a Git commit.

The custom `.env` loader trims surrounding whitespace but does not remove quotes from values. We entered these values without surrounding quotes. Existing process environment variables take precedence over `.env`; restart a running process after configuration changes.

Official reference: [connecting to Supabase PostgreSQL](https://supabase.com/docs/guides/database/connecting-to-postgres).

## 6. The private database schema

### 6.1 Check for existing application tables

Before creating anything, we ran a read-only table listing in Supabase's SQL Editor. It returned no application tables. This avoided assuming that a new project was empty or overwriting existing application structure.

A focused check for the two relevant schemas is:

```sql
SELECT schemaname, tablename
FROM pg_catalog.pg_tables
WHERE schemaname IN ('public', 'uranium_private')
ORDER BY schemaname, tablename;
```

### 6.2 Create a private schema

We ran this once in SQL Editor:

```sql
CREATE SCHEMA IF NOT EXISTS uranium_private;

REVOKE ALL ON SCHEMA uranium_private
FROM PUBLIC, anon, authenticated;
```

Here, `PUBLIC` is PostgreSQL's group representing all roles; it is different from the schema named `public`.

The design is that the Python API checks access and queries the private application tables. Browser users do not directly query those tables through Supabase's Data API. We did not expose this private schema through the Data API or add broad browser access policies.

This is not a claim that we implemented Row Level Security policies on every existing application table. We used a private schema with revoked direct schema access and kept the existing backend authorization model. Do not grant browser roles access or expose the schema without a separate policy review.

### 6.3 Why the first schema-selection attempt failed

We initially added a connection URL option:

```text
&options=-csearch_path%3Duranium_private%2Cpublic
```

The test still reported `Active schema: public`. A diagnostic confirmed:

```text
Terminal DATABASE_URL override: False
Schema option: -csearch_path=uranium_private,public
Search path: "$user", public, extensions
Private schema exists: True
Explicit schema test: uranium_private
```

So the setting was loaded, the schema existed, and an explicit SQL command worked, but the startup URL option was not applied in this connection path. We removed that suffix rather than pretending it worked.

### 6.4 The actual fix

We added `DATABASE_SCHEMA` to the configuration loader and updated `services/api/uranium/db.py`:

1. Create the SQLAlchemy engine.
2. On each new PostgreSQL connection, read the configured schema name.
3. Validate it as an identifier to avoid interpolating arbitrary SQL.
4. Temporarily use DBAPI autocommit to run:

```sql
SET search_path TO "uranium_private", public;
```

5. Restore the connection's earlier autocommit state.

The `search_path` is PostgreSQL's ordered list of schemas to search when code mentions an unqualified table name such as `users`. With `uranium_private` first, the application's unqualified tables are created and found there.

SQLite handling was retained. If a different environment does not set `DATABASE_SCHEMA`, the factory does not force that private schema.

In `services/api/migrations/env.py`, we changed the migration engine to use `make_engine(url)`, so migrations and the API use the same schema-selection behavior. This avoids creating tables in one schema and querying another.

The shared connection test then printed:

```text
Active schema: uranium_private
```

### 6.5 Check direct access restrictions

We ran:

```sql
SELECT
  has_schema_privilege('anon', 'uranium_private', 'USAGE')
    AS anonymous_access,
  has_schema_privilege('authenticated', 'uranium_private', 'USAGE')
    AS direct_authenticated_access;
```

Both returned `false`. That is the intended result for this backend-mediated design. It does not remove the privileged backend's responsibility to enforce roles, institution membership and assignments.

## 7. Python environment and migrations

These are initial setup steps, not commands to repeat every time you need a report.

### 7.1 Verify Python

```powershell
python --version
```

Your interpreter was Python `3.14.3`.

### 7.2 Create a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe --version
```

We used the full interpreter path in commands. This works without activating the environment and avoids PowerShell activation-policy issues.

### 7.3 Install the existing locked dependencies

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -c "import sqlalchemy, psycopg; print('Database dependencies ready')"
```

The lock lists package versions so a fresh deployment uses the expected versions. Installation is different from running the API.

### 7.4 Read-only connection check

We loaded `Settings().database_url` and executed `SELECT 1`, then checked `SELECT current_schema()` using `make_engine`. We verified the actual private schema before allowing migrations.

A reusable current check, from the project root:

```powershell
@'
import sys
sys.path.insert(0, 'services/api')
from sqlalchemy import text
from uranium.config import Settings
from uranium.db import make_engine

engine = None
try:
    engine = make_engine(Settings().database_url)
    with engine.connect() as connection:
        print('Active schema:', connection.execute(text('SELECT current_schema()')).scalar())
except Exception as error:
    print('Connection check failed:', type(error).__name__)
finally:
    if engine is not None:
        engine.dispose()
'@ | .\.venv\Scripts\python.exe -
```

It does not print the connection string or password.

### 7.5 Apply migrations

```powershell
$env:PYTHONPATH = 'services/api'
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic current
```

The result was:

```text
0012_restored_portal (head)
```

`head` means the latest migration revision in that checkout. It does not mean the application is fully production-ready. Check migration changes before applying future updates; do not use database reset/drop commands to fix an ordinary deployment issue.

## 8. Sample users and applications

### 8.1 Initial seed configuration

We set a private `DEMO_PASSWORD` with at least 16 characters in `.env`. It was a test-user setup value, separate from the database password.

We ran:

```powershell
.\scripts\setup.ps1 -Python '.venv/Scripts/python.exe'
```

The existing setup script:

1. Preserves an existing `.env`.
2. Applies database migrations.
3. Creates the initial synthetic fixtures.
4. Creates additional review/evidence examples.
5. Seeds portal notices/content.
6. Configures the three advertised sample accounts.
7. Restores the earlier institution/application sample pack.

The line `Existing .env preserved` was the first setup message, not proof that every stage had finished. The same applied to `Synthetic fixture pack ready`: it referred to one stage.

### 8.2 The immutable-file conflict and its fix

The final restoration stage stopped with:

```text
ValueError: Immutable storage object conflict
Institution and application examples failed
```

An existing opaque file key pointed to different bytes than the new generated PDF. The storage layer deliberately refuses to overwrite original evidence. We kept that protection.

In `services/api/uranium/seed_restored_portal.py`, we changed two sample file-key calculations:

```python
# Original sample documents: old form
key = hashlib.sha256(("portal-original:" + case.id + kind).encode()).hexdigest()

# Response document: old form
key = hashlib.sha256(b"restored-financial-response").hexdigest()

# New form at both locations
key = hashlib.sha256(content).hexdigest()
```

The new key is derived from the actual bytes. Identical bytes produce the same key; different bytes receive a different key. This did not require deleting old originals or weakening `write_once`.

We reran only the failed stage:

```powershell
.\.venv\Scripts\python.exe scripts/seed-restored-portal.py
```

It returned:

```text
{'applications': 7, 'institution_id': 'INS-1-4412'}
```

This confirmed restoration of the seven sample cases. These were examples, not imported official approvals.

### 8.3 Public demonstration accounts

These credentials are deliberately advertised by the sample-login interface, not private production credentials:

| Role          | Email                         | Public sample password |
| ------------- | ----------------------------- | ---------------------- |
| Institution   | `admin.a@demo.uranium.test`   | `Uranium@2026!`        |
| Officer       | `officer.a@demo.uranium.test` | `Uranium@2026!`        |
| Administrator | `platform@demo.uranium.test`  | `Uranium@2026!`        |

Clicking a sample account fills the form; clicking Sign in submits it. This is existing Python demo authentication backed by stored password hashes and sessions. It is not Supabase Auth and is not intended for real institutions' confidential submissions.

## 9. Private cloud document storage

### 9.1 Why the database was not enough

Database records contained document references, but the actual PDFs were initially in `var/private` on your computer. Hosting those references alone would leave the hosted API unable to open the files.

Render's free web service does not provide a persistent disk. We selected Supabase Storage for the durable originals instead of relying on that service's local filesystem. See [Render Free limitations](https://render.com/docs/free).

### 9.2 Create the private bucket

In Supabase:

1. Open **Storage**.
2. Choose **New bucket**.
3. Name it `uranium-documents`.
4. Keep **Public bucket OFF**.
5. Create it.

We did not add an anonymous read policy or make files public just to make previews work. [Supabase private-bucket behavior](https://supabase.com/docs/guides/storage/buckets/fundamentals).

### 9.3 Obtain server configuration

We copied the HTTPS Project URL from the dashboard's framework example. A line such as `NEXT_PUBLIC_SUPABASE_URL=https://...` was only a place to find the value. We copied the HTTPS value, not the Next.js variable name and not a PostgreSQL URL.

Under **Project Settings -> API Keys -> Secret keys**, we used a server secret beginning `sb_secret_`, named for the backend. This secret belongs only in local private configuration and Render's server environment. It is not a publishable key and must not be bundled into React. [Supabase API key guidance](https://supabase.com/docs/guides/getting-started/api-keys).

### 9.4 Final storage environment settings

We added these in both the private local `.env` and Render:

```dotenv
STORAGE_BACKEND=supabase
SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
SUPABASE_SECRET_KEY=YOUR_ACTUAL_SB_SECRET_KEY
SUPABASE_STORAGE_BUCKET=uranium-documents
```

The values above are placeholders. `STORAGE_BACKEND` chooses the adapter. `STORAGE_ROOT` remains the local private working-directory location; it is no longer the only source of cloud originals.

### 9.5 Install the adapter

The prepared installer was:

```powershell
.\.venv\Scripts\python.exe artifacts/supabase-storage-setup/install_storage.py
```

It backed up existing code under ignored `var/storage-code-backups`, updated the API and worker to use a storage factory, added the storage variable names to the loader, installed `supabase_storage.py`, and installed the transfer script.

The adapter uses the already installed/pinned HTTPX library for Storage API requests. We did not install a new Supabase Python SDK just to perform file operations.

The installer was a local preparation tool. It was not one of the files required by the deployed API; the resulting source files were what we committed.

### 9.6 What the adapter does

- Validates the Supabase project URL, server-key prefix, bucket name and object-key shape.
- Checks that the configured bucket exists and is private.
- Sends the server key in the request's `apikey` header.
- Reads originals through the authenticated Storage endpoint.
- Uploads with `x-upsert: false` to avoid silently replacing an existing original.
- Treats a duplicate upload as success only when the existing bytes match.
- Preserves the API's existing authorization and quarantine checks.
- Downloads private working copies for existing PDF/OCR functions that require a filesystem path.
- Uses a separate `supabase-cache` directory, preventing old local originals from masking a missing cloud object during transfer.
- Limits each object to 32 MiB and the local working-copy cache to 512 MiB.

The cache is disposable; the bucket is durable. This adapter does not provide automatic cache eviction. If the budget fills, stop processing and manage disposable cached copies carefully; do not delete cloud originals or the original local archive as a shortcut.

### 9.7 Tests before real credentials

Eleven offline tests passed for the adapter and installer. They covered private-bucket enforcement, repeated uploads, conflicting bytes, invalid keys, download paths, missing objects, redirects, sanitized network errors, limits, backups and repeatable installation. Synthetic HTTP responses were used, so those tests alone did not prove a real Supabase connection.

### 9.8 Transfer existing originals

With the local API stopped, we ran:

```powershell
.\.venv\Scripts\python.exe scripts/transfer-to-supabase.py
```

The script reads database-referenced document/report keys, validates local hashes, uploads without overwriting conflicting objects, downloads the cloud bytes and checks their hashes again. It preserves database references and local originals.

The first run stopped because the supplied value did not have the required server-secret prefix. After correcting the secret value privately, it completed:

```text
Transfer complete: 55 originals verified. Local files and database unchanged.
```

The count was the observed number of referenced originals at that moment. It is not a permanent quota or expected count for every later database.

This transfer command is not a general cloud-to-cloud backup system. If the local machine no longer contains every DB-referenced original, do not rerun it blindly; it deliberately stops when originals are missing or inconsistent.

## 10. Local testing

### 10.1 Start the API

From the correct project folder:

```powershell
.\.venv\Scripts\python.exe -m uvicorn uranium.main:app --app-dir services/api --host 127.0.0.1 --port 8014
```

Expected startup lines include `Application startup complete` and `Uvicorn running on http://127.0.0.1:8014`.

Open [the local API health endpoint](http://127.0.0.1:8014/api/v1/health). After cloud storage was configured, it reported:

```json
{
  "data": {
    "status": "ok",
    "database": "ready",
    "storage": "private-supabase",
    "mode": "DEMO"
  }
}
```

The complete response also includes request metadata and `error`. IDs and timestamps naturally change.

### 10.2 Start the frontend in a different terminal

We initially used port `5174`, but a 404 was shown. We moved to a fresh strict port and the login page loaded correctly. The exact cause of the earlier 404 was not proven; we did not claim the route itself was missing.

```powershell
npm run dev -- --port 5184 --host 127.0.0.1 --strictPort
```

Open [the local login page](http://127.0.0.1:5184/login).

The existing Vite proxy forwards local `/api` requests to `127.0.0.1:8014`. That proxy is for development; it is not automatically a Vercel production proxy.

### 10.3 Local checks completed

You confirmed institution login, visibility of `APP-01482` and `APP-01377`, officer case access, document lists and attachment previews. After installing cloud storage, the health endpoint reported `private-supabase` and an attachment opened.

The **Review document** button appeared unresponsive because it added a review form below the entire table without scrolling to it. You found the form by scrolling. We identified that usability issue but did not implement a modal or automatic scrolling as part of this session.

## 11. Git and GitHub

### 11.1 Check the repository and secret exclusion

```powershell
git status --short
git check-ignore .env
git remote -v
```

Your remote pointed to `https://github.com/jainbhavya17/Uranium-Verify`, and `.env` was ignored. Ignoring a file prevents new untracked copies from being added normally; if a secret file were already tracked, ignoring it alone would not erase its history. We did not commit private configuration in these steps.

### 11.2 Work on a separate branch

We created:

```powershell
git switch -c backend/supabase-setup
```

A branch lets you prepare changes before updating the live branch. Do not rerun that creation command if the branch already exists.

We staged specific source files rather than `git add .`, so unrelated artifacts and private working files were not swept into the commit.

### 11.3 Check, commit and push

Typical sequence used:

```powershell
git add PATH_TO_CHANGED_SOURCE_FILE
git diff --cached --check
git commit -m "Describe the change clearly"
git push origin backend/supabase-setup
```

The first push used `git push -u origin backend/supabase-setup` to set the upstream tracking branch.

`git diff --cached --check` detects whitespace problems. It is not a substitute for program tests.

Windows warnings saying LF will become CRLF describe line-ending normalization. They were warnings, not failed commits.

### 11.4 Changes recorded in this session

| Commit    | Change                                                            |
| --------- | ----------------------------------------------------------------- |
| `a0dc5b5` | Configure private schema and content-derived sample document keys |
| `bef97ea` | Add private Supabase Storage and verified transfer script         |
| `72bfa19` | Mark `win32_setctime` as Windows-only                             |
| `030590d` | Route Vercel API requests to Render                               |
| `397f096` | Use the coral-square favicon                                      |

The first integration pull request was merged with a merge commit. Vercel showed the resulting `main` production deployment Ready. The favicon update was also merged and you confirmed its appearance after caching caught up. Local commit history can remain on the feature branch until you fetch/synchronize it; that does not mean the GitHub merge failed.

We avoided force pushes and rewriting published history, which matters for this Lovable-connected repository.

## 12. Render backend deployment

### 12.1 Create the web service

In Render, you chose **New -> Web Service**, connected GitHub, selected `jainbhavya17/Uranium-Verify`, and configured:

| Field             | Value used                                                      |
| ----------------- | --------------------------------------------------------------- |
| Name              | `uranium-verify-api`                                            |
| Branch            | `backend/supabase-setup`                                        |
| Runtime           | Python 3                                                        |
| Region            | Nearby available region; Singapore was the suggested choice     |
| Root Directory    | Blank, because the repository root contains the dependency lock |
| Build Command     | `pip install -r requirements.lock`                              |
| Start Command     | See below                                                       |
| Health Check Path | `/api/v1/health`                                                |
| Compute           | Free web service                                                |

Start command, entered into Render rather than PowerShell:

```bash
python -m uvicorn uranium.main:app --app-dir services/api --host 0.0.0.0 --port $PORT
```

`0.0.0.0` lets the hosted server accept platform-routed traffic. `$PORT` is supplied by Render. Using only `127.0.0.1` on the hosted service would make it listen only internally.

### 12.2 Server environment variables

| Key                       | Configured value / purpose                                 |
| ------------------------- | ---------------------------------------------------------- |
| `PYTHON_VERSION`          | `3.14.3`, matching the verified local interpreter          |
| `DATABASE_URL`            | Private Psycopg Session pooler URL with `?sslmode=require` |
| `DATABASE_SCHEMA`         | `uranium_private`                                          |
| `APP_ENV`                 | `development`                                              |
| `AUTH_ADAPTER`            | `demo`                                                     |
| `COOKIE_SECURE`           | `true` for HTTPS-hosted cookies                            |
| `LOCAL_RECOVERY_PREVIEW`  | `false`                                                    |
| `MALWARE_SCANNER`         | `unavailable`                                              |
| `RAG_EMBEDDINGS_ENABLED`  | `false`                                                    |
| `STORAGE_BACKEND`         | `supabase`                                                 |
| `SUPABASE_URL`            | Your project HTTPS URL                                     |
| `SUPABASE_SECRET_KEY`     | Private server secret                                      |
| `SUPABASE_STORAGE_BUCKET` | `uranium-documents`                                        |

Render does not receive your ignored local `.env` through Git. These settings were entered privately in the dashboard.

`APP_ENV=development` and `AUTH_ADAPTER=demo` were intentional because the existing application rejects production mode with its demo identity adapter. We did not bypass that guard or replace the identity provider. A publicly hosted evaluator demo is not the same as a production-authenticated government system.

`MALWARE_SCANNER=unavailable` means new uploaded documents are retained in quarantine. It does not report a successful virus scan. Disabling embeddings avoids introducing an extra model dependency for this demonstration.

For local HTTP development, leave `COOKIE_SECURE=false` in your local `.env`; use `true` on HTTPS Render. These are separate configuration environments.

### 12.3 Windows dependency marker

In `requirements.lock`, we changed:

```text
win32_setctime==1.2.1
```

to:

```text
win32_setctime==1.2.1; sys_platform == "win32"
```

This lets the Linux deployment skip a Windows-specific helper while retaining it on Windows. It was a portability adjustment; it was not evidence that every package had been retested on every platform.

### 12.4 Deploy and verify

You clicked **Deploy Web Service**, waited for the service, and checked:

[https://uranium-verify-api.onrender.com/api/v1/health](https://uranium-verify-api.onrender.com/api/v1/health)

The response showed `status: ok`, `database: ready`, `storage: private-supabase`, `mode: DEMO`.

The API root `/` need not be a frontend page. Use the known health path when checking the API.

Render still follows the feature branch configured for this service. Changing the service to follow `main` later should be a deliberate dashboard change after verifying that main contains the same backend code. Do not delete the configured deployment branch without deciding how Render will receive updates.

References: [FastAPI on Render](https://render.com/docs/deploy-fastapi), [Python version configuration](https://render.com/docs/python-version), [free-service limits](https://render.com/docs/free).

## 13. Connecting Vercel to Render

### 13.1 Why a rewrite was needed

The React API helper calls URLs beginning `/api/v1` on the current website and uses same-origin credentials. The backend already uses session cookies and CSRF checks.

We kept this request pattern. Instead of making the browser call a different domain directly, Vercel forwards the API traffic to Render. We did not solve it by exposing server secrets in browser environment variables or turning off CSRF.

### 13.2 The configuration file

We created `vercel.json` beside `package.json`:

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "rewrites": [
    {
      "source": "/api/:path*",
      "destination": "https://uranium-verify-api.onrender.com/api/:path*"
    }
  ]
}
```

`:path*` keeps everything after `/api/`, including the `v1` portion. For example, the website's `/api/v1/health` is forwarded to Render's `/api/v1/health`.

A rewrite forwards the request without changing the browser's visible URL. A redirect tells the browser to navigate elsewhere. We needed a rewrite. [Vercel's rewrite documentation](https://vercel.com/docs/routing/rewrites).

### 13.3 Preview first

After committing and pushing the file, Vercel built a preview for `backend/supabase-setup`. You opened its health endpoint and verified the cloud response. You then confirmed institution login, application loading, session persistence after refresh, officer access and attachments on that preview.

Preview URLs are temporary deployment-specific URLs. The stable public address for evaluators is `https://uraniumverify.vercel.app/`.

### 13.4 Publish through a pull request

On GitHub, we selected:

```text
Base: main
Compare: backend/supabase-setup
```

You created a pull request describing the changes and verified scope, checked for conflicts/check failures, selected **Create a merge commit**, and confirmed the merge.

Vercel's production deployment from `main` became Ready. You tested the live `/api/v1/health` endpoint and repeated login/session/attachment checks on the actual evaluator URL.

Do not mistake a Ready frontend build for a verified database or complete worker deployment. The browser checks were a separate important step.

## 14. Checks we completed

These results come from terminal output and the browser outcomes you confirmed during setup, plus the adapter's offline test run. They are not a new independent audit of the entire website.

| Check                                          | Observed result                                                            |
| ---------------------------------------------- | -------------------------------------------------------------------------- |
| Python version                                 | `3.14.3`                                                                   |
| Required database imports                      | SQLAlchemy and Psycopg available                                           |
| Database connectivity                          | Successful                                                                 |
| Private schema selection                       | `uranium_private`                                                          |
| Current migration                              | `0012_restored_portal (head)`                                              |
| `anon` / `authenticated` schema usage          | Both false                                                                 |
| Restored application sample pack               | Seven cases                                                                |
| Storage adapter and installer offline checks   | Eleven passed                                                              |
| Real private-file transfer                     | 55 originals uploaded and round-trip verified                              |
| Render health                                  | Database ready; private Supabase storage                                   |
| Vercel preview API forwarding                  | Successful                                                                 |
| Preview login, refresh and attachment access   | Confirmed working                                                          |
| Live-site login, refresh and attachment access | Confirmed working                                                          |
| Local worker with live site                    | Started; report became downloadable                                        |
| Report readability                             | You identified vague technical headings and raw JSON; improvement deferred |
| Favicon                                        | You confirmed the new two-square icon appeared                             |

## 15. The worker and reports

### 15.1 Why there is another process

The API handles short browser requests. The worker checks job queues and performs longer processing separately, so an officer does not have to keep an HTTP request open while a report is built.

The existing worker can select document, report and notification queues. Notifications handled by this worker are not proof that an external email/SMS provider has been configured.

### 15.2 Start it whenever needed

You do not need to start the local frontend or local API just to process jobs from the hosted website. The worker reads your private local `.env` and connects directly to the same cloud database and bucket.

Open PowerShell or a VS Code terminal:

```powershell
Set-Location -LiteralPath 'C:\Users\Nishit\Downloads\screenshot-to-spark-4072\uranium-verify-redesign'
.\.venv\Scripts\python.exe scripts/run-worker.py
```

Keep the computer awake, online, and the terminal process running. A quiet terminal can be normal when no jobs are available. Absence of output alone is not a complete health check; request a report and verify its result.

To process only report jobs while presenting:

```powershell
.\.venv\Scripts\python.exe scripts/run-worker.py --queue reports
```

Choose either the full worker or the reports-only worker for a simple demonstration, rather than starting multiple copies without a reason. `--once` performs one polling cycle; it does not necessarily drain a whole queue.

Press `Ctrl+C` to stop the worker. Stopping a worker is different from deleting jobs. If a job was in flight, recovery depends on the existing job lifecycle; inspect the status rather than repeatedly clicking Generate.

### 15.3 What closing your computer changes

| Action                                      | Computer/VS Code off                                                |
| ------------------------------------------- | ------------------------------------------------------------------- |
| Visit the website                           | Hosted services remain responsible for availability                 |
| Sign in and load stored applications        | Works through hosted API/database when those services are available |
| Open an existing permitted cloud attachment | Works through hosted API/storage                                    |
| Download an existing ready cloud report     | Works through hosted API/storage                                    |
| Generate a newly queued report              | Waits for a worker                                                  |
| Run queued document analysis                | Waits for a worker and required processing tools                    |

For an online evaluator visiting at an unknown time, a locally run worker cannot guarantee immediate new report generation. We discussed hosting it, then you explicitly deferred that work. A Render Background Worker was not created. Free Render web services also have idle/cold-start and usage limitations.

Reference: [Render background workers](https://render.com/docs/background-workers). Check the current plan display before purchasing hosting; no paid worker plan was authorized or provisioned in this setup.

### 15.4 Report-generation check

With the local worker active, you signed in as Officer on the live site, opened `APP-01482`, requested a review report and downloaded the PDF. This demonstrated job processing and file delivery.

The PDF included raw requested-value dictionaries, internal IDs and technical headings. You asked to improve that later. A downloadable PDF is not proof that its presentation is acceptable for an evaluator.

Recommended later report structure: application summary, institution details, documents reviewed, findings with sources, clarification responses, remaining actions, officer remarks and audit summary. Internal IDs should be reserved for useful reference details rather than dumped as JSON.

## 16. Favicon and link-preview metadata

### 16.1 Favicon

The old tab icon was the inherited builder icon. We created `public/favicon.svg` using the existing brand mark:

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect x="8" y="32" width="24" height="24" fill="#fc584d"/>
  <rect x="32" y="8" width="24" height="24" fill="#fc584d"/>
</svg>
```

In `src/routes/__root.tsx`, we changed the icon reference to:

```tsx
{ rel: "icon", href: "/favicon.svg?v=2", type: "image/svg+xml" },
```

`?v=2` is a URL version label that helps refresh a cached icon. The physical filename remains `favicon.svg`, not `favicon.svg?v=2`.

You committed the two files, pushed the feature branch, opened another pull request into `main`, merged it, waited for Vercel and eventually confirmed the new icon appeared. This was a cache delay, not a reason to repeatedly rewrite the file.

### 16.2 Repeated title and vague share description

You later reported a preview reading `Uranium Verify | URANIUM VERIFY` with a vague description. The SEO helper appended the brand to a homepage title that was already the brand, and its Open Graph title differed from the browser title.

Prepared locally with this guide:

**Homepage title:**

```text
Uranium Verify | AICTE Application Review
```

**Description:**

```text
An independent prototype for preparing AICTE applications, reviewing supporting documents, resolving queries and tracking application progress.
```

The shared helper now avoids repeating the homepage brand, keeps other page titles as `Page name | Uranium Verify`, and supplies consistent browser, Open Graph and Twitter title/description values. Root fallback metadata and homepage metadata use shared constants.

Files: `src/lib/seo.ts`, `src/routes/index.tsx`, `src/routes/__root.tsx`.

**Publication status:** these metadata corrections are local changes prepared in this documentation turn. They still need committing, pushing, preview verification and merging before the live preview changes. Previously shared messages may retain their original cached card; updating HTML does not edit those messages retroactively.

## 17. Files changed and their responsibilities

| File                                           | What it does / what changed                                                        |
| ---------------------------------------------- | ---------------------------------------------------------------------------------- |
| `.env`                                         | Private local database/storage/demo configuration; excluded from Git               |
| `services/api/uranium/config.py`               | Loads supported private setting names, including schema and storage configuration  |
| `services/api/uranium/db.py`                   | Shared engine creation, explicit PostgreSQL schema selection, SQLite compatibility |
| `services/api/migrations/env.py`               | Uses the shared engine factory so migrations target the same schema                |
| `services/api/uranium/seed_restored_portal.py` | Uses content-derived keys at the two conflicting sample PDF locations              |
| `services/api/uranium/supabase_storage.py`     | New private cloud storage adapter and factory                                      |
| `services/api/uranium/main.py`                 | API uses the storage factory; health identifies configured cloud storage           |
| `services/api/uranium/worker.py`               | Worker uses the same selected cloud storage adapter                                |
| `scripts/transfer-to-supabase.py`              | Verified transfer of existing referenced local originals                           |
| `requirements.lock`                            | Windows-specific environment marker for `win32_setctime`                           |
| `vercel.json`                                  | Same-origin frontend API proxy to Render                                           |
| `public/favicon.svg`                           | New two-square brand favicon                                                       |
| `src/routes/__root.tsx`                        | Favicon reference; later shared fallback title/description                         |
| `src/lib/seo.ts`                               | Later corrected reusable page and social-preview metadata                          |
| `src/routes/index.tsx`                         | Later uses the corrected shared homepage description                               |
| `SUPABASE_BACKEND_DEPLOYMENT_GUIDE.md`         | This guide                                                                         |

Local helper artifacts also include `artifacts/seed_restored_portal_fixed.py` and `artifacts/supabase-storage-setup/`. Those helped prepare/test/install the changes; do not assume all unrelated contents of `artifacts/` should be committed.

Existing migrations, authorization logic, application routes, worker queue code and report generation were reused rather than all being newly implemented in this cloud setup.

## 18. Troubleshooting

| Symptom                                           | Meaning / next action                                                                                     |
| ------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| `Test-Path .venv/Scripts/python.exe` prints False | Create `.venv` in the correct project folder                                                              |
| Python modules not found                          | Use the project's `.venv` interpreter; check lock installation                                            |
| Active schema is `public`                         | Check `DATABASE_SCHEMA`, the loader and use of shared `make_engine`; do not migrate into the wrong schema |
| Database connection fails                         | Check copied pooler host/username, password encoding, SSL and project availability privately              |
| Immutable storage conflict                        | Existing key has different bytes; preserve originals and inspect the key-generation source                |
| Server-secret-key error                           | Check the actual `sb_secret_` value, no surrounding quotes, and no process environment override           |
| New `.env` setting has no effect                  | Save the file and restart the relevant API/worker process; explicit process variables override the file   |
| `Uvicorn running...` and no prompt                | Expected: the API is serving requests; open another terminal for another command                          |
| `/favicon.ico` 404 in local API logs              | Browser asked the API for an icon; not evidence that the health endpoint failed                           |
| Login page 404 on local port                      | Check the exact URL, project directory and Vite output; use the known working strict port `5184`          |
| Review document seems inactive                    | Scroll below the supporting-documents table to its review form                                            |
| LF/CRLF Git warning                               | Normal Windows line-ending notice; inspect for a real error separately                                    |
| Preview works but main site does not              | Check whether the change was merged and the production deployment is Ready                                |
| Old favicon/title persists                        | Check deployed asset/HTML, then browser/social-card cache; do not assume a local edit is live             |
| Render health works but Vercel health fails       | Inspect `vercel.json`, the deployed branch and actual proxy destination                                   |
| New report remains queued                         | Start/check the worker and the same cloud DB/storage configuration                                        |
| Worker prints `WORKER_QUEUE_FAILURE`              | Check the error class and job status; do not paste credentials or blindly delete jobs                     |
| New upload stays quarantined                      | Expected with `MALWARE_SCANNER=unavailable`; a running worker does not constitute a scan                  |
| Cloud working-copy cache full                     | Stop processes and manage disposable `supabase-cache` files carefully; originals remain in cloud storage  |

Error messages can contain sensitive values depending on the library. Before sharing terminal output, remove database URLs, passwords, tokens and keys.

## 19. Current limitations and later work

1. **No hosted worker.** New queued jobs are dependent on your local worker until that separate deployment is done.
2. **Demo identity adapter.** We did not migrate to Supabase Auth, add verified institutional onboarding or certify production identity security.
3. **Shared sample accounts.** Multiple visitors can use the same examples. This is not isolation between every evaluator's changes.
4. **Quarantined uploads.** Malware scanning is unconfigured. Do not turn quarantine into a passed state merely for a demonstration.
5. **Processing prerequisites.** Tesseract, language files, ClamAV, signature trust configuration and other binaries/configuration are separate from Python package installation. We did not demonstrate all of them on Render.
6. **Report presentation.** Download works; raw JSON and technical wording need revision.
7. **Review-form visibility.** The form appears below the table without automatic scrolling.
8. **Free-hosting limits.** Cold starts and account usage limits can affect access. Keeping the database and file storage in the cloud does not eliminate every operational dependency.
9. **Privileged server credentials.** The backend uses powerful DB/storage access. Further least-privilege credentials and a complete security/access audit are required for real confidential data.
10. **Backups and operations.** The verified transfer is not a full scheduled backup/restore, monitoring or disaster-recovery plan.
11. **Regulatory/AI limits.** This setup did not make every AICTE rule authoritative, connect live issuer systems, establish forensic accuracy or create automatic approval decisions.

When explaining the project, say: “The evaluator prototype uses a hosted FastAPI backend, Supabase PostgreSQL and private document storage. Officer review and evidence access are demonstrated. New queued reports currently require our local worker.” Avoid claiming an always-on production AICTE system.

## 20. Routine operation and future changes

### When you only want to visit the live site

Open [Uranium Verify](https://uraniumverify.vercel.app/). No VS Code or local frontend/API is required.

### When you need to generate a new report

Start the local worker using the command in section 15, leave it connected, request one report and confirm a download. Do not rerun setup or migrations to start a worker.

### When you change code

1. Check `git status` and your current branch.
2. Preserve existing local work; do not force-reset the folder to make it “clean.”
3. Work on a feature branch based on the current intended base.
4. Test the affected feature locally.
5. Stage only relevant source files. Keep `.env`, `.venv` and `var` private/untracked.
6. Commit with a clear description and push.
7. Check the Vercel preview and/or Render deployment for the relevant service branch.
8. Create a pull request into `main`, inspect the diff and checks, and merge using the repository's history-preserving workflow.
9. Wait for the production deployment and repeat the relevant live check.

Vercel production follows `main`; Render was configured to follow `backend/supabase-setup`. Therefore a push can update a backend service before a frontend production merge. Track each service's branch instead of assuming that every deployment follows the same one.

### Files to keep private

Keep `.env`, raw credentials, local database copies, original private documents, caches and `.venv` out of commits. The project's `.gitignore` covers `.env`, `.venv` and `var`. Save database and API secrets in a password manager; a Git repository is not a secret backup.

### Simple evaluator checklist

- Open the stable live website, not localhost or an obsolete preview URL.
- Test health, institution login, officer case access and an existing attachment.
- If presenting a new report, verify a worker is running and the report actually completes.
- Keep a ready report available as an example, with an honest explanation of current report wording limitations.
- Distinguish stored sample records from live external verification results.
- Remember that evaluators visiting later may encounter queued report generation while the local worker is off.

## 21. Learning path and official resources

You do not need to master all of this at once. Learn one layer, build a small example, and explain how it connects to the next. The durations below are a suggested study rhythm, not a promise of mastery.

### Stage 1 — Files, terminal and Git

**Learn:** absolute/relative paths, current directory, processes, ports, environment variables, repository, branch, commit, remote, pull request and merge.

**Practice:** create a tiny repository, edit one file on a branch, open a pull request, inspect its diff and merge. Start a local server, leave it running and use a second terminal. Explain why closing the terminal stops a process.

**Resources:** [GitHub Learn](https://learn.github.com/), [Pro Git book](https://git-scm.com/book/en/v2), [VS Code terminal guide](https://code.visualstudio.com/docs/terminal/basics).

**You understand this stage when:** you can identify your branch and folder, explain commit versus push, and avoid committing `.env` without relying on copied commands.

### Stage 2 — Web fundamentals and frontend

**Learn:** HTML, CSS, JavaScript, HTTP methods/status codes, JSON, browser developer tools, fetch, cookies, origins, React components/state and TypeScript types.

**Practice:** make a small form, submit data to a sample API and show loading/error/success states. Inspect a request in the Network panel. Make a favicon and update title/description metadata. Learn why a social card can be cached after the page changes.

**Resources:** [MDN Learn Web Development](https://developer.mozilla.org/en-US/docs/Learn_web_development), [React Learn](https://react.dev/learn), [TypeScript Handbook](https://www.typescriptlang.org/docs/handbook/intro.html), [TanStack Router documentation](https://tanstack.com/router/latest/docs/framework/react/overview), [TanStack Query documentation](https://tanstack.com/query/latest/docs/framework/react/overview).

**You understand this stage when:** you can trace a button click to a request and distinguish a frontend rendering problem from an API error.

### Stage 3 — Python and virtual environments

**Learn:** variables, functions, imports, classes, exceptions, files, `pathlib`, modules, virtual environments and package installation.

**Practice:** write a script that reads non-sensitive configuration, hashes a file and handles a missing-file error. Create a fresh virtual environment and install a small locked set of dependencies.

**Resources:** [Python tutorial](https://docs.python.org/3/tutorial/), [Python virtual environments](https://docs.python.org/3/library/venv.html), [Python Packaging guide](https://packaging.python.org/en/latest/tutorials/installing-packages/). The official Python tutorial assumes some basic programming familiarity; start with fundamentals and small exercises if you are entirely new.

**You understand this stage when:** you know which Python executable is running, why `.venv` exists, and how to report an error without exposing secrets.

### Stage 4 — SQL and PostgreSQL

**Learn:** tables, rows, columns, primary/foreign keys, joins, constraints, transactions, indexes, schemas, roles and grants. Understand `public` versus `PUBLIC`, and what `search_path` does.

**Practice:** in a separate learning database, create institutions and applications, relate them with a foreign key, query them with a join, and test which role can access a private schema. Do not practice destructive SQL in the evaluator database.

**Resources:** [PostgreSQL tutorial](https://www.postgresql.org/docs/current/tutorial.html), [Supabase database guides](https://supabase.com/docs/guides/database/overview), [Supabase Row Level Security](https://supabase.com/docs/guides/database/postgres/row-level-security).

**You understand this stage when:** you can write a query yourself and explain why a private schema, a table permission and an RLS policy are different controls.

### Stage 5 — FastAPI, SQLAlchemy and Alembic

**Learn:** routes, request/response validation, dependencies, sessions, authorization, engine/connection/session differences, ORM models and migrations.

**Practice:** build a small application API with two roles and institution-scoped records. Write tests proving that one institution cannot read another's record. Add a column through a migration and verify the migration revision.

**Resources:** [FastAPI tutorial](https://fastapi.tiangolo.com/tutorial/), [SQLAlchemy tutorial](https://docs.sqlalchemy.org/en/21/tutorial/), [Alembic tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html), [Pydantic documentation](https://docs.pydantic.dev/latest/). Select documentation matching installed package versions. FastAPI's SQL tutorial may use SQLModel; this project uses SQLAlchemy directly.

**You understand this stage when:** you can explain the purpose of `config.py`, `db.py`, `models.py` and migrations without describing them all as “the database file.”

### Stage 6 — Supabase Storage and server security

**Learn:** private buckets, publishable versus secret keys, object keys, immutable files, SHA-256 checks, backend authorization, quarantine, CSRF and session-cookie flags.

**Practice:** in a separate test bucket, upload a synthetic PDF from a server, download it and verify its hash. Test a conflicting write and an unauthorized application request. Keep privileged keys out of your React build.

**Resources:** [Supabase Storage fundamentals](https://supabase.com/docs/guides/storage/buckets/fundamentals), [Supabase API keys](https://supabase.com/docs/guides/getting-started/api-keys), [Storage upload behavior](https://supabase.com/docs/guides/storage/uploads/standard-uploads), [OWASP Cheat Sheet Series](https://cheatsheetseries.owasp.org/).

**You understand this stage when:** you can explain how a user can see an authorized private file without receiving the server's secret key, and why hashing is different from encryption or malware scanning.

### Stage 7 — Deployment and operations

**Learn:** build/start commands, Linux versus Windows dependencies, environment settings, health checks, logs, HTTPS, external rewrites, preview versus production and free-hosting limits.

**Practice:** deploy a separate small API, connect a preview frontend through a rewrite, test cookies after refresh, intentionally break one safe setting and diagnose the resulting logs. Restore the setting and repeat the checks.

**Resources:** [Render FastAPI deployment](https://render.com/docs/deploy-fastapi), [Render free limitations](https://render.com/docs/free), [Vercel rewrites](https://vercel.com/docs/routing/rewrites), [Vercel deployments](https://vercel.com/docs/deployments).

**You understand this stage when:** you can identify which service failed and which branch/configuration it uses, rather than redeploying everything blindly.

### Stage 8 — Workers, testing and reliability

**Learn:** job states, polling, retries, duplicate processing, idempotency, failure recovery, resource limits, monitoring, backups and restore testing. A reliable retry must avoid duplicating irreversible work.

**Practice:** build a small report queue, stop/restart its worker, verify pending jobs, make a duplicate request and confirm correct behavior. Back up a separate learning database and bucket and prove you can restore them.

**Resources:** [Render background workers](https://render.com/docs/background-workers), [pytest documentation](https://docs.pytest.org/en/stable/), [HTTPX documentation](https://www.python-httpx.org/), [Playwright documentation](https://playwright.dev/docs/intro).

**You understand this stage when:** you can explain why a healthy API can coexist with a stalled report queue and demonstrate recovery without deleting evidence or manufacturing a passed result.

### A realistic study rhythm

Start with terminal/Git and web basics, then Python and SQL, followed by APIs/migrations, private storage and deployment. Finally practice queues, testing and recovery. Spending a few weeks on each pair of layers is a useful starting plan; progress should be measured by what you can build and explain, not by finishing videos.

For every topic, follow this cycle: read the official guide, build a small example, deliberately trigger a safe failure, fix it, and write a short explanation in your own words.

### Final mastery exercise

In a new learning project with synthetic records, reproduce the complete journey without copying this repository wholesale:

1. A React form submits an application to a FastAPI endpoint.
2. The backend validates it and stores it in PostgreSQL.
3. A private PDF is uploaded and linked to that application.
4. Institution and officer access rules are tested.
5. A worker generates a readable evidence summary.
6. A preview deployment is tested, merged and published.
7. Credentials remain private, original files are not overwritten, and a backup/restore is demonstrated.
8. You can stop any one process and explain exactly what keeps working and what waits.

Being able to build, explain, test and recover that small system is a stronger measure of mastery than memorizing commands.
