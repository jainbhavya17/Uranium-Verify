# New and upgraded features

## Institution preparation

Choose the year/category and create or resume a saved draft. Previous approvals remain read-only. Requested name, address, course, intake and room changes are separate from the baseline. The server regenerates conditional requirements and protects against stale edits. EoA is the core procedure; intake/additional-course support is limited; other categories provide guidance only.

Upload original PDFs or supported images. The server hashes and stores them privately, queues scanning and extraction, and preserves previous versions. The interface polls actual processing states. Missing scanner support retains quarantine; unreadable/uncertain evidence gets a correction or review state. There is no button that invents a processed document.

Opening Precheck evaluates current completeness, field consistency and certificate dates. Findings identify what needs attention and link to the saved source where available. Institutions correct permitted details/documents, then review and submit an immutable revision with a receipt. A preliminary pass is not an official approval.

## Officer review

Assigned queues show review progress and interpretable priority reasons. Officers open original evidence, inspect extracted fields/page regions, compare records and record attributed corrections. Evidence cards link findings to their source document version and page; nested result data uses readable labels rather than JSON.

Compliance checks use versioned deterministic rules and retain source references. The limited room-area procedure compares declared and supported areas, applies the selected rule only when applicable, and explains inspection recommendations. It does not infer certified floor area from a photograph.

Issuer demonstrations distinguish match, conflict, timeout and unsupported outcomes. Local PDF-signature and C2PA checks use explicit trust configuration; absent provenance is inconclusive. General forgery detection and provider watermark services are not implemented.

Officers publish clarification requests, route verification tasks and review institution responses. Original submissions remain unchanged; responses have separate revisions and evidence. Generated ReportLab PDFs retain the evaluated snapshot; explicitly published summaries exclude private officer findings. Notifications and audit records connect the workflow.

## Administration

Access changes, connectors, audit exports, rule/source versions and two-person publication reuse server-side authorization. An administrator cannot automatically read all institutional documents. Auditors and verification specialists see appropriate navigation.

Portal notices and homepage announcements are now persistent. An administrator can create drafts, publish from a chosen date, pin a notice or archive it. Concurrent changes require reload rather than silently overwriting another editor. Public pages never receive drafts or private case data.

## Automation boundary

Automated: upload safety/integrity and supported extraction, conditional checklists, current completeness/consistency/date evaluation, version tracking, polling, notifications/report jobs and deterministic prioritization.

Human-reviewed: uncertain extracted information, certified infrastructure inputs, regulatory interpretation, inspection need and review disposition.

Unavailable until configured/reviewed: live issuer/AICTE connections, universal AI-generated/forged-document detection, arbitrary handwriting, automatic plan measurement, full multi-programme rule coverage, production identity/hosting. See `feature-traceability.md` for feature-by-feature proof and limitations.

## Restored working portal journeys

- `/institution/applications/new`: five application categories; save land tenure, campus area, built-up area and faculty count alongside existing institution/course details. Leased-land new-institution proposals activate Affidavit 7; intake/new-course requests include applicable Affidavit 8 and Format 3. Existing-category workflows remain resumable.
- `/institution/applications/APP-01482/status`: institution details, named documents, clarification requests, actual submitted responses, acknowledgment and chronological history.
- `/institution/deficiencies/DEF-0931/respond`: populated response explanation and a private PDF attachment, with original records available on demand.
- `/officer/queue`: six restored submitted cases across five institutions, filtered by status, type or institution. Authorization still depends on current assignment.
- Officer case sections: original file previews, recorded manual document reviews, inspection records, response re-verification, version-checked actions and downloadable captured reports. Manual document review never implies external issuer confirmation.
- Homepage tracking accepts the short application ID or full acknowledgment reference. Drafts and private details are excluded.
- Homepage carousel retains the original campus illustration and adds document and review cards with keyboard-accessible controls.

The restored documents are generated sample PDFs, not recovered authority-issued certificates. They use private storage and real access-controlled previews. New uploads still require real safety/extraction processing. These sample workflows do not constitute full APH certification or live government submission.
