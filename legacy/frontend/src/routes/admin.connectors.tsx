import { DataTable } from "@/components/portal";
import { createFileRoute } from "@tanstack/react-router";
import { InnerPage, Status } from "@/components/portal";
import { actions, useStore } from "@/lib/store";
import { seo } from "@/lib/seo";

export const Route = createFileRoute("/admin/connectors")({
  head: seo("Connectors", "External registries used for document authentication."),
  component: Page,
});

function Page() {
  const cs = useStore((s) => s.connectors);
  return (
    <InnerPage
      role="admin"
      crumbs={[{ label: "Administration" }, { label: "Connectors" }]}
      title="Connectors"
    >
      <p className="notice mb-5">
        Demonstration configurations only. These controls do not connect to registries, synchronize
        records, or authenticate documents.
      </p>
      <DataTable className="gov-table">
        <thead>
          <tr>
            <th>Connector</th>
            <th>Purpose</th>
            <th>Endpoint</th>
            <th>Seeded sync example</th>
            <th>Status</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {cs.map((c) => (
            <tr key={c.id}>
              <td>{c.name}</td>
              <td>{c.purpose}</td>
              <td className="font-mono text-xs">{c.endpoint}</td>
              <td>{c.lastSync}</td>
              <td>
                <Status s={c.status} />
              </td>
              <td>
                <button className="link" onClick={() => actions.toggleConnector(c.id)}>
                  {c.status === "Disabled" ? "Enable locally" : "Disable locally"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </DataTable>
    </InnerPage>
  );
}
