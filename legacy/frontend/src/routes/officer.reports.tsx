import { DataTable } from "@/components/portal";
import { createFileRoute } from "@tanstack/react-router";
import { InnerPage, Panel, Status } from "@/components/portal";
import { Link } from "@/components/link";
import { useStore } from "@/lib/store";
import { institutions } from "@/lib/data";
import { ReviewSnapshots } from "@/components/workflow-tools";
import { seo } from "@/lib/seo";

export const Route = createFileRoute("/officer/reports")({
  head: seo("Reports", "Statistical reports on applications, decisions and document verification."),
  component: Page,
});

function Page() {
  const apps = useStore((s) => s.applications.filter((a) => a.status !== "Draft"));
  const statuses = ["Submitted", "Under Scrutiny", "Deficiency Raised", "Approved", "Rejected"];
  const docs = apps.flatMap((a) => a.documents);
  const decided = apps.filter((a) => a.decision);
  return (
    <InnerPage
      role="officer"
      crumbs={[{ label: "Reports" }]}
      title="Reports"
      actions={
        <button className="btn btn-outline" onClick={() => window.print()}>
          Print Report
        </button>
      }
    >
      <div className="space-y-6">
        <ReviewSnapshots />
        <div className="grid gap-6 lg:grid-cols-2">
          <Panel title="Applications by Status">
            <DataTable className="gov-table">
              <thead>
                <tr>
                  <th>Status</th>
                  <th>Count</th>
                </tr>
              </thead>
              <tbody>
                {statuses.map((s) => (
                  <tr key={s}>
                    <td>
                      <Link to="/officer/queue" search={{ status: s }} className="link">
                        {s}
                      </Link>
                    </td>
                    <td>{apps.filter((a) => a.status === s).length}</td>
                  </tr>
                ))}
                <tr>
                  <th>Total</th>
                  <th>{apps.length}</th>
                </tr>
              </tbody>
            </DataTable>
          </Panel>
          <Panel title="Document Verification Summary">
            <DataTable className="gov-table">
              <thead>
                <tr>
                  <th>Status</th>
                  <th>Count</th>
                </tr>
              </thead>
              <tbody>
                {["Verified", "Mismatch Found", "Under Review", "Not Submitted"].map((s) => (
                  <tr key={s}>
                    <td>
                      <Status s={s} />
                    </td>
                    <td>{docs.filter((d) => d.status === s).length}</td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          </Panel>
          <Panel title="Applications by State" className="lg:col-span-2">
            <DataTable className="gov-table">
              <thead>
                <tr>
                  <th>State</th>
                  <th>Institution</th>
                  <th>Applications</th>
                  <th>Approved</th>
                  <th>Rejected</th>
                </tr>
              </thead>
              <tbody>
                {institutions.map((i) => {
                  const x = apps.filter((a) => a.institutionId === i.id);
                  return (
                    <tr key={i.id}>
                      <td>{i.state}</td>
                      <td>{i.name}</td>
                      <td>{x.length}</td>
                      <td>{x.filter((a) => a.status === "Approved").length}</td>
                      <td>{x.filter((a) => a.status === "Rejected").length}</td>
                    </tr>
                  );
                })}
              </tbody>
            </DataTable>
          </Panel>
          <Panel title="Decisions Recorded" className="lg:col-span-2">
            <DataTable className="gov-table">
              <thead>
                <tr>
                  <th>Application</th>
                  <th>Decision</th>
                  <th>Officer</th>
                  <th>Date</th>
                  <th>Reason</th>
                </tr>
              </thead>
              <tbody>
                {decided.map((a) => (
                  <tr key={a.id}>
                    <td>
                      <Link to={`/officer/cases/${a.id}/review`} className="link">
                        {a.ref}
                      </Link>
                    </td>
                    <td>
                      <Status s={a.decision!.decision} />
                    </td>
                    <td>{a.decision!.officer}</td>
                    <td>{a.decision!.at}</td>
                    <td>{a.decision!.reason}</td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          </Panel>
        </div>
      </div>
    </InnerPage>
  );
}
