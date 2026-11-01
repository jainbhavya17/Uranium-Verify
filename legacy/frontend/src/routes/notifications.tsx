import { DataTable } from "@/components/portal";
import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { InnerPage, EmptyRow, Filters } from "@/components/portal";
import { Link } from "@/components/link";
import { actions, useCurrentUser, useStore } from "@/lib/store";
import { seo } from "@/lib/seo";

export const Route = createFileRoute("/notifications")({
  head: seo("Notifications", "Portal notices, circulars and application alerts."),
  component: Notifications,
});

function Notifications() {
  const user = useCurrentUser();
  const all = useStore((s) => s.notifications);
  const [q, setQ] = useState("");
  const list = all
    .filter(
      (n) =>
        n.role === "public" ||
        (user &&
          n.role === user.role &&
          (!n.institutionId || n.institutionId === user.institutionId)),
    )
    .filter((n) => n.text.toLowerCase().includes(q.toLowerCase()));
  return (
    <InnerPage crumbs={[{ label: "Notifications" }]} title="Notifications & Circulars">
      <p className="workspace-note mb-4">
        Personal workspace alerts and legacy sample circulars.{" "}
        <Link className="link" to="/notices">
          View current published portal notices →
        </Link>
      </p>
      <Filters>
        <div className="flex-1 min-w-[14rem]">
          <label className="label" htmlFor="nq">
            Search
          </label>
          <input id="nq" className="field" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
      </Filters>
      <DataTable className="gov-table">
        <thead>
          <tr>
            <th className="w-28">Date</th>
            <th className="w-28">Category</th>
            <th>Subject</th>
            <th className="w-28">Status</th>
          </tr>
        </thead>
        <tbody>
          {list.length === 0 ? (
            <EmptyRow cols={4} />
          ) : (
            list.map((n) => (
              <tr key={n.id} className={n.read ? "" : "font-medium"}>
                <td>{n.at}</td>
                <td>{n.role === "public" ? "Public Notice" : "Alert"}</td>
                <td>
                  {n.link ? (
                    <Link to={n.link} className="link" onClick={() => actions.markRead(n.id)}>
                      {n.text}
                    </Link>
                  ) : (
                    n.text
                  )}
                </td>
                <td>
                  {n.role === "public" ? (
                    "—"
                  ) : n.read ? (
                    "Read"
                  ) : (
                    <button className="link text-xs" onClick={() => actions.markRead(n.id)}>
                      Mark as read
                    </button>
                  )}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </DataTable>
    </InnerPage>
  );
}
