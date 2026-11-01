import { DataTable } from "@/components/portal";
import { createFileRoute } from "@tanstack/react-router";
import { InstitutionAppPage } from "@/components/app-flow";
import { Panel, Status } from "@/components/portal";
import { Link } from "@/components/link";
import { useCurrentUser, useStore } from "@/lib/store";
import { seo } from "@/lib/seo";

export const Route = createFileRoute("/institution/applications/$id/status")({
  head: seo("Application Status", "Current status, stage and decision of the AICTE application."),
  component: Page,
});

const STAGES = ["Submitted", "Under Scrutiny", "Deficiency Raised", "Decision"];

function Page() {
  const { id } = Route.useParams();
  const user = useCurrentUser();
  const defs = useStore((s) => s.deficiencies.filter((d) => d.appId === id));
  return (
    <InstitutionAppPage id={id} title="Application Status">
      {(a) => {
        const idx =
          a.status === "Approved" || a.status === "Rejected" ? 3 : STAGES.indexOf(a.status);
        return (
          <div className="space-y-5">
            <Panel title="Status Summary">
              <dl className="dl">
                <dt>Application ID</dt>
                <dd>{a.ref}</dd>
                <dt>Current Status</dt>
                <dd>
                  <Status s={a.status} />
                </dd>
                <dt>Submitted On</dt>
                <dd>{a.submittedOn ?? "Not submitted"}</dd>
                <dt>Scrutinising Officer</dt>
                <dd>{a.assignedOfficer ?? "To be assigned"}</dd>
                <dt>Course</dt>
                <dd>{a.details.course}</dd>
                <dt>Intake</dt>
                <dd>{a.details.intake}</dd>
              </dl>
              <ol className="grid grid-cols-4 mt-4 text-xs text-center border border-border">
                {STAGES.map((s, i) => (
                  <li
                    key={s}
                    className={`py-2 border-r border-border ${i <= idx ? "bg-navy text-navy-foreground" : "bg-card"}`}
                  >
                    {s}
                  </li>
                ))}
              </ol>
            </Panel>
            {a.decision && (
              <Panel title="Decision">
                <dl className="dl">
                  <dt>Decision</dt>
                  <dd>
                    <Status s={a.decision.decision} />
                  </dd>
                  <dt>Decided By</dt>
                  <dd>{a.decision.officer}</dd>
                  <dt>Date</dt>
                  <dd>{a.decision.at}</dd>
                  <dt>Reason Recorded</dt>
                  <dd>{a.decision.reason}</dd>
                </dl>
              </Panel>
            )}
            {user && (
              <Panel title="Deficiency Notices">
                <DataTable className="gov-table">
                  <thead>
                    <tr>
                      <th>Notice No.</th>
                      <th>Category</th>
                      <th>Raised On</th>
                      <th>Due</th>
                      <th>Status</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {defs.length === 0 ? (
                      <tr>
                        <td colSpan={6} className="text-center text-muted-foreground py-4">
                          No records found
                        </td>
                      </tr>
                    ) : (
                      defs.map((d) => (
                        <tr key={d.id}>
                          <td>{d.id}</td>
                          <td>{d.category}</td>
                          <td>{d.raisedOn}</td>
                          <td>{d.dueOn}</td>
                          <td>
                            <Status s={d.status} />
                          </td>
                          <td>
                            <Link to={`/institution/deficiencies/${d.id}/respond`} className="link">
                              {d.status === "Open" ? "Respond" : "View"}
                            </Link>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </DataTable>
              </Panel>
            )}
            {!user && (
              <div className="notice">
                Sign in as the applicant institution to view documents, deficiencies and the
                complete record.{" "}
                <Link to="/login" className="link">
                  Login
                </Link>
              </div>
            )}
          </div>
        );
      }}
    </InstitutionAppPage>
  );
}
