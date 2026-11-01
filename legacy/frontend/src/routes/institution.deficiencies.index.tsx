import { DataTable } from "@/components/portal";
import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { InnerPage, Status, EmptyRow, Filters } from "@/components/portal";
import { Link } from "@/components/link";
import { useCurrentUser, useStore } from "@/lib/store";
import { seo } from "@/lib/seo";

export const Route = createFileRoute("/institution/deficiencies/")({
  head: seo("Deficiencies", "Deficiency Notices issued against your institution's applications."),
  component: Page,
});

function Page() {
  const user = useCurrentUser();
  const apps = useStore((s) => s.applications);
  const defs = useStore((s) => s.deficiencies).filter(
    (d) => apps.find((a) => a.id === d.appId)?.institutionId === user?.institutionId,
  );
  const [st, setSt] = useState("");
  const [q, setQ] = useState("");
  const list = defs.filter(
    (d) =>
      (!st || d.status === st) &&
      `${d.id} ${d.description} ${apps.find((a) => a.id === d.appId)?.ref}`
        .toLowerCase()
        .includes(q.toLowerCase()),
  );
  return (
    <InnerPage role="institution" crumbs={[{ label: "Deficiencies" }]} title="Deficiency Notices">
      <Filters>
        <div className="flex-1 min-w-[12rem]">
          <label className="label" htmlFor="q">
            Search
          </label>
          <input id="q" className="field" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <div>
          <label className="label" htmlFor="st">
            Status
          </label>
          <select id="st" className="field" value={st} onChange={(e) => setSt(e.target.value)}>
            <option value="">All</option>
            <option>Open</option>
            <option>Responded</option>
            <option>Closed</option>
          </select>
        </div>
      </Filters>
      <DataTable className="gov-table">
        <thead>
          <tr>
            <th>Notice No.</th>
            <th>Application</th>
            <th>Category</th>
            <th>Description</th>
            <th>Raised By</th>
            <th>Due</th>
            <th>Status</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {list.length === 0 ? (
            <EmptyRow cols={8} />
          ) : (
            list.map((d) => (
              <tr key={d.id}>
                <td>{d.id}</td>
                <td>{apps.find((a) => a.id === d.appId)?.ref}</td>
                <td>{d.category}</td>
                <td className="max-w-sm">{d.description}</td>
                <td>
                  {d.raisedBy}
                  <div className="text-xs text-muted-foreground">{d.raisedOn}</div>
                </td>
                <td>{d.dueOn}</td>
                <td>
                  <Status s={d.status} />
                </td>
                <td>
                  <Link to={`/institution/deficiencies/${d.id}/respond`} className="link">
                    {d.status === "Open" ? "Respond" : "View"}
                  </Link>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </DataTable>
    </InnerPage>
  );
}
