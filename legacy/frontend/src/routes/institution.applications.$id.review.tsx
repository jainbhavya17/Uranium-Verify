import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { InstitutionAppPage, WizardNav, DetailsDL, DocTable } from "@/components/app-flow";
import { Panel } from "@/components/portal";
import { useGo } from "@/components/link";
import { actions, readiness, useStore } from "@/lib/store";
import { seo } from "@/lib/seo";

export const Route = createFileRoute("/institution/applications/$id/review")({
  head: seo("Review & Submit", "Review the complete application and submit it to AICTE."),
  component: Page,
});

function Page() {
  const { id } = Route.useParams();
  const rules = useStore((s) => s.rules);
  const go = useGo();
  const [ok, setOk] = useState(false);
  return (
    <InstitutionAppPage id={id} step="review" title="Review & Submit">
      {(a) => {
        const blocked = readiness(a, rules).blocking;
        const d = a.frozen ?? a;
        return (
          <div className="space-y-5">
            <Panel title="Application Particulars">
              <DetailsDL a={a} d={d.details} />
            </Panel>
            <Panel title="Documents">
              <DocTable docs={d.documents} />
            </Panel>
            {a.status === "Draft" && (
              <Panel title="Declaration">
                {blocked.length > 0 && (
                  <div className="notice mb-3">
                    Submission is not permitted: {blocked.map((b) => b.text).join(", ")}{" "}
                  </div>
                )}
                <label className="flex gap-2 text-sm">
                  <input type="checkbox" checked={ok} onChange={(e) => setOk(e.target.checked)} />I
                  hereby declare that the information furnished is true and correct to the best of
                  my knowledge. I understand that the submitted application cannot be modified.
                </label>
                <div className="mt-4">
                  <button
                    className="btn btn-primary"
                    disabled={!ok || blocked.length > 0}
                    onClick={() => {
                      actions.submit(a.id);
                      go(`/institution/applications/${a.id}/status`);
                    }}
                  >
                    Submit Application
                  </button>
                </div>
                <WizardNav id={a.id} step="review" />
              </Panel>
            )}
          </div>
        );
      }}
    </InstitutionAppPage>
  );
}
