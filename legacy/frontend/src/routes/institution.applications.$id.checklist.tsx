import { DataTable } from "@/components/portal";
import { createFileRoute } from "@tanstack/react-router";
import { InstitutionAppPage, WizardNav } from "@/components/app-flow";
import { Panel, Status } from "@/components/portal";
import { seo } from "@/lib/seo";

export const Route = createFileRoute("/institution/applications/$id/checklist")({
  head: seo(
    "Document Checklist",
    "List of mandatory and optional documents required for the application.",
  ),
  component: Page,
});

function Page() {
  const { id } = Route.useParams();
  return (
    <InstitutionAppPage id={id} step="checklist" title="Document Checklist">
      {(a) => (
        <Panel title="Documents Required under APH 2026-27, Clause 2.6">
          <DataTable className="gov-table">
            <thead>
              <tr>
                <th>S.No.</th>
                <th>Document</th>
                <th>Mandatory</th>
                <th>Format</th>
                <th>Current Status</th>
              </tr>
            </thead>
            <tbody>
              {a.documents.map((d, i) => (
                <tr key={d.code}>
                  <td>{i + 1}</td>
                  <td>{d.name}</td>
                  <td>{d.mandatory ? "Yes" : "No"}</td>
                  <td>PDF, max 5 MB, digitally signed</td>
                  <td>
                    <Status s={d.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </DataTable>
          <p className="text-xs text-muted-foreground mt-3">
            Documents must be self-attested by the Head of Institution. Documents issued by
            government authorities will be authenticated through connected registries.
          </p>
          {a.status === "Draft" && <WizardNav id={a.id} step="checklist" />}
        </Panel>
      )}
    </InstitutionAppPage>
  );
}
