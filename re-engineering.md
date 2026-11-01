# Re-engineering decisions

## Reference order

1. User's current direction: approved website styling and simpler, comprehensible workflows.
2. “Solution proposal breakdown”, SIH 2026 TEAM URANIUM project: Institution → application → processing → corrections → submission → evidence-linked officer review.
3. SRS v1.1: functional requirements, scope tiers and AT-01–AT-18 acceptance tests.
4. Separate Uranium MVP: reusable implementations, locks, migrations and regression tests; not its visual design.
5. UX4G: accessible forms, progress, document upload, feedback and disclosure patterns where useful.

## Architecture

React/TypeScript/TanStack Start and Router remain in place. Shared `InnerPage`/`PublicShell`, existing tokens, Radix components and Lucide icons preserve the approved design. TanStack Query reads the API; backend sessions replace localStorage authority. `src/features/navigation.tsx` translates reused workflow links into the existing portal URLs, including source-version and page query parameters.

FastAPI/Pydantic validate requests. SQLAlchemy/Alembic own durable records. PostgreSQL is supported and separately tested; isolated SQLite is the local default. Private filesystem storage implements authorized access. A separate bounded Python worker owns document/report/notification processing with explicit states, leases and retries. No Redis, hosted AI, vector service or external task queue was added: durable database jobs meet this prototype's demonstrated requirement.

PyMuPDF extracts digital text; Tesseract handles supported scanned English evidence; Pillow/OpenCV prepare and assess images. ClamAV must clear the safety boundary before extraction. SHA-256 identifies immutable bytes. pyHanko/C2PA inspect supported signed evidence with explicit trust configuration. ReportLab creates actual PDF reports. Source-filtered retrieval supports cited regulatory assistance without using model output to decide an application.

## Review of inherited implementation

Reused: per-object institution/assignment checks, CSRF/session handling, original-byte storage, immutable snapshots, processing leases and retries, deterministic rule evaluation, scoped clarification versions, private/publishable report separation, governed source publication and audit records.

Changed rather than reused verbatim: React Router integration, source theme, portal shell, document upload presentation, category choices, repeated sample warnings, generic JSON rendering, evidence-graph navigation, initial session handling, logout cache removal, save-and-continue behavior during autosave, editable notices, help/resources content and accessibility semantics.

Removed from the normal interface: generated fixture attachment buttons and the old quarantine-only uploader. Those backend shortcuts now return 404 outside test environments. Actual uploads always use the processing pipeline. Prior browser-only tests are archived and do not count as evidence for the new backend interface.

## Explicit conflicts resolved

| Conflict                                                               | Resolution                                                                                                                                            |
| ---------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| Earlier no-backend architecture vs latest backend request              | Latest user request takes precedence; change applies only to this nested folder.                                                                      |
| SRS/source UI palette vs approved redesigned page                      | Approved navy/coral theme retained; source workflow behavior adapted.                                                                                 |
| SRS repeated MOCK fixtures vs clean interface                          | One workspace-level sample context; issuer demonstrations and inconclusive results labelled at their point of use. Underlying provenance is retained. |
| Proposal recommends optional Celery/Redis, Supabase, LLMs and pgvector | Existing bounded worker and backend sessions reused; no unnecessary external infrastructure or secrets introduced.                                    |
| Broad AI/forgery claims vs implemented methods                         | Explicit limited OCR/provenance indicators; no general AI/forgery verdict.                                                                            |
| All application categories vs reviewed procedure depth                 | EoA and limited intake/additional-course flow enabled; other categories are guidance until reviewed.                                                  |
| Source admin knowledge route vs existing public resources              | Governed sources use `/admin/knowledge-sources`; public guidance uses `/resources`.                                                                   |
| Existing browser data vs authoritative database                        | Browser data retained in place and archived source; no unverified import into approved history.                                                       |
| SRS WCAG 2.2 AA vs UX4G 2.1 AA patterns                                | Retain SRS's stricter target. Adopting patterns does not claim certification.                                                                         |

## Security boundaries

Server membership and assignment scope is authoritative on each request. HttpOnly sessions use SameSite cookies and CSRF checks for authenticated mutations. Secure cookies must be enabled on HTTPS deployment. Password hashes are server-side. At the user’s explicit request, the three advertised demo accounts have a public sample password that the buttons fill; other credentials remain private. Administrative roles do not imply access to private case evidence. Immutable document versions, submitted revisions, rule inputs and audit records preserve what was checked. External integrations remain unconfigured/demonstrations until authorized.

The production identity adapter is not implemented and production startup fails closed. This is a working development prototype, not a production government service.

## Restored portal presentation and persistence

Migration `0012_restored_portal` adds `portal_case_records` and `portal_institution_profiles` to retain earlier portal context. Core applications, revisions, documents, sessions, assignments, clarifications, reports and audit records remain authoritative in their existing tables. No second client-side authority or localStorage import was introduced.

`seed_restored_portal.py` restores examples additively and produces deterministic sample PDFs. It skips existing application IDs, retains user changes and uses versioned immutable catalogue/rule records. Run it through the updated setup script; a repeated run does not duplicate application records.

`restored_portal.py` provides scoped presentation endpoints and minimal public status tracking. Institution membership and officer assignment checks precede access; specialist roles cannot retrieve the full officer dossier. Document reviews and inspection records require the current review version and create attributed actions. Existing server session/CSRF checks remain in effect.

`RestoredPortal.tsx` supplies the approved portal summaries and case sections. Existing processing and regulatory tools are reused within contextual disclosures. The clarification attachment fix reads the last submitted response revision when no active draft is present. Historical reports retain their earlier snapshot label when later evidence changes.
