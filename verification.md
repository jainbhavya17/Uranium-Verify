# Verification record — 2 November 2026

## Automated results

| Check                               | Observed result                                                                                                                                                                                                                                                                            |
| ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Current API suite, isolated SQLite  | **102 passed**, `tmp/api-final.xml`; includes actual PDF/OCR processing, safety-boundary behavior, scoped access, immutability, stale revisions, reports, notifications, notice publication and disabled legacy shortcuts.                                                                 |
| Isolated PostgreSQL 18.4            | **101 passed** in the earlier full database-specific run; migration upgrade/check/downgrade/reapply all passed. The later shortcut guard and precheck wording/version adjustments were subsequently verified in the 102-test SQLite run. Original source PostgreSQL/database was not used. |
| Current ORM versus migration schema | `alembic check`: **No new upgrade operations detected**.                                                                                                                                                                                                                                   |
| Frontend Vitest/RTL                 | **43 passed**: 33 SRS route-template matches, deep-link preservation, session/cache/CSRF behavior, readable findings, exact evidence-source navigation and accessibility components.                                                                                                       |
| axe-core                            | No violations in the evidence-component test. JSDOM color-contrast testing is disabled because it needs layout; this is not a full-page or full-WCAG audit.                                                                                                                                |
| TypeScript                          | Passed after typed OpenAPI regeneration and the interface changes.                                                                                                                                                                                                                         |
| ESLint/Prettier                     | Passed with **0 errors, 23 Fast Refresh warnings** from mixed helper/component exports. Warnings are recorded, not suppressed.                                                                                                                                                             |
| Ruff                                | Passed for services, scripts and API tests.                                                                                                                                                                                                                                                |
| Python lock compatibility           | Every installed package matched `requirements.lock`; `pip check` reported no broken requirements. Verification used the existing compatible interpreter read-only; a fresh checkout should create its own environment.                                                                     |
| Production frontend build           | Passed on patched Vite **8.3.5**. Builds are local artifacts only; no deployment occurred.                                                                                                                                                                                                 |
| Playwright configuration            | Four Chromium/Firefox test cases are discoverable with `playwright test --list`. Full standalone cross-browser execution was **not performed** during this desktop-browser session.                                                                                                        |

Test reports live under ignored/local `tmp` and `var`; rerun documented commands to reproduce. Prior browser-only localStorage tests are archived and not counted as checks of this implementation.

## Browser checks actually observed

- Institution sign-in reaches server-backed records and approved history.
- Category selection shows working EoA and limited intake/additional-course procedures first; other categories are in guidance disclosure.
- A real database draft was created, an authorized-signatory edit saved, and checklist navigation followed.
- Six application steps expose their number and current step. Precheck automatically produced missing-document findings with working correction links.
- Normal upload presentation uses original processing controls; sample attachment shortcuts were removed.
- Officer sign-in reached the assigned queue; a case overview and original-evidence viewer were opened through the translated routes.
- Source review identified and removed raw JSON/assignment-ID lists, repeated `is_mock` rows, epoch timestamps and sample annotations described as machine extraction.
- Mobile-width screenshots show the shared typography, palette, progress navigation and correction cards. `screenshots/precheck-working.jpg` records the final correction guidance.

These are targeted workflow/visual checks, not a claim that every page was exhaustively audited in every browser. Native screen-reader, full keyboard journey, 200% zoom, complete contrast verification, and Firefox execution remain formal acceptance work.

## Dependency audit

The online npm audit initially reported 2 high and 14 moderate advisories. Vite was updated from 8.1.5 to **8.3.5** and Zod from 3.x to **4.6.7**, with build/type/test checks afterward. The subsequent online install audit reported **14 moderate** advisories and no high/critical advisories; the remaining chain is development lint tooling (ESLint, plugins, typescript-eslint/minimatch). No forced major downgrade/update was applied. A later offline install saying zero is not treated as an authoritative security audit.

The preview process was restarted and reported Vite 8.3.5 on `127.0.0.1:5174`. Private API runs on `127.0.0.1:8014`, with a separate worker. The inherited production identity mode remains disabled.

## Deliberate limits

Sample institutional records and example rule interpretations are not approved government records. Issuer checks are clearly identified demonstrations; live AICTE/issuer connections and QR resolvers are not configured. Signature/C2PA results require explicit trust and do not prove all claims in a document. No universal forgery/AI-image detector or automatic floor-plan measurement is claimed. OCR is bounded to the supported printed-English documents/fields. The five restored categories use local reference checklists; complete official procedures and other programmes require separate regulatory review.

There is no production government-readiness or accessibility certification. These limits are reflected in `feature-traceability.md`, help content, connector results and the engineering documentation.

## Portal restoration verification — 2 November 2026

- Existing backend suite: 102 passed (isolated SQLite, 301 seconds).
- New restoration integration tests: 5 passed. Covered additive seeding and tenant/assignment isolation, specialist restrictions, public short/full-reference tracking, draft exclusion, response text/private PDF preview, all five category drafts, conditional leased-land affidavit, optimistic review conflicts, inspection persistence and real report PDF contents.
- Frontend: 46 tests passed, including three carousel navigation/pause/focus checks. TypeScript passed. ESLint has no errors; Fast Refresh organization warnings remain.
- Production build passed. Ruff passed. Alembic reported no new upgrade operations against the local schema.
- Browser checks: populated institution dashboard, all five application choices, APP-01482 tracking, officer sign-in/dashboard, detailed institution dossier and submitted response text/attachment. Screenshots saved under `screenshots/restored-*`.
- A mobile viewport override did not change the browser's reported dimensions in this session, so no new mobile-browser pass is claimed. Responsive styles are included; formal mobile and accessibility audit remains separate.

The new migration was checked on SQLite in this update. Earlier PostgreSQL verification predates migration 0012; PostgreSQL verification of this additive migration remains outstanding.
