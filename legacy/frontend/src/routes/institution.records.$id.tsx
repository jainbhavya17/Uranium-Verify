import { createFileRoute } from "@tanstack/react-router";
import { InstitutionAppPage, DetailsDL, DocTable } from "@/components/app-flow";
import { Panel } from "@/components/portal";
import { seo } from "@/lib/seo";

export const Route = createFileRoute("/institution/records/$id")({
  head: seo("Record Detail", "Frozen, read-only record of the application as submitted."),
  component: Page,
});

function Page() {
  const { id } = Route.useParams();
  return (
    <InstitutionAppPage id={id} title="Record Detail (Submitted Version)">
      {(a) =>
        !a.frozen ? (
          <div className="notice">
            This application has not been submitted. No frozen record exists.
          </div>
        ) : (
          <div className="space-y-5">
            <div className="notice">
              Read-only record frozen on {a.frozen.submittedOn}. Subsequent verification outcomes
              are shown on the Application Status page.
            </div>
            <Panel title="Particulars as Submitted">
              <DetailsDL a={a} d={a.frozen.details} />
            </Panel>
            <Panel title="Documents as Submitted">
              <DocTable
                docs={a.frozen.documents.map((d) => ({
                  ...d,
                  status: d.status === "Not Submitted" ? d.status : "Under Review",
                  checkedBy: undefined,
                }))}
              />
            </Panel>
            <Panel title="Current Verification Report">
              <DocTable docs={a.documents} />
            </Panel>
          </div>
        )
      }
    </InstitutionAppPage>
  );
}
