import { createFileRoute } from "@tanstack/react-router";
import { PublicShell } from "@/components/portal";
import { Link } from "@/components/link";
import { seo } from "@/lib/seo";
export const Route = createFileRoute("/help")({
  head: seo("Help centre", "Get help with sample accounts, documents, and application review."),
  component: Page,
});
const faqs = [
  [
    "How do I sign in?",
    "Choose Institution, Officer or Administrator on the sign-in page to fill both sample credentials, then select Sign in. Their shared sample password is Uranium@2026!. Other accounts use credentials issued by your local administrator.",
  ],
  [
    "What happens when I upload a document?",
    "The server stores the original privately, checks file integrity and malware safety, then extracts readable text. Scanned English documents use OCR. Processing updates automatically; unclear information is flagged for review.",
  ],
  [
    "What should I do before submitting?",
    "Complete the request details, upload applicable documents, then open Precheck. The system checks missing evidence, certificate dates and inconsistent details. Follow each correction link and check again. Submission preserves the version you reviewed.",
  ],
  [
    "Where do I respond to a deficiency?",
    "Open Deficiencies in your institution workspace. Read the published request and deadline, provide the permitted changes and supporting documents, and submit your response. The officer reviews it before closing the request.",
  ],
  [
    "Can I track an application without signing in?",
    "Sign in to view your own applications and status. Application details and document contents are available only to authorized users.",
  ],
  [
    "Which checks need human review?",
    "Document extraction, consistency and date checks assist preparation. Officers review uncertain evidence, infrastructure measurements, regulatory interpretations and verification results. Review priorities do not approve or reject an application.",
  ],
  [
    "What does demonstration verification mean?",
    "This workspace uses sample institutional records and example rule interpretations. Issuer responses are explicitly marked as demonstrations because no authorized issuer is connected. C2PA and PDF signature checks inspect supported cryptographic evidence; an absent signal does not prove authenticity. Unsupported watermark checks remain unavailable.",
  ],
  [
    "Will my saved work appear in another browser?",
    "Saved applications, document versions, notices and reports are held by this prototype’s server. They are available when you sign in with the same authorized account. Earlier browser-only prototype data remains in its original browser storage and is not treated as an approved institutional record.",
  ],
  [
    "How do I publish a portal notice?",
    "Administrators can open Portal notices, create a draft and set a publication date. Choose Published to display it from that date. Archived notices stay in the library. Each saved change is recorded in the audit trail.",
  ],
];
function Page() {
  return (
    <PublicShell landing>
      <section className="uv-section uv-resource-page">
        <span className="uv-eyebrow">HELP, WHEN YOU NEED IT</span>
        <h1>Let’s clear things up.</h1>
        <p className="uv-resource-lead">
          A few answers to help you find your way around the prototype.
        </p>
        <div className="uv-faq">
          {faqs.map(([q, a]) => (
            <details key={q}>
              <summary>
                {q}
                <span aria-hidden="true">+</span>
              </summary>
              <p>{a}</p>
            </details>
          ))}
        </div>
        <div className="uv-form-row">
          <Link to="/login" className="uv-button uv-coral">
            Explore sample accounts
          </Link>
          <Link to="/resources" className="uv-button">
            Application guidance
          </Link>
        </div>
      </section>
    </PublicShell>
  );
}
