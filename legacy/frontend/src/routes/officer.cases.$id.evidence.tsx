import { createFileRoute } from "@tanstack/react-router";
import { CasePage, DocTable } from "@/components/app-flow";
import { Panel } from "@/components/portal";
import { EvidenceVersions } from "@/components/workflow-tools";
import { seo } from "@/lib/seo";

export const Route = createFileRoute("/officer/cases/$id/evidence")({
  head: seo("Case Evidence", "Documents and evidence submitted with the application."),
  component: Page,
});

function Page() {
  const { id } = Route.useParams();
  return (
    <CasePage id={id} step="evidence">
      {(a) => (
        <div className="space-y-5">
          <Panel title="Evidence on record">
            <DocTable docs={a.documents} />
            <p className="text-xs text-muted-foreground mt-3">
              Proceed to the Authenticity step to record verification outcome for each document.
            </p>
          </Panel>
          <EvidenceVersions docs={a.documents} />
        </div>
      )}
    </CasePage>
  );
}
