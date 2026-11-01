import { DataTable } from "@/components/portal";
import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { InnerPage, Status, EmptyRow, Filters, instName } from "@/components/portal";
import { Link } from "@/components/link";
import { useStore } from "@/lib/store";
import { institutions } from "@/lib/data";
import { seo } from "@/lib/seo";

export const Route = createFileRoute("/officer/queue")({
  head: seo("Case Queue", "All submitted applications awaiting or under scrutiny."),
  validateSearch: (s: Record<string, unknown>) => ({
    status: typeof s.status === "string" ? s.status : undefined,
  }),
  component: Page,
});

function Page() {
  const init = Route.useSearch();
  const deficiencies = useStore((s) => s.deficiencies);
  const [order, setOrder] = useState("attention");
  const priority = (id: string) => {
    const ds = deficiencies.filter((d) => d.appId === id && d.status !== "Closed");
    const day = new Date().toLocaleDateString("en-CA");
    return ds.some((d) => d.status === "Responded")
      ? { rank: 0, label: "Response ready for review" }
      : ds.some((d) => d.dueOn < day)
        ? { rank: 1, label: "Response overdue" }
        : ds.length
          ? { rank: 3, label: "Awaiting institution" }
          : { rank: 2, label: "Continue scrutiny" };
  };
  const apps = useStore((s) => s.applications.filter((a) => a.status !== "Draft"));
  const [q, setQ] = useState("");
  const [st, setSt] = useState(init.status ?? "");
  const [inst, setInst] = useState("");
  const [from, setFrom] = useState("");
  const list = apps
    .filter(
      (a) =>
        (!st || a.status === st) &&
        (!inst || a.institutionId === inst) &&
        (!from || (a.submittedOn ?? "") >= from) &&
        `${a.ref} ${a.details.course} ${instName(a.institutionId)}`
          .toLowerCase()
          .includes(q.toLowerCase()),
    )
    .sort((a, b) =>
      order === "attention"
        ? Number(!!a.decision) - Number(!!b.decision) ||
          priority(a.id).rank - priority(b.id).rank ||
          (a.submittedOn ?? "").localeCompare(b.submittedOn ?? "")
        : (a.submittedOn ?? "").localeCompare(b.submittedOn ?? ""),
    );
  return (
    <InnerPage role="officer" crumbs={[{ label: "Case Queue" }]} title="Case Queue">
      <Filters>
        <div className="flex-1 min-w-[12rem]">
          <label className="label" htmlFor="q">
            Search
          </label>
          <input
            id="q"
            className="field"
            placeholder="Application ID, course, institution"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>
        <div>
          <label className="label" htmlFor="st">
            Status
          </label>
          <select id="st" className="field" value={st} onChange={(e) => setSt(e.target.value)}>
            <option value="">All</option>
            {["Submitted", "Under Scrutiny", "Deficiency Raised", "Approved", "Rejected"].map(
              (s) => (
                <option key={s}>{s}</option>
              ),
            )}
          </select>
        </div>
        <div>
          <label className="label" htmlFor="in">
            Institution
          </label>
          <select id="in" className="field" value={inst} onChange={(e) => setInst(e.target.value)}>
            <option value="">All</option>
            {institutions.map((i) => (
              <option key={i.id} value={i.id}>
                {i.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="label" htmlFor="fr">
            Submitted from
          </label>
          <input
            id="fr"
            type="date"
            className="field"
            value={from}
            onChange={(e) => setFrom(e.target.value)}
          />
        </div>
        <div>
          <label className="label" htmlFor="queue-order">
            Work order
          </label>
          <select
            id="queue-order"
            className="field"
            value={order}
            onChange={(e) => setOrder(e.target.value)}
          >
            <option value="attention">Needs attention first</option>
            <option value="oldest">Oldest submission first</option>
          </select>
        </div>
      </Filters>
      <p className="workspace-note mb-4">
        Work order uses response status and due dates, with oldest submissions first on ties. This
        is a workflow aid, not an automated decision or risk score.
      </p>
      <div className="overflow-x-auto">
        <DataTable className="gov-table">
          <thead>
            <tr>
              <th>Application ID</th>
              <th>Institution</th>
              <th>Type</th>
              <th>Course</th>
              <th>Intake</th>
              <th>Submitted</th>
              <th>Next attention</th>
              <th>Officer</th>
              <th>Status</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {list.length === 0 ? (
              <EmptyRow cols={10} />
            ) : (
              list.map((a) => (
                <tr key={a.id}>
                  <td className="whitespace-nowrap">{a.ref}</td>
                  <td>{instName(a.institutionId)}</td>
                  <td>{a.type}</td>
                  <td>{a.details.course}</td>
                  <td>{a.details.intake}</td>
                  <td>{a.submittedOn}</td>
                  <td>{a.decision ? "Review complete" : priority(a.id).label}</td>
                  <td>{a.assignedOfficer ?? "—"}</td>
                  <td>
                    <Status s={a.status} />
                  </td>
                  <td>
                    <Link to={`/officer/cases/${a.id}/overview`} className="link">
                      Open
                    </Link>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </DataTable>
      </div>
    </InnerPage>
  );
}
