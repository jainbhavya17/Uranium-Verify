import { createFileRoute } from "@tanstack/react-router";
import { ArrowRight, FileCheck2 } from "lucide-react";
import { PublicShell } from "@/components/portal";
import { Link } from "@/components/link";
const applicationTypes = [
  {
    code: "EOA",
    name: "Extension of Approval",
    desc: "Prepare an EoA request using a conditional checklist and your previous approved record.",
  },
  {
    code: "INTAKE",
    name: "Intake increase",
    desc: "Propose higher course intake with supporting infrastructure, faculty details and applicable declarations.",
  },
  {
    code: "COURSE",
    name: "New course or programme",
    desc: "Propose the new course, its intake and supporting facilities. Your saved details determine the required declarations.",
  },
  {
    code: "NEW",
    name: "New technical institution",
    desc: "Prepare the campus, sponsoring-body, staffing and applicable land-lease records for a new-institution proposal.",
  },
  {
    code: "CLOSURE",
    name: "Closure of course / institution",
    desc: "Provide the governing-body resolution, reasons and plan to protect enrolled students and their records.",
  },
];
const documentExamples = [
  "Affidavit 2 — Institutional Declaration",
  "Affidavit 7 — Joint Land-Lease Undertaking, where applicable",
  "Affidavit 8 and Format 3 — Intake / New-Course Request",
  "Registered Ownership / Lease Deed",
  "Faculty List with Qualifications",
  "Building and occupancy evidence",
  "Fire and structural safety evidence",
  "Applicable payment records",
  "Financial statements",
  "Programme and infrastructure records",
];
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
          Use the checklist generated for your application. Requirements depend on category, year,
          programme and conditions; consult the official AICTE handbook and applicable amendments.
        </p>
        <section id="documents">
          <h2>Choose your approval type.</h2>
          <div className="uv-resource-grid">
            {applicationTypes.map((a, i) => (
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
          <p>
            Examples of evidence you may need. Your generated checklist determines what is required,
            conditional or due at a later stage.
          </p>
          <ul className="uv-document-list">
            {documentExamples.map((name) => (
              <li key={name}>
                <FileCheck2 size={19} />
                <span>{name}</span>
              </li>
            ))}
          </ul>
        </section>
        <section>
          <h2>From draft to review.</h2>
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
                title: "Recorded review",
                text: "The officer records findings and any further verification needed. Official approval decisions remain with the competent authority.",
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
