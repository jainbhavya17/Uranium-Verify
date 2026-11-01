import { DataTable } from "@/components/portal";
import { createFileRoute } from "@tanstack/react-router";
import { CasePage } from "@/components/app-flow";
import { Panel, Status } from "@/components/portal";
import { evaluateRules, useStore } from "@/lib/store";
import { seo } from "@/lib/seo";

export const Route = createFileRoute("/officer/cases/$id/compliance")({
  head: seo(
    "Compliance Check",
    "Evaluation of the application against active rules of the Approval Process Handbook.",
  ),
  component: Page,
});

function Page() {
  const { id } = Route.useParams();
  const rules = useStore((s) => s.rules);
  return (
    <CasePage id={id} step="compliance">
      {(a) => {
        const res = evaluateRules(a, rules);
        return (
          <Panel title="Regulatory Compliance Report">
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
            <p className="text-sm mt-3">
              <b>{res.filter((r) => !r.pass).length}</b> of {res.length} active rules not satisfied.
              Mismatched documents:{" "}
              {a.documents
                .filter((d) => d.status === "Mismatch Found")
                .map((d) => d.code)
                .join(", ") || "None"}
              .
            </p>
          </Panel>
        );
      }}
    </CasePage>
  );
}
