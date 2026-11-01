# UX4G review decisions

Checked against UX4G accessibility foundations and application/submission patterns on 2 November 2026. This is a design/application review, not a certification.

| Guidance                                     | Application in this prototype                                                                             | Verification / remaining scope                                                                        |
| -------------------------------------------- | --------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| Consistent navigation and clear page purpose | Shared header, role sidebar, breadcrumbs, page heading and specific next-step description                 | 33 core route templates resolve automatically; institution workflow manually navigated.               |
| Orient users in a long form                  | Six visible application steps, announced step count and `aria-current=step`                               | Browser accessibility tree confirms step names/counts.                                                |
| Reduce decision load                         | Usable categories first; unfinished categories in guidance disclosure                                     | Browser confirms two main application choices rather than a grid of unfinished procedures.            |
| Visible labels, relevant input types         | Email/date/numeric controls, labelled inputs, draft vs submission requirement distinction                 | Role and form spot checks; field error association on notice and key institution fields.              |
| Actionable errors and recovery               | Server validation, error summary, correction/source links, preserved edits on stale version, retry states | API tests cover validation/conflicts; component/session tests cover presentation and expiry.          |
| Guided upload and processing feedback        | Original upload, format/size limits, progress, queued/safety/quality/review states                        | Real parser/OCR/ClamAV tests; browser checks normal upload presentation.                              |
| Human-readable results                       | Labelled nested values and lists, source cards, contextual supporting details                             | RTL and axe component checks; no JSON dump in normal result component.                                |
| Accessible status                            | Text accompanies color; current step exposed; meaningful names and focus styles                           | Partial automated/component/manual review; full screen-reader audit remains.                          |
| Transparent limitations without clutter      | One sample-workspace context; issuer demonstration warnings at the actual results                         | Avoids implying external authentication while removing repetitive mock banners.                       |
| Responsive layout and keyboard access        | Existing responsive shell, responsive forms/tables, native controls/Radix dialogs                         | Desktop browser check and responsive spot checks; Firefox/200%/NVDA need full independent acceptance. |

Sources: https://www.ux4g.gov.in/foundations/accessibility and https://www.ux4g.gov.in/patterns/application-submission . SRS retains WCAG 2.2 AA as the target even where UX4G documents WCAG 2.1 AA patterns.
