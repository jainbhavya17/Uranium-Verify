import { DataTable } from "@/components/portal";
import { Link, useGo } from "./link";
import type { ReactNode } from "react";
import { Check } from "lucide-react";
import { InnerPage, Status, instName } from "./portal";
import { useCurrentUser, useStore } from "@/lib/store";
import type { Application } from "@/lib/data";

export const WIZARD = [
  { slug: "details", label: "Application Details" },
  { slug: "checklist", label: "Document Checklist" },
  { slug: "documents", label: "Documents" },
  { slug: "validation", label: "Pre-Validation" },
  { slug: "review", label: "Review & Submit" },
] as const;

export function useApp(id: string) {
  return useStore((s) => s.applications.find((a) => a.id === id));
}

function NotFound({ id }: { id: string }) {
  return (
    <div className="notice">
      No application found with reference <b>{id}</b>.{" "}
      <Link to="/" className="link">
        Return to Home
      </Link>
    </div>
  );
}

/** Institution application page wrapper with ownership check and wizard step bar. */
export function InstitutionAppPage({
  id,
  step,
  title,
  children,
  allowPublic,
}: {
  id: string;
  step?: string;
  title: string;
  children: (a: Application) => ReactNode;
  allowPublic?: boolean;
}) {
  const a = useApp(id);
  const user = useCurrentUser();
  const crumbs = [
    { label: "My Applications", to: "/institution/applications" },
    { label: a?.ref ?? id, to: a ? `/institution/applications/${a.id}/status` : undefined },
    { label: title },
  ];
  return (
    <InnerPage role="institution" allowPublic={allowPublic} crumbs={crumbs} title={title}>
      {!a ? (
        <NotFound id={id} />
      ) : user && user.institutionId !== a.institutionId ? (
        <div className="notice">This application does not belong to your institution.</div>
      ) : (
        <>
          <div className="record-summary">
            <span>
              <b className="text-navy">Application ID:</b> {a.ref}
            </span>
            <span>
              <b className="text-navy">Institution:</b> {instName(a.institutionId)}
            </span>
            <span>
              <b className="text-navy">Type:</b> {a.type}
            </span>
            <span>
              <b className="text-navy">Status:</b> <Status s={a.status} />
            </span>
          </div>
          {step && (
            <ol className="flow-steps" aria-label="Application steps">
              {WIZARD.map((w, i) => (
                <li key={w.slug}>
                  <Link
                    to={`/institution/applications/${a.id}/${w.slug}`}
                    aria-current={w.slug === step ? "step" : undefined}
                    className={`flow-step ${w.slug === step ? "current" : ""} ${i < WIZARD.findIndex((w) => w.slug === step) ? "visited" : ""}`}
                  >
                    <span className="step-number">{i + 2}</span>
                    <span>
                      <small>Step {i + 2}</small>
                      {w.label}
                    </span>
                  </Link>
                </li>
              ))}
            </ol>
          )}
          {step && a.status !== "Draft" && (
            <div className="notice mb-4">
              This application was submitted on {a.submittedOn} and is frozen. The content below is
              read-only.{" "}
              <Link to={`/institution/records/${a.id}`} className="link">
                View submitted record
              </Link>
            </div>
          )}
          {children(a)}
          <div className="mt-6 flex flex-wrap gap-2 text-sm">
            <Link to={`/institution/applications/${a.id}/status`} className="btn btn-outline">
              Application Status
            </Link>
            <Link to={`/institution/applications/${a.id}/history`} className="btn btn-outline">
              Application History
            </Link>
          </div>
        </>
      )}
    </InnerPage>
  );
}

export function WizardNav({
  id,
  step,
  onNext,
  nextDisabled,
}: {
  id: string;
  step: string;
  onNext?: () => void;
  nextDisabled?: boolean;
}) {
  const go = useGo();
  const i = WIZARD.findIndex((w) => w.slug === step);
  const prev =
    i > 0
      ? `/institution/applications/${id}/${WIZARD[i - 1].slug}`
      : "/institution/applications/new";
  const next =
    i < WIZARD.length - 1 ? `/institution/applications/${id}/${WIZARD[i + 1].slug}` : null;
  return (
    <div className="flex justify-between mt-5">
      <Link to={prev} className="btn btn-outline">
        &larr; Previous
      </Link>
      {next && (
        <button
          className="btn btn-primary"
          disabled={nextDisabled}
          onClick={() => {
            onNext?.();
            go(next);
          }}
        >
          Save &amp; Continue &rarr;
        </button>
      )}
    </div>
  );
}

export const CASE_STEPS = [
  { slug: "overview", label: "Overview" },
  { slug: "evidence", label: "Evidence" },
  { slug: "authenticity", label: "Authenticity" },
  { slug: "compliance", label: "Compliance" },
  { slug: "inspection", label: "Inspection" },
  { slug: "review", label: "Review & Decision" },
] as const;

export function CasePage({
  id,
  step,
  children,
}: {
  id: string;
  step: string;
  children: (a: Application) => ReactNode;
}) {
  const a = useApp(id);
  const i = CASE_STEPS.findIndex((c) => c.slug === step);
  const cur = CASE_STEPS[i];
  return (
    <InnerPage
      role="officer"
      crumbs={[
        { label: "Case Queue", to: "/officer/queue" },
        { label: a?.ref ?? id, to: `/officer/cases/${id}/overview` },
        { label: cur.label },
      ]}
      title={cur.label}
    >
      {!a || a.status === "Draft" ? (
        <NotFound id={id} />
      ) : (
        <>
          <div className="record-summary">
            <span>
              <b className="text-navy">Institution:</b> {instName(a.institutionId)}
            </span>
            <span>
              <b className="text-navy">Type:</b> {a.type}
            </span>
            <span>
              <b className="text-navy">Assigned:</b> {a.assignedOfficer ?? "Unassigned"}
            </span>
            <span>
              <b className="text-navy">Status:</b> <Status s={a.status} />
            </span>
          </div>
          <ol className="flow-steps" aria-label="Application steps">
            {CASE_STEPS.map((c, j) => (
              <li key={c.slug}>
                <Link
                  to={`/officer/cases/${a.id}/${c.slug}`}
                  aria-current={c.slug === step ? "step" : undefined}
                  className={`flow-step ${c.slug === step ? "current" : ""}`}
                >
                  <span className="step-number">{j + 1}</span>
                  <span>
                    <small>Stage {j + 1}</small>
                    {c.label}
                  </span>
                </Link>
              </li>
            ))}
          </ol>
          {children(a)}
          <div className="flex justify-between mt-6">
            {i > 0 ? (
              <Link
                to={`/officer/cases/${a.id}/${CASE_STEPS[i - 1].slug}`}
                className="btn btn-outline"
              >
                &larr; {CASE_STEPS[i - 1].label}
              </Link>
            ) : (
              <Link to="/officer/queue" className="btn btn-outline">
                &larr; Case Queue
              </Link>
            )}
            {i < CASE_STEPS.length - 1 && (
              <Link
                to={`/officer/cases/${a.id}/${CASE_STEPS[i + 1].slug}`}
                className="btn btn-primary"
              >
                {CASE_STEPS[i + 1].label} &rarr;
              </Link>
            )}
          </div>
        </>
      )}
    </InnerPage>
  );
}

export function DetailsDL({ a, d = a.details }: { a: Application; d?: Application["details"] }) {
  return (
    <dl className="dl">
      <dt>Application ID</dt>
      <dd>{a.ref}</dd>
      <dt>Institution</dt>
      <dd>{instName(a.institutionId)}</dd>
      <dt>Application Type</dt>
      <dd>{a.type}</dd>
      <dt>Programme</dt>
      <dd>{d.programme}</dd>
      <dt>Course</dt>
      <dd>{d.course || "—"}</dd>
      <dt>Intake</dt>
      <dd>{d.intake}</dd>
      <dt>Academic Year</dt>
      <dd>{d.academicYear}</dd>
      <dt>Land Area</dt>
      <dd>{d.landArea} acres</dd>
      <dt>Built-up Area</dt>
      <dd>{d.builtUpArea} sq.m</dd>
      <dt>Full-time Faculty</dt>
      <dd>{d.facultyCount}</dd>
      <dt>Head of Institution</dt>
      <dd>{d.principal || "—"}</dd>
      <dt>Address</dt>
      <dd>{d.address || "—"}</dd>
      <dt>Submission Date</dt>
      <dd>{a.submittedOn ?? "Not submitted"}</dd>
    </dl>
  );
}

export function DocTable({
  docs,
  link,
}: {
  docs: Application["documents"];
  link?: (code: string) => ReactNode;
}) {
  return (
    <div className="overflow-x-auto">
      <DataTable className="gov-table">
        <thead>
          <tr>
            <th>Code</th>
            <th>Document</th>
            <th>Mandatory</th>
            <th>File</th>
            <th>Status</th>
            <th>Verification Report</th>
            {link && <th>Action</th>}
          </tr>
        </thead>
        <tbody>
          {docs.map((d) => (
            <tr key={d.code}>
              <td>{d.code}</td>
              <td>{d.name}</td>
              <td>{d.mandatory ? "Yes" : "No"}</td>
              <td>
                {d.fileName ?? "—"}
                {d.uploadedOn && (
                  <div className="text-xs text-muted-foreground">Uploaded {d.uploadedOn}</div>
                )}
              </td>
              <td>
                <Status s={d.status} />
              </td>
              <td className="text-xs">
                {d.checkedBy ? (
                  <>
                    <div>{d.findings}</div>
                    <div className="text-muted-foreground mt-1">
                      Checked by {d.checkedBy} on {d.checkedOn}
                    </div>
                  </>
                ) : d.status === "Under Review" ? (
                  "Verification pending"
                ) : (
                  "—"
                )}
              </td>
              {link && <td>{link(d.code)}</td>}
            </tr>
          ))}
        </tbody>
      </DataTable>
    </div>
  );
}
