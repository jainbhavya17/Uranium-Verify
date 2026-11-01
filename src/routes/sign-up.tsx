import { createFileRoute } from "@tanstack/react-router";
import { PublicShell } from "@/components/portal";
import { Link } from "@/components/link";
import { seo } from "@/lib/seo";
export const Route = createFileRoute("/sign-up")({
  head: seo("Get started", "Start exploring Uranium Verify with an institution sample account."),
  component: Page,
});
function Page() {
  return (
    <PublicShell landing>
      <section className="uv-section uv-resource-page uv-get-started">
        <span className="uv-eyebrow">YOUR INSTITUTION’S NEXT STEP</span>
        <h1>Start with a workspace.</h1>
        <p className="uv-resource-lead">
          Explore applications, prepare documents, and follow the review process with an institution
          sample account.
        </p>
        <div className="uv-prototype-note">
          <h2>About registration</h2>
          <p>
            The existing MVP uses accounts issued by an administrator. Self-service institution
            registration is not connected to an identity service in this prototype. Explore the
            application journey using the sample accounts on the sign-in page.
          </p>
        </div>
        <div className="uv-form-row">
          <Link to="/login" className="uv-button uv-coral">
            Choose a sample account →
          </Link>
          <Link to="/resources" className="uv-button">
            See what you’ll need
          </Link>
        </div>
      </section>
    </PublicShell>
  );
}
