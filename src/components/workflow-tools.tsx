import { useState } from "react";
import {
  ArrowRight,
  CheckCircle2,
  ClipboardCheck,
  Download,
  History,
  AlertCircle,
} from "lucide-react";
import { Panel } from "./portal";
import { Link } from "./link";
import { actions, precheckFingerprint, readiness, useStore } from "@/lib/store";
import type { Application, Doc } from "@/lib/data";

export function ReadinessPanel({ application: a }: { application: Application }) {
  const rules = useStore((s) => s.rules);
  const [message, setMessage] = useState("");
  const result = readiness(a, rules);
  const stale = !!a.precheck && a.precheck.fingerprint !== precheckFingerprint(a, rules);
  return (
    <Panel title="A clear view before you submit">
      <div className={`readiness-banner ${result.blocking.length ? "needs-work" : "is-ready"}`}>
        <span>
          {result.blocking.length ? <AlertCircle size={24} /> : <CheckCircle2 size={24} />}
        </span>
        <div>
          <h3>
            {result.blocking.length
              ? `${result.blocking.length} thing${result.blocking.length === 1 ? "" : "s"} to complete`
              : "Ready for a sample submission"}
          </h3>
          <p>Completeness checks help you prepare. They do not constitute AICTE approval.</p>
        </div>
      </div>
      {result.blocking.length > 0 && (
        <ul className="readiness-issues">
          {result.blocking.map((b) => (
            <li key={b.text}>
              <span>{b.text}</span>
              <Link className="link" to={`/institution/applications/${a.id}/${b.step}`}>
                Fix this <ArrowRight size={14} />
              </Link>
            </li>
          ))}
        </ul>
      )}
      {result.advisory.length > 0 && (
        <div className="readiness-advisory">
          <h3>For your attention</h3>
          <p>These sample rule findings need officer review:</p>
          <ul>
            {result.advisory.map((t) => (
              <li key={t}>{t}</li>
            ))}
          </ul>
        </div>
      )}
      {a.status === "Draft" && (
        <div className="readiness-save">
          <button
            className="btn btn-outline"
            onClick={() => {
              actions.savePrecheck(a.id);
              setMessage("Readiness check saved.");
            }}
          >
            <ClipboardCheck size={16} />
            Save readiness check
          </button>
          <span role="status">
            {message ||
              (a.precheck
                ? `${stale ? "Changes since last check · " : "Last saved · "}${a.precheck.checkedOn}`
                : "No saved check yet")}
          </span>
        </div>
      )}
    </Panel>
  );
}
export function EvidenceVersions({ docs }: { docs: Doc[] }) {
  return (
    <Panel title="Evidence history">
      <p className="workspace-note">
        <History size={15} />
        Local metadata only. Original PDF bytes, signatures, and OCR results are not stored or
        verified here.
      </p>
      <div className="evidence-version-list">
        {docs
          .filter((d) => d.fileName || d.versions?.length)
          .map((d) => (
            <details key={d.code}>
              <summary>
                {d.code} · {d.name}
                <span>
                  {d.versions?.length ?? 1} version{(d.versions?.length ?? 1) === 1 ? "" : "s"} ·{" "}
                  {d.fileName ? "Attached" : "Removed"}
                </span>
              </summary>
              <ol>
                {(d.versions?.length
                  ? d.versions
                  : [
                      {
                        number: 1,
                        fileName: d.fileName!,
                        recordedOn: d.uploadedOn ?? "Not recorded",
                        actor: "Existing MVP record",
                      },
                    ]
                ).map((v) => (
                  <li key={v.number}>
                    <b>v{v.number}</b>
                    <span>
                      {v.fileName}
                      <small>
                        {v.actor} · {v.recordedOn}
                      </small>
                    </span>
                  </li>
                ))}
              </ol>
            </details>
          ))}
        {!docs.some((d) => d.fileName || d.versions?.length) && (
          <p className="workspace-note">
            No document metadata recorded yet. Attach a PDF to begin.
          </p>
        )}
      </div>
    </Panel>
  );
}
export function ReviewSnapshots({ appId }: { appId?: string }) {
  const reports = useStore((s) => s.reviewReports.filter((r) => !appId || r.appId === appId));
  const [message, setMessage] = useState("");
  const download = (id: string, ref: string) => {
    const data = actions.exportReviewReport(id);
    const url = URL.createObjectURL(new Blob([data], { type: "application/json" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `${ref.replaceAll("/", "-")}-review.json`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    setMessage("Review snapshot downloaded as JSON.");
  };
  return (
    <Panel title="Saved review snapshots">
      <div className="snapshot-intro">
        <p>
          Capture the evidence, findings, and rule results as they stand. Later edits do not replace
          an existing snapshot.
        </p>
        {appId && (
          <button
            className="btn btn-primary"
            onClick={() => {
              actions.createReviewReport(appId);
              setMessage("Review snapshot saved.");
            }}
          >
            Create snapshot
          </button>
        )}
      </div>
      <p className="workspace-note">
        Officer-only local reports. These are editable browser data, not certified or tamper-proof
        records.
      </p>
      <p role="status" className="workflow-feedback">
        {message}
      </p>
      {reports.length ? (
        <div className="snapshot-list">
          {reports.map((r) => (
            <article key={r.id}>
              <div>
                <b>{r.reference}</b>
                <p>
                  {r.createdBy} · {r.createdOn}
                </p>
                <small>
                  {r.application.status} · {r.checks.filter((c) => c.pass).length}/{r.checks.length}{" "}
                  sample checks pass
                </small>
              </div>
              <button className="btn btn-outline" onClick={() => download(r.id, r.reference)}>
                <Download size={15} />
                Download JSON
              </button>
            </article>
          ))}
        </div>
      ) : (
        <div className="table-empty">
          <ClipboardCheck size={26} />
          <b>No snapshots yet</b>
          <span>Open a case’s Review & Decision stage to capture its current review.</span>
        </div>
      )}
    </Panel>
  );
}
