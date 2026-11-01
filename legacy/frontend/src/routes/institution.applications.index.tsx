import { DataTable } from "@/components/portal";
import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { InnerPage, Status, EmptyRow, Filters } from "@/components/portal";
import { Link } from "@/components/link";
import { useCurrentUser, useStore } from "@/lib/store";
import { seo } from "@/lib/seo";

export const Route = createFileRoute("/institution/applications/")({
  head: seo("My Applications", "All applications submitted or drafted by your institution."),
  validateSearch: (s: Record<string, unknown>) => ({
    status: typeof s.status === "string" ? s.status : undefined,
  }),
  component: List,
});

const STATUSES = [
  "Draft",
  "Submitted",
  "Under Scrutiny",
  "Deficiency Raised",
  "Approved",
  "Rejected",
];

function List() {
  const user = useCurrentUser();
  const init = Route.useSearch();
  const apps = useStore((s) =>
    s.applications.filter((a) => a.institutionId === user?.institutionId),
  );
  const [q, setQ] = useState("");
  const [st, setSt] = useState(init.status ?? "");
  const [from, setFrom] = useState("");
  const list = apps.filter(
    (a) =>
      (!st || a.status === st) &&
      (!from || (a.submittedOn ?? a.createdOn) >= from) &&
      `${a.ref} ${a.type} ${a.details.course}`.toLowerCase().includes(q.toLowerCase()),
  );
  return (
    <InnerPage
      role="institution"
      crumbs={[{ label: "My Applications" }]}
      title="My Applications"
      actions={
        <Link to="/institution/applications/new" className="btn btn-primary">
          New Application
        </Link>
      }
    >
      <Filters>
        <div className="flex-1 min-w-[12rem]">
          <label className="label" htmlFor="q">
            Search
          </label>
          <input
            id="q"
            className="field"
            placeholder="Application ID, type or course"
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
            {STATUSES.map((s) => (
              <option key={s}>{s}</option>
            ))}
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
        <button
          className="btn btn-outline"
          onClick={() => {
            setQ("");
            setSt("");
            setFrom("");
          }}
        >
          Reset
        </button>
      </Filters>
      <div className="overflow-x-auto">
        <DataTable className="gov-table">
          <thead>
            <tr>
              <th>Application ID</th>
              <th>Type</th>
              <th>Course / Programme</th>
              <th>Intake</th>
              <th>AY</th>
              <th>Submitted</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {list.length === 0 ? (
              <EmptyRow cols={8} />
            ) : (
              list.map((a) => (
                <tr key={a.id}>
                  <td>{a.ref}</td>
                  <td>{a.type}</td>
                  <td>
                    {a.details.course || "—"}
                    <div className="text-xs text-muted-foreground">{a.details.programme}</div>
                  </td>
                  <td>{a.details.intake}</td>
                  <td>{a.details.academicYear}</td>
                  <td>{a.submittedOn ?? "—"}</td>
                  <td>
                    <Status s={a.status} />
                  </td>
                  <td className="space-x-2 whitespace-nowrap">
                    {a.status === "Draft" ? (
                      <Link to={`/institution/applications/${a.id}/details`} className="link">
                        Continue
                      </Link>
                    ) : (
                      <>
                        <Link to={`/institution/applications/${a.id}/status`} className="link">
                          Status
                        </Link>
                        <Link to={`/institution/records/${a.id}`} className="link">
                          Record
                        </Link>
                      </>
                    )}
                    <Link to={`/institution/applications/${a.id}/history`} className="link">
                      History
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
