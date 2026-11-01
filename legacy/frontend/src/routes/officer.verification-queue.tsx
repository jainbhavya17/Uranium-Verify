import { DataTable } from "@/components/portal";
import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { InnerPage, Status, EmptyRow, Filters, instName } from "@/components/portal";
import { Link } from "@/components/link";
import { useStore } from "@/lib/store";
import { seo } from "@/lib/seo";

export const Route = createFileRoute("/officer/verification-queue")({
  head: seo("Verification Queue", "Documents across all cases awaiting authenticity verification."),
  component: Page,
});

function Page() {
  const apps = useStore((s) => s.applications.filter((a) => a.status !== "Draft"));
  const [st, setSt] = useState("Under Review");
  const [q, setQ] = useState("");
  const rows = apps
    .flatMap((a) => a.documents.filter((d) => d.status !== "Not Submitted").map((d) => ({ a, d })))
    .filter(
      ({ a, d }) =>
        (!st || d.status === st) &&
        `${a.ref} ${d.name} ${instName(a.institutionId)}`.toLowerCase().includes(q.toLowerCase()),
    );
  return (
    <InnerPage role="officer" crumbs={[{ label: "Verification Queue" }]} title="Verification Queue">
      <Filters>
        <div className="flex-1 min-w-[12rem]">
          <label className="label" htmlFor="q">
            Search
          </label>
          <input id="q" className="field" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <div>
          <label className="label" htmlFor="st">
            Document Status
          </label>
          <select id="st" className="field" value={st} onChange={(e) => setSt(e.target.value)}>
            <option value="">All</option>
            <option>Under Review</option>
            <option>Verified</option>
            <option>Mismatch Found</option>
          </select>
        </div>
      </Filters>
      <DataTable className="gov-table">
        <thead>
          <tr>
            <th>Application</th>
            <th>Institution</th>
            <th>Document</th>
            <th>Uploaded</th>
            <th>Status</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <EmptyRow cols={6} />
          ) : (
            rows.map(({ a, d }) => (
              <tr key={a.id + d.code}>
                <td className="whitespace-nowrap">{a.ref}</td>
                <td>{instName(a.institutionId)}</td>
                <td>
                  {d.code} · {d.name}
                </td>
                <td>{d.uploadedOn}</td>
                <td>
                  <Status s={d.status} />
                </td>
                <td>
                  <Link to={`/officer/cases/${a.id}/authenticity`} className="link">
                    Verify
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
