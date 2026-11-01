# Changes made

- Preserved the approved homepage, typography, colors, shared header/sidebar/breadcrumb and responsive visual language.
- Connected business screens to FastAPI and persistent scoped records rather than browser-only approval data.
- Retained the separate MVP's proven backend modules and locked Python dependencies, while replacing its route integration and visible presentation.
- Added tested route translation for all 33 SRS templates; approved-record and governed-source routes were added without breaking the current portal structure.
- Replaced repeated mock banners with one sample-workspace context. Demonstration issuer responses remain explicit because they do not confirm authenticity.
- Rebuilt document slots around real original uploads and automatic processing. Removed generated attachments and obsolete quarantine-only controls from normal usage; restricted their API endpoints to tests.
- Simplified category selection: usable categories first, unfinished procedures behind guidance disclosure.
- Run current readiness checks when opening Precheck or Review; submission uses the saved evaluation and rejects stale inputs.
- Replaced nested JSON data dumps with labelled results and readable lists. Added navigable evidence source cards.
- Corrected initial anonymous-session handling and logout removal of cached private records.
- Improved draft save/continue during an in-flight autosave and retained conflict recovery.
- Added real unread notification counts, scoped notifications, account sessions, clarification response versions and report library integration.
- Added persistent notice/announcement administration with publication dates, archive states, optimistic concurrency, server validation, CSRF, administrator authorization and audit events. Alembic migration 0011 is additive.
- Corrected outdated help/resources statements about localStorage, public tracking and automatic approval decisions. Public tracking now directs users to authorized applications.
- Added UX4G-inspired progress semantics, visible field errors and supporting guidance while retaining the approved design.
- Archived browser-only test cases so they cannot be mistaken for tests of the new architecture. Added route/session/API/evidence/accessibility and notice/shortcut-guard tests.
- Added setup/runtime checks and the requested engineering, feature, reference, traceability and verification documentation.

No source MVP database, private storage, environment secrets, published history or parent prototype was changed. No deployment or git push was performed.

- Patched Vite to 8.3.5 and Zod to 4.6.7 after online dependency audit; regenerated current OpenAPI JSON/types and retained the original Bun lock in the legacy archive. The active frontend uses package-lock.json.

## Sample sign-in update — 2 November 2026

The user requested usable, prefilled sample credentials. Institution, Officer and Administrator buttons now fill their existing demo email and `Uranium@2026!`. The three local demo-account hashes were updated, prior sessions for changed credentials revoked, and roles/assignments/records preserved. Setup configures these public demo accounts on fresh installations. All three were verified through real API sign-in, authenticated session and sign-out requests.

## Portal restoration — 2 November 2026

Restored the earlier Lovable portal's seven application examples and five institution profiles into the current server-backed prototype. Existing applications are preserved. The institution dashboard defaults to Shri Venkateshwara Institute of Technology; the officer queue displays assigned cases, institution details, document review findings, responses, history and generated reports.

All five earlier categories are selectable: EoA, intake increase, new course, new institution and closure. Supporting-document instructions now name the certificate, issuer information and required contents. Conditional affidavits and structural-stability requirements follow saved application details. Non-applicable requirements do not show an upload control.

Fixed the empty submitted-response attachment list: it previously queried only an active response draft. It now reads the submitted revision when no draft exists. Response text, attachment, version and acknowledgment appear together. Notifications support read/unread filters, marking as read, pagination and translated destination links. Public application-ID tracking returns minimal status information without institution identity or document contents.

Replaced generic officer summary screens with the approved portal's populated layout. Officers can record document reviews, inspection observations, clarification requests, recommendations, re-verification/closure and report generation. Existing detailed extraction, issuer, signature, rule and infrastructure tools remain available in contextual disclosures.

The landing page now has three navigable cards, retaining the original university artwork first. Rotation pauses on hover/focus and has pause and reduced-motion support. The supplied mandala is placed at the hero's left edge and the closing panel's right corner in a restrained theme colour.
