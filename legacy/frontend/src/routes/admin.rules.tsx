import { DataTable } from "@/components/portal";
import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { InnerPage, Status, EmptyRow, Filters } from "@/components/portal";
import { actions, useStore } from "@/lib/store";
import { seo } from "@/lib/seo";

export const Route = createFileRoute("/admin/rules")({
  head: seo(
    "Rule Library",
    "Compliance rules derived from the Approval Process Handbook used in validation.",
  ),
  component: Page,
});

function Page() {
  const rules = useStore((s) => s.rules);
  const [q, setQ] = useState("");
  const list = rules.filter((r) =>
    `${r.id} ${r.title} ${r.clause}`.toLowerCase().includes(q.toLowerCase()),
  );
  return (
    <InnerPage
      role="admin"
      crumbs={[{ label: "Administration" }, { label: "Rule Library" }]}
      title="Rule Library"
    >
      <Filters>
        <div className="flex-1">
          <label className="label" htmlFor="q">
            Search
          </label>
          <input id="q" className="field" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
      </Filters>
      <DataTable className="gov-table">
        <thead>
          <tr>
            <th>Rule ID</th>
            <th>Title</th>
            <th>Clause</th>
            <th>Requirement</th>
            <th>Status</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {list.length === 0 ? (
            <EmptyRow cols={6} />
          ) : (
            list.map((r) => (
              <tr key={r.id}>
                <td>{r.id}</td>
                <td>{r.title}</td>
                <td>{r.clause}</td>
                <td>{r.description}</td>
                <td>
                  <Status s={r.active ? "Active" : "Disabled"} />
                </td>
                <td>
                  <button className="link" onClick={() => actions.toggleRule(r.id)}>
                    {r.active ? "Deactivate" : "Activate"}
                  </button>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </DataTable>
      <p className="text-xs text-muted-foreground mt-3">
        Deactivated rules are excluded from pre-validation and compliance evaluation. All changes
        are recorded in the Audit Trail.
      </p>
    </InnerPage>
  );
}
