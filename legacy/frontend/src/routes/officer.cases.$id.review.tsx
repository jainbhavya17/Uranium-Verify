import { DataTable } from "@/components/portal";
import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { CasePage } from "@/components/app-flow";
import { Panel, Status } from "@/components/portal";
import { actions, evaluateRules, useStore } from "@/lib/store";
import type { Application } from "@/lib/data";
import { ReviewSnapshots } from "@/components/workflow-tools";
import { seo } from "@/lib/seo";

export const Route = createFileRoute("/officer/cases/$id/review")({
  head: seo(
    "Review & Decision",
    "Raise deficiencies, re-verify responses and record the final decision.",
  ),
  component: Page,
});

function Page() {
  const { id } = Route.useParams();
  return (
    <CasePage id={id} step="review">
      {(a) => <Review a={a} />}
    </CasePage>
  );
}

function Review({ a }: { a: Application }) {
  const defs = useStore((s) => s.deficiencies.filter((d) => d.appId === a.id));
  const rules = useStore((s) => s.rules);
  const [cat, setCat] = useState("Infrastructure");
  const [desc, setDesc] = useState("");
  const [dec, setDec] = useState<"Approved" | "Rejected">("Approved");
  const [reason, setReason] = useState("");
  const [close, setClose] = useState<Record<string, string>>({});
  const fails = evaluateRules(a, rules).filter((r) => !r.pass).length;
  const open = defs.filter((d) => d.status !== "Closed").length;
  const decided = !!a.decision;
  const approvalBlocked =
    fails > 0 || a.documents.some((d) => d.mandatory && d.status !== "Verified");
  return (
    <div className="space-y-5">
      <Panel title="Scrutiny Summary">
        <dl className="dl">
          <dt>Compliance</dt>
          <dd>{fails} rule(s) not satisfied</dd>
          <dt>Documents</dt>
          <dd>
            {a.documents.filter((d) => d.status === "Verified").length} verified,{" "}
            {a.documents.filter((d) => d.status === "Mismatch Found").length} mismatch,{" "}
            {a.documents.filter((d) => d.status === "Under Review").length} under review
          </dd>
          <dt>Inspection</dt>
          <dd>
            {a.inspection
              ? `${a.inspection.recommendation} (${a.inspection.inspector}, ${a.inspection.date})`
              : "Not recorded"}
          </dd>
          <dt>Open Deficiencies</dt>
          <dd>{open}</dd>
        </dl>
      </Panel>
      <Panel title="Deficiency Notices">
        <DataTable className="gov-table">
          <thead>
            <tr>
              <th>Notice</th>
              <th>Description</th>
              <th>Response</th>
              <th>Status</th>
              <th>Re-verification</th>
            </tr>
          </thead>
          <tbody>
            {defs.length === 0 ? (
              <tr>
                <td colSpan={5} className="text-center text-muted-foreground py-4">
                  No records found
                </td>
              </tr>
            ) : (
              defs.map((d) => (
                <tr key={d.id}>
                  <td>
                    {d.id}
                    <div className="text-xs text-muted-foreground">
                      {d.category} · {d.raisedBy}, {d.raisedOn}
                    </div>
                  </td>
                  <td className="max-w-xs">{d.description}</td>
                  <td className="max-w-xs">{d.response ?? "Awaited"}</td>
                  <td>
                    <Status s={d.status} />
                  </td>
                  <td>
                    {d.status === "Responded" ? (
                      <form
                        className="space-y-1"
                        onSubmit={(e) => {
                          e.preventDefault();
                          actions.closeDeficiency(d.id, close[d.id]);
                        }}
                      >
                        <label className="sr-only" htmlFor={`c-${d.id}`}>
                          Closure remark
                        </label>
                        <input
                          id={`c-${d.id}`}
                          className="field"
                          placeholder="Re-verification remark"
                          required
                          value={close[d.id] ?? ""}
                          onChange={(e) => setClose({ ...close, [d.id]: e.target.value })}
                        />
                        <button className="btn btn-primary text-xs">Re-verify &amp; Close</button>
                      </form>
                    ) : d.status === "Closed" ? (
                      <span className="text-xs">
                        {d.closeRemark}
                        <br />
                        {d.closedBy}, {d.closedOn}
                      </span>
                    ) : (
                      "Awaiting institution"
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </DataTable>
        {!decided && (
          <form
            className="mt-4 grid gap-3 sm:grid-cols-4 items-end"
            onSubmit={(e) => {
              e.preventDefault();
              actions.raiseDeficiency(a.id, cat, desc);
              setDesc("");
            }}
          >
            <div>
              <label className="label" htmlFor="cat">
                Category
              </label>
              <select
                id="cat"
                className="field"
                value={cat}
                onChange={(e) => setCat(e.target.value)}
              >
                {["Infrastructure", "Faculty", "Documentation", "Financial", "Land"].map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </select>
            </div>
            <div className="sm:col-span-2">
              <label className="label" htmlFor="desc">
                Deficiency Description
              </label>
              <input
                id="desc"
                className="field"
                value={desc}
                required
                minLength={15}
                onChange={(e) => setDesc(e.target.value)}
              />
            </div>
            <button className="btn btn-danger" disabled={a.status === "Submitted"}>
              Raise Deficiency
            </button>
          </form>
        )}
      </Panel>
      <Panel title="Final Decision">
        {decided ? (
          <dl className="dl">
            <dt>Decision</dt>
            <dd>
              <Status s={a.decision!.decision} />
            </dd>
            <dt>Deciding Officer</dt>
            <dd>{a.decision!.officer}</dd>
            <dt>Date</dt>
            <dd>{a.decision!.at}</dd>
            <dt>Reason Recorded</dt>
            <dd>{a.decision!.reason}</dd>
          </dl>
        ) : (
          <form
            className="space-y-3"
            onSubmit={(e) => {
              e.preventDefault();
              actions.decide(a.id, dec, reason);
            }}
          >
            {open > 0 && (
              <div className="notice">
                A decision cannot be recorded while {open} deficiency notice(s) remain open.
              </div>
            )}
            {a.status === "Submitted" && (
              <div className="notice">
                Take up the case for scrutiny from the Overview step before recording a decision.
              </div>
            )}
            {dec === "Approved" && approvalBlocked && (
              <div className="notice">
                Approval needs all active sample rules to pass and every mandatory document to be
                verified. Record the remaining findings before approving.
              </div>
            )}
            <fieldset className="flex gap-6 text-sm">
              <legend className="label">Decision</legend>
              <label className="flex gap-2">
                <input
                  type="radio"
                  checked={dec === "Approved"}
                  onChange={() => setDec("Approved")}
                />{" "}
                Approve
              </label>
              <label className="flex gap-2">
                <input
                  type="radio"
                  checked={dec === "Rejected"}
                  onChange={() => setDec("Rejected")}
                />{" "}
                Reject
              </label>
            </fieldset>
            <div>
              <label className="label" htmlFor="rs">
                Reason for Decision (mandatory)
              </label>
              <textarea
                id="rs"
                rows={4}
                className="field"
                value={reason}
                required
                minLength={20}
                onChange={(e) => setReason(e.target.value)}
              />
            </div>
            <button
              className="btn btn-primary"
              disabled={
                open > 0 || a.status === "Submitted" || (dec === "Approved" && approvalBlocked)
              }
            >
              Record Decision
            </button>
          </form>
        )}
      </Panel>
      <ReviewSnapshots appId={a.id} />
    </div>
  );
}
