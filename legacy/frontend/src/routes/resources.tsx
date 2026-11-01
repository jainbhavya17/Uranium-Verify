import { createFileRoute } from "@tanstack/react-router";
import { ArrowRight, FileCheck2 } from "lucide-react";
import { PublicShell } from "@/components/portal";
import { Link } from "@/components/link";
import { APP_TYPES, DOC_TEMPLATE } from "@/lib/data";
import { seo } from "@/lib/seo";
export const Route = createFileRoute("/resources")({
  head: seo(
    "Application resources",
    "Approval types, document checklists, and the sample scrutiny process.",
  ),
  component: Page,
});
function Page() {
  return (
    <PublicShell landing>
      <div className="uv-resource-page uv-section">
        <span className="uv-eyebrow">PREPARE WITH A CLEAR VIEW</span>
        <h1>
          A little guidance.
          <br />A confident next step.
        </h1>
        <p className="uv-resource-lead">
          Know the application type, gather your documents, and understand what happens after
          submission.
        </p>
        <p className="uv-prototype-note">
          Prototype guidance based on the existing MVP. For real submissions, consult the current
          official AICTE handbook.
        </p>
        <section>
          <h2>Choose your approval type.</h2>
          <div className="uv-resource-grid">
            {APP_TYPES.map((a, i) => (
              <article className={`uv-${["mint", "pink", "blue", "yellow"][i % 4]}`} key={a.code}>
                <span className="uv-eyebrow">{a.code}</span>
                <h3>{a.name}</h3>
                <p>{a.desc}</p>
              </article>
            ))}
          </div>
        </section>
        <section>
          <h2>Your document checklist.</h2>
          <p>Required and supporting evidence used in the sample workflow.</p>
          <ul className="uv-document-list">
            {DOC_TEMPLATE.map((d) => (
              <li key={d.code}>
                <FileCheck2 size={19} />
                <span>{d.name}</span>
                <span className="uv-tag uv-tag-guidance">
                  {d.mandatory ? "Required" : "Supporting"}
                </span>
              </li>
            ))}
          </ul>
        </section>
        <section>
          <h2>From draft to decision.</h2>
          <div className="uv-resource-grid">
            {[
              {
                n: "01",
                title: "Prepare & submit",
                text: "Choose a type, save institution details, add documents, and review validation checks before submission.",
              },
              {
                n: "02",
                title: "Scrutiny & queries",
                text: "An officer reviews evidence and compliance. If a deficiency is raised, the institution can respond for re-verification.",
              },
              {
                n: "03",
                title: "Recorded decision",
                text: "After review, the officer records an approval or rejection with reasons. Follow the outcome in your application history.",
              },
            ].map((s) => (
              <article className="uv-lavender" key={s.n}>
                <span className="uv-eyebrow">{s.n}</span>
                <h3>{s.title}</h3>
                <p>{s.text}</p>
              </article>
            ))}
          </div>
        </section>
        <div className="uv-form-row">
          <Link to="/institution/applications/new" className="uv-button uv-coral">
            Start an application <ArrowRight size={16} />
          </Link>
          <Link to="/help" className="uv-button">
            Visit the help centre
          </Link>
        </div>
      </div>
    </PublicShell>
  );
}
