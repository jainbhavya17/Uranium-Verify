import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { CasePage } from "@/components/app-flow";
import { Panel } from "@/components/portal";
import { actions, useCurrentUser } from "@/lib/store";
import type { Application } from "@/lib/data";
import { seo } from "@/lib/seo";

export const Route = createFileRoute("/officer/cases/$id/inspection")({
  head: seo(
    "Inspection Report",
    "Record the physical or online inspection report for the institution.",
  ),
  component: Page,
});

function Page() {
  const { id } = Route.useParams();
  return (
    <CasePage id={id} step="inspection">
      {(a) => <Form a={a} />}
    </CasePage>
  );
}

function Form({ a }: { a: Application }) {
  const user = useCurrentUser();
  const [ins, setIns] = useState(
    a.inspection ?? {
      date: "",
      inspector: user?.name ?? "",
      observations: "",
      recommendation: "Satisfactory",
    },
  );
  const [msg, setMsg] = useState("");
  const locked = a.status === "Approved" || a.status === "Rejected";
  return (
    <Panel title="Inspection Report">
      {a.inspection && (
        <p className="text-sm mb-3">
          Last recorded by {a.inspection.inspector} for inspection on {a.inspection.date}.
        </p>
      )}
      <form
        className="grid gap-4 sm:grid-cols-2"
        onSubmit={(e) => {
          e.preventDefault();
          actions.saveInspection(a.id, ins);
          setMsg("Inspection report recorded.");
        }}
      >
        <div>
          <label className="label" htmlFor="dt">
            Date of Inspection
          </label>
          <input
            id="dt"
            type="date"
            className="field"
            value={ins.date}
            disabled={locked}
            required
            onChange={(e) => setIns({ ...ins, date: e.target.value })}
          />
        </div>
        <div>
          <label className="label" htmlFor="ip">
            Inspecting Officer
          </label>
          <input
            id="ip"
            className="field"
            value={ins.inspector}
            disabled={locked}
            required
            onChange={(e) => setIns({ ...ins, inspector: e.target.value })}
          />
        </div>
        <div className="sm:col-span-2">
          <label className="label" htmlFor="ob">
            Observations
          </label>
          <textarea
            id="ob"
            rows={5}
            className="field"
            value={ins.observations}
            disabled={locked}
            required
            onChange={(e) => setIns({ ...ins, observations: e.target.value })}
          />
        </div>
        <div>
          <label className="label" htmlFor="rc">
            Recommendation
          </label>
          <select
            id="rc"
            className="field"
            value={ins.recommendation}
            disabled={locked}
            onChange={(e) => setIns({ ...ins, recommendation: e.target.value })}
          >
            <option>Satisfactory</option>
            <option>Satisfactory with conditions</option>
            <option>Not satisfactory</option>
          </select>
        </div>
        {!locked && (
          <div className="sm:col-span-2">
            <button className="btn btn-primary">Save Inspection Report</button>
            {msg && (
              <span className="ml-3 text-sm text-success" role="status">
                {msg}
              </span>
            )}
          </div>
        )}
      </form>
    </Panel>
  );
}
