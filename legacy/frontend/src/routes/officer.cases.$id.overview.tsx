import { DataTable } from "@/components/portal";
import { createFileRoute } from "@tanstack/react-router";
import { CasePage, DetailsDL } from "@/components/app-flow";
import { Panel } from "@/components/portal";
import { actions } from "@/lib/store";
import { seo } from "@/lib/seo";

export const Route = createFileRoute("/officer/cases/$id/overview")({
  head: seo("Case Overview", "Particulars of the application under scrutiny."),
  component: Page,
});

function Page() {
  const { id } = Route.useParams();
  return (
    <CasePage id={id} step="overview">
      {(a) => (
        <div className="space-y-5">
          {a.status === "Submitted" && (
            <div className="notice flex flex-wrap items-center justify-between gap-3">
              <span>This case has not been taken up for scrutiny.</span>
              <button className="btn btn-primary" onClick={() => actions.startScrutiny(a.id)}>
                Take Up for Scrutiny
              </button>
            </div>
          )}
          <Panel title="Application Particulars (Submitted Version)">
            <DetailsDL a={a} d={a.frozen?.details} />
          </Panel>
          <Panel title="Recent Actions">
            <DataTable className="gov-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Action</th>
                  <th>By</th>
                </tr>
              </thead>
              <tbody>
                {[...a.history]
                  .reverse()
                  .slice(0, 5)
                  .map((h, i) => (
                    <tr key={i}>
                      <td>{h.at}</td>
                      <td>{h.action}</td>
                      <td>{h.by}</td>
                    </tr>
                  ))}
              </tbody>
            </DataTable>
          </Panel>
        </div>
      )}
    </CasePage>
  );
}
