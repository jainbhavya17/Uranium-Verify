import { DataTable } from "@/components/portal";
import { createFileRoute } from "@tanstack/react-router";
import { InstitutionAppPage } from "@/components/app-flow";
import { Panel } from "@/components/portal";
import { Link } from "@/components/link";
import { seo } from "@/lib/seo";

export const Route = createFileRoute("/institution/applications/$id/history")({
  head: seo("Application History", "Chronological record of all actions taken on the application."),
  component: Page,
});

function Page() {
  const { id } = Route.useParams();
  return (
    <InstitutionAppPage id={id} title="Application History">
      {(a) => (
        <div className="space-y-5">
          <Panel title="Action Log">
            <DataTable className="gov-table">
              <thead>
                <tr>
                  <th>Date & Time</th>
                  <th>Action</th>
                  <th>By</th>
                  <th>Remarks</th>
                </tr>
              </thead>
              <tbody>
                {[...a.history].reverse().map((h, i) => (
                  <tr key={i}>
                    <td className="whitespace-nowrap">{h.at}</td>
                    <td>{h.action}</td>
                    <td>{h.by}</td>
                    <td>{h.remark ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          </Panel>
          <Panel title="Versions">
            <DataTable className="gov-table">
              <thead>
                <tr>
                  <th>Version</th>
                  <th>Date</th>
                  <th>State</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {a.frozen && (
                  <tr>
                    <td>Submitted Version (v1)</td>
                    <td>{a.frozen.submittedOn}</td>
                    <td>Frozen, read-only</td>
                    <td>
                      <Link to={`/institution/records/${a.id}`} className="link">
                        View Record
                      </Link>
                    </td>
                  </tr>
                )}
                <tr>
                  <td>Working Copy</td>
                  <td>{a.createdOn}</td>
                  <td>{a.status === "Draft" ? "Editable draft" : "Locked"}</td>
                  <td>
                    <Link to={`/institution/applications/${a.id}/details`} className="link">
                      Open
                    </Link>
                  </td>
                </tr>
              </tbody>
            </DataTable>
          </Panel>
        </div>
      )}
    </InstitutionAppPage>
  );
}
