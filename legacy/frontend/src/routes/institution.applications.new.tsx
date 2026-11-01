import { DataTable } from "@/components/portal";
import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { InnerPage, Panel } from "@/components/portal";
import { useGo } from "@/components/link";
import { actions } from "@/lib/store";
import { APP_TYPES } from "@/lib/data";
import { seo } from "@/lib/seo";

export const Route = createFileRoute("/institution/applications/new")({
  head: seo(
    "Choose Application Type",
    "Step 1 of a new AICTE application: select the type of approval sought.",
  ),
  component: NewApp,
});

function NewApp() {
  const go = useGo();
  const [t, setT] = useState("");
  return (
    <InnerPage
      role="institution"
      crumbs={[
        { label: "My Applications", to: "/institution/applications" },
        { label: "Choose Application Type" },
      ]}
      title="Step 1: Choose Application Type"
    >
      <Panel title="Type of Approval Sought">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const id = actions.createApp(APP_TYPES.find((x) => x.code === t)!.name);
            go(`/institution/applications/${id}/details`);
          }}
        >
          <DataTable className="gov-table">
            <thead>
              <tr>
                <th className="w-12">Select</th>
                <th>Application Type</th>
                <th>Description</th>
              </tr>
            </thead>
            <tbody>
              {APP_TYPES.map((a) => (
                <tr key={a.code} className="cursor-pointer" onClick={() => setT(a.code)}>
                  <td>
                    <input
                      type="radio"
                      name="type"
                      aria-label={a.name}
                      checked={t === a.code}
                      onChange={() => setT(a.code)}
                    />
                  </td>
                  <td className="font-medium">{a.name}</td>
                  <td>{a.desc}</td>
                </tr>
              ))}
            </tbody>
          </DataTable>
          <div className="flex justify-end mt-4">
            <button className="btn btn-primary" disabled={!t}>
              Create Draft &amp; Continue &rarr;
            </button>
          </div>
        </form>
      </Panel>
    </InnerPage>
  );
}
