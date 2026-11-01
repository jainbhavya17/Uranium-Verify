import { DataTable } from "@/components/portal";
import { createFileRoute } from "@tanstack/react-router";
import { InstitutionAppPage, WizardNav } from "@/components/app-flow";
import { Panel, Status } from "@/components/portal";
import { evaluateRules, useStore } from "@/lib/store";
import { ReadinessPanel } from "@/components/workflow-tools";
import { seo } from "@/lib/seo";

export const Route = createFileRoute("/institution/applications/$id/validation")({
  head: seo("Pre-Validation", "Local readiness and sample compliance checks before submission."),
  component: Page,
});

function Page() {
  const { id } = Route.useParams();
  const rules = useStore((s) => s.rules);
  return (
    <InstitutionAppPage id={id} step="validation" title="Pre-Validation">
      {(a) => {
        const res = evaluateRules(a, rules);
        const fails = res.filter((r) => !r.pass).length;
        return (
          <div className="space-y-5">
            <ReadinessPanel application={a} />
            <Panel title="Sample Rule Evaluation">
              <div className={`notice mb-4`}>
                {fails === 0
                  ? "All active sample rules pass. Review the readiness checklist before submission."
                  : `${fails} rule(s) not satisfied. Rectify the particulars or documents before submission.`}
              </div>
              <DataTable className="gov-table">
                <thead>
                  <tr>
                    <th>Rule</th>
                    <th>Clause</th>
                    <th>Requirement</th>
                    <th>Observed</th>
                    <th>Result</th>
                  </tr>
                </thead>
                <tbody>
                  {res.map((r) => (
                    <tr key={r.rule.id}>
                      <td>
                        {r.rule.id} {r.rule.title}
                      </td>
                      <td>{r.rule.clause}</td>
                      <td>{r.rule.description}</td>
                      <td>{r.observed}</td>
                      <td>
                        <Status s={r.pass ? "Pass" : "Fail"} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </DataTable>
              {a.status === "Draft" && <WizardNav id={a.id} step="validation" />}
            </Panel>
          </div>
        );
      }}
    </InstitutionAppPage>
  );
}
