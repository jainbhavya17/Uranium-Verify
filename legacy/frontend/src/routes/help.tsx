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
    "How do I try the different roles?",
    "Visit Sign in and choose an institution, reviewing officer, or administrator sample account. These accounts explore different sides of the same local application data.",
  ],
  [
    "Where do I respond to a deficiency?",
    "Sign in as the institution, open Deficiencies, and select the query. Read the due date and provide a response. An officer can then re-verify and close the deficiency.",
  ],
  [
    "Can I track an application without signing in?",
    "Yes. Use Track your application on the home page with the complete sample ID, such as APP-01482. The public result shows only its status and approval type. Detailed records require the relevant role.",
  ],
  [
    "How do notices get published?",
    "Sign in as the administrator and open Portal notices. Create or edit a notice, set its category and publication date, and enable Publish. Future-dated notices appear on their publication date. Drafts stay in the editor.",
  ],
  [
    "Are my files uploaded to AICTE?",
    "No. This is a browser-based demonstration with no backend or AICTE integration. The existing document flow records file metadata locally; it is not an official document submission.",
  ],
  [
    "Will my changes appear on another device?",
    "No. Data is stored in this browser’s localStorage. Clearing site data removes local changes. This redesign uses a separate storage key from the original MVP.",
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
