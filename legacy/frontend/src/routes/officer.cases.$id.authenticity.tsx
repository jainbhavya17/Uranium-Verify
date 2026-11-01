import { DataTable } from "@/components/portal";
import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { CasePage } from "@/components/app-flow";
import { Panel, Status } from "@/components/portal";
import { actions, useStore } from "@/lib/store";
import type { Application, Doc, DocStatus } from "@/lib/data";
import { seo } from "@/lib/seo";

export const Route = createFileRoute("/officer/cases/$id/authenticity")({
  head: seo(
    "Document Authenticity",
    "Authenticate each document and record the verification report.",
  ),
  component: Page,
});

function Page() {
  const { id } = Route.useParams();
  return (
    <CasePage id={id} step="authenticity">
      {(a) => (
        <div className="space-y-4">
          {a.documents
            .filter((d) => d.status !== "Not Submitted")
            .map((d) => (
              <DocCheck key={d.code} a={a} d={d} />
            ))}
        </div>
      )}
    </CasePage>
  );
}

function DocCheck({ a, d }: { a: Application; d: Doc }) {
  const connectors = useStore((s) => s.connectors);
  const [st, setSt] = useState<DocStatus>(d.status === "Under Review" ? "Verified" : d.status);
  const [f, setF] = useState(d.findings ?? "");
  const locked = a.status === "Approved" || a.status === "Rejected";
  const reg =
    d.code === "D01"
      ? connectors[1]
      : d.code === "D03"
        ? connectors[4]
        : d.code === "D05"
          ? connectors[3]
          : connectors[0];
  return (
    <Panel title={`${d.code} · ${d.name}`}>
      <p className="workspace-note mb-4">
        Record a human review outcome against sample evidence. This is not automated authentication.
      </p>
      <div className="grid gap-4 lg:grid-cols-2">
        <DataTable className="gov-table">
          <tbody>
            <tr>
              <th>File</th>
              <td>{d.fileName}</td>
            </tr>
            <tr>
              <th>Digital signature</th>
              <td>Not checked — no signature verification service is connected.</td>
            </tr>
            <tr>
              <th>Registry check</th>
              <td>
                {reg.name}: local configuration <Status s={reg.status} />
                <span className="block text-xs text-muted-foreground">
                  No live registry request was made.
                </span>
              </td>
            </tr>
            <tr>
              <th>Current status</th>
              <td>
                <Status s={d.status} />
                {d.checkedBy && (
                  <div className="text-xs text-muted-foreground mt-1">
                    {d.checkedBy}, {d.checkedOn}
                  </div>
                )}
              </td>
            </tr>
          </tbody>
        </DataTable>
        <form
          className="space-y-2"
          onSubmit={(e) => {
            e.preventDefault();
            actions.setDocStatus(a.id, d.code, st, f);
          }}
        >
          <div>
            <label className="label" htmlFor={`s-${d.code}`}>
              Verification Outcome
            </label>
            <select
              id={`s-${d.code}`}
              className="field"
              value={st}
              disabled={locked}
              onChange={(e) => setSt(e.target.value as DocStatus)}
            >
              <option>Verified</option>
              <option>Mismatch Found</option>
              <option>Under Review</option>
            </select>
          </div>
          <div>
            <label className="label" htmlFor={`f-${d.code}`}>
              Findings (Verification Report)
            </label>
            <textarea
              id={`f-${d.code}`}
              rows={3}
              className="field"
              value={f}
              disabled={locked}
              required
              onChange={(e) => setF(e.target.value)}
            />
          </div>
          {!locked && <button className="btn btn-primary">Record Outcome</button>}
        </form>
      </div>
    </Panel>
  );
}
