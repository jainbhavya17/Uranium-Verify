import { DataTable } from "@/components/portal";
import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { InnerPage, EmptyRow, Filters } from "@/components/portal";
import { useStore } from "@/lib/store";
import { seo } from "@/lib/seo";

export const Route = createFileRoute("/admin/audit")({
  head: seo("Audit Trail", "Chronological log of every action performed on the system."),
  component: Page,
});

function Page() {
  const audit = useStore((s) => s.audit);
  const [q, setQ] = useState("");
  const [role, setRole] = useState("");
  const [from, setFrom] = useState("");
  const list = audit.filter(
    (a) =>
      (!role || a.role === role) &&
      (!from || a.at >= from) &&
      `${a.actor} ${a.action} ${a.ref}`.toLowerCase().includes(q.toLowerCase()),
  );
  return (
    <InnerPage
      role="admin"
      crumbs={[{ label: "Administration" }, { label: "Audit Trail" }]}
      title="Audit Trail"
    >
      <Filters>
        <div className="flex-1 min-w-[12rem]">
          <label className="label" htmlFor="q">
            Search
          </label>
          <input
            id="q"
            className="field"
            placeholder="Officer, action or reference"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>
        <div>
          <label className="label" htmlFor="r">
            Role
          </label>
          <select id="r" className="field" value={role} onChange={(e) => setRole(e.target.value)}>
            <option value="">All</option>
            <option value="institution">Institution</option>
            <option value="officer">Officer</option>
            <option value="admin">Administrator</option>
          </select>
        </div>
        <div>
          <label className="label" htmlFor="fr">
            Date from
          </label>
          <input
            id="fr"
            type="date"
            className="field"
            value={from}
            onChange={(e) => setFrom(e.target.value)}
          />
        </div>
      </Filters>
      <DataTable className="gov-table">
        <thead>
          <tr>
            <th>Timestamp</th>
            <th>Performed By</th>
            <th>Role</th>
            <th>Action</th>
            <th>Reference</th>
          </tr>
        </thead>
        <tbody>
          {list.length === 0 ? (
            <EmptyRow cols={5} />
          ) : (
            list.map((a) => (
              <tr key={a.id}>
                <td className="whitespace-nowrap">{a.at}</td>
                <td>{a.actor}</td>
                <td className="capitalize">{a.role}</td>
                <td>{a.action}</td>
                <td>{a.ref}</td>
              </tr>
            ))
          )}
        </tbody>
      </DataTable>
    </InnerPage>
  );
}
