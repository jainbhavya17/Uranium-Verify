# Uranium Verify — redesigned working prototype

The approved navy/coral website is the visual base. The SIH solution proposal defines the journey; SRS v1.1 defines acceptance criteria. This folder is isolated from both original MVPs.

## What works

Institution sign-in, previous approved records, versioned application drafts, category/year-specific conditional checklists, private original uploads, automatic safety/readability/extraction processing, pre-submission checks, immutable submission receipts, assigned officer queues, evidence previews, source-linked findings, clarification responses, reports, notifications, and scoped administration now use the Python API and persistent database.

The restored portal supports local preparation and review workflows for EoA, intake increase, new course, new institution and closure, with category-specific reference checklists. These are prototype workflows; complete APH interpretation, official exemptions and live government submission require separate review. Do not describe this as covering every AICTE approval process.

The interface uses one workspace-level sample-record notice. Demonstration issuer responses and unsupported verification methods remain labelled where they affect interpretation. No automated approval/rejection, universal forgery detector, or live AICTE connection is claimed.

## Run locally

Use Node 24 and a compatible Python environment (verified here with Python 3.14.3). The inherited Python lock was checked against the installed environment; every pinned package matched. PostgreSQL-specific migrations and authorization tests were also run against an isolated PostgreSQL 18.4 instance.

```powershell
npm ci
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.lock
./scripts/setup.ps1
```

Setup creates a random password in the ignored `.env` file and applies additive migrations and sample data. Existing records are preserved. The three advertised sample accounts are configured with the public password below; other passwords stay unchanged. It never reads the separate MVP's secrets, database or private documents. For this machine's verification, the existing compatible interpreter in the separate MVP was used read-only; a fresh checkout should create its own environment as above.

Run these in three terminals from this folder, with the environment activated:

```powershell
npm run api
npm run worker
npm run dev -- --port 5174 --host 127.0.0.1
```

Open http://127.0.0.1:5174. The Vite proxy sends `/api` to the isolated API at `127.0.0.1:8014`. API health: `/api/v1/health`; API contract: `/api/v1/openapi.json`. A deployed reverse proxy is a separate deployment task; the existing Cloudflare frontend build does not host this Python service.

Accounts: `admin.a@demo.uranium.test` (institution), `officer.a@demo.uranium.test` (assigned officer), `specialist@demo.uranium.test`, `supervisor@demo.uranium.test`, `platform@demo.uranium.test` (administrator), and `auditor@demo.uranium.test`. The three advertised sample accounts (institution, officer and administrator) use `Uranium@2026!`; each sample button fills both fields. Run `python scripts/seed-demo-accounts.py` to configure those three accounts in an existing local database. Other roles keep the locally generated password from `.env`. Optional `scripts/seed-browser-check.py` creates dedicated synthetic QA accounts; those are not production identities.

## Processing configuration

The checked-in `.env.example` defaults to an unavailable scanner, which retains quarantine. Install ClamAV and current signature definitions; set `MALWARE_SCANNER=clamav`, `CLAMSCAN_PATH`, and `CLAMAV_DATABASE`. Install Tesseract plus `eng` language data and set `TESSERACT_PATH`. This machine has independent copies under ignored `var/tools`, verified as ClamAV 1.5.4 and Tesseract 5.5.3.20260724. Copied antivirus definitions reported 26 October 2026; update them operationally before using non-synthetic uploads.

Original PDFs and images stay in `var/private`; SQLite uses `var/uranium.db` by default. For PostgreSQL set `DATABASE_URL=postgresql+psycopg://...` in private configuration and rerun migrations. No public static file mount exists. Downloads and short-lived previews recheck current authority. S3-compatible storage is not configured; the private local adapter is the implemented storage mode.

C2PA and PDF signature validation require explicit trust configuration (`C2PA_TRUST_ANCHORS`, `PDF_TRUST_ANCHORS`). Generated test roots are for isolated tests only. Issuer integrations are demonstrations, not external confirmations. OCR currently supports printed English and known extraction fields; arbitrary handwritten evidence or floor-plan measurement is not promised.

## Verify

```powershell
npm run typecheck
npm run lint
npm test
npm run build
.venv/Scripts/python.exe -m pytest tests/api --basetemp=tmp/pytest-local
.venv/Scripts/python.exe -m ruff check services scripts tests/api
.venv/Scripts/python.exe scripts/check-runtime.py
```

Playwright checks are in `tests/e2e`; start the three services first, install Playwright browsers, set dedicated `UV_E2E_EMAIL`/`UV_E2E_PASSWORD`, then run `npm run test:e2e`. Chromium/Firefox projects are defined. Browser interaction during this implementation uses the desktop browser testing controls. Do not infer a full Firefox pass merely from the test configuration. Axe component tests supplement manual review and do not establish WCAG/GIGW certification.

See `verification.md` for observed results, `feature-traceability.md` for requirement mapping, `re-engineering.md` for architecture decisions, `changes.md`, `newfeatures.md`, and `reference.md`.

## Earlier browser data

The original `uranium-verify-redesign-v1` localStorage key is left untouched. Earlier source and tests are archived in `legacy/frontend`. Browser-only identities and unverified records are not silently imported as authoritative approvals. A real data migration needs verified institution/user mapping and source review. Source MVP files, database, secrets and private storage remain unchanged.

Production is intentionally disabled by the inherited development identity adapter. An approved identity provider, operational security review, maintained rules, authorized issuer integrations, storage/backup policy, accessibility audit and deployment configuration are separate readiness work.

## Restored portal walkthrough

Select the Institution or Officer sample button on the login screen, then Sign in. Institution users default to the earlier Shri Venkateshwara portal records. Open APP-01482 for a clarification case, and DEF-0931 for a submitted response with its private PDF attachment. Officer users see six restored submitted cases, institution details, document reviews, inspection forms, response re-verification and generated reports. Seven earlier applications are retained in total, including one draft belonging to its own institution.

The homepage includes application-ID tracking (try APP-01482), a three-card campus-first carousel and the supplied mandala in two corner placements. Setup now includes `scripts/seed-restored-portal.py`; it preserves existing applications. See changes.md and verification.md for the latest scope and checks.
