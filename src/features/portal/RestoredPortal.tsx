import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  Files,
  Clock3,
  FileCheck2,
  MessageSquare,
  CheckCircle2,
  Download,
  Eye,
  ClipboardCheck,
  Building2,
} from "lucide-react";
import { api, type Preview, type User } from "../api";
import { Link } from "@/components/link";
import { Panel, DataTable, MetricCard, Status } from "@/components/portal";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { EvidenceViewer } from "../officer/EvidenceViewer";
import { ScrutinyContent } from "../officer/ScrutinyPages";
import { ReportLibrary, ClarificationResponsePage } from "../release/ReleasePages";
import { useSearchParams, portalPath } from "../navigation";

type PortalDocument = {
  id: string;
  versionId?: string | null;
  version?: number;
  name: string;
  description: string;
  type: string;
  status: string;
  fileName?: string;
  uploadedOn?: number;
  reviewer?: string;
  findings?: string;
  previewable?: boolean;
  mandatory?: boolean;
};
type Answer = {
  id: string;
  explanation: string;
  submittedAt: number;
  receipt: Record<string, unknown>;
  documents: {
    id: string;
    versionId: string;
    version: number;
    fileName: string;
    previewable: boolean;
  }[];
};
type Query = {
  id: string;
  message: string;
  raisedOn: number;
  dueOn: number;
  status: string;
  responses: Answer[];
};
export type PortalApplication = {
  id: string;
  reference: string;
  institution: {
    id: string;
    name: string;
    aicteId: string;
    state?: string;
    city?: string;
    type?: string;
  };
  type: string;
  academicYear: string;
  status: string;
  state: string;
  details: {
    programme?: string;
    course?: string;
    intake?: number;
    landArea?: number;
    builtUpArea?: number;
    facultyCount?: number;
    principal?: string;
    address?: string;
  };
  submittedOn?: string;
  createdOn: string;
  assignedOfficer?: string;
  reviewVersion?: number;
  decision?: { decision: string; reason: string; officer: string; at: string };
  inspection?: { date: string; inspector: string; observations: string; recommendation: string };
  documents: PortalDocument[];
  queries: Query[];
  history: { id: string; action: string; remark: string; at: string; by: string }[];
  actions: { id: string; action: string; reason: string; at: number; by: string }[];
  reports: {
    id: string;
    state: string;
    download_url?: string;
    message?: string;
    payload?: { rationale?: string };
  }[];
  receipt?: {
    acknowledgment: string;
    submitted_at: number;
    document_count: number;
    version: number;
  };
};
const date = (s?: string | number) =>
  s
    ? new Date(typeof s === "number" ? s * 1000 : s).toLocaleDateString("en-IN", {
        day: "numeric",
        month: "short",
        year: "numeric",
      })
    : "Not recorded";
const call = (path: string, body: unknown) =>
  api(path, {
    method: "POST",
    headers: { "Idempotency-Key": crypto.randomUUID() },
    body: JSON.stringify(body),
  });
export function usePortalApplications() {
  return useQuery({
    queryKey: ["portal-applications"],
    queryFn: () => api<PortalApplication[]>("/portal/applications"),
    refetchInterval: 10000,
  });
}
function usePortalCase(id: string) {
  return useQuery({
    queryKey: ["portal-case", id],
    queryFn: () => api<PortalApplication>(`/portal/applications/${id}`),
    refetchInterval: 10000,
  });
}
function Load({ error, retry }: { error?: Error | null; retry: () => void }) {
  return (
    <Card>
      <h2>{error ? "This information could not be loaded" : "Loading your records…"}</h2>
      {error && (
        <>
          <p role="alert">{error.message}</p>
          <Button onClick={retry}>Try again</Button>
        </>
      )}
    </Card>
  );
}
function DocumentBadge({ status }: { status: string }) {
  return (
    <span
      className={`portal-doc-status ${status === "Reviewed" ? "reviewed" : status === "Correction required" ? "correction" : status === "Not uploaded" ? "missing" : "pending"}`}
    >
      {status}
    </span>
  );
}
function AppTable({ items, officer = false }: { items: PortalApplication[]; officer?: boolean }) {
  return (
    <DataTable className="gov-table">
      <caption className="sr-only">Application records</caption>
      <thead>
        <tr>
          <th>Application</th>
          <th>Institution / course</th>
          <th>Request</th>
          <th>Submitted</th>
          <th>Status</th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody>
        {items.map((a) => (
          <tr key={a.id}>
            <td>
              <b>{a.id.startsWith("APP-") ? a.id : a.reference}</b>
              <small className="portal-subline">{a.academicYear}</small>
            </td>
            <td>
              <b>{a.institution.name}</b>
              <small className="portal-subline">
                {a.details.course || "Course details to be completed"}
                {a.details.intake !== undefined ? ` · Intake ${a.details.intake}` : ""}
              </small>
            </td>
            <td>{a.type}</td>
            <td>{a.submittedOn ? date(a.submittedOn) : "Not submitted"}</td>
            <td>
              <Status s={a.status} />
            </td>
            <td>
              <Link
                className="portal-inline-link"
                to={
                  officer
                    ? `/officer/cases/${a.id}/overview`
                    : `/institution/applications/${a.id}/${a.state === "DRAFT" ? "details" : "status"}`
                }
              >
                {officer
                  ? "Review case"
                  : a.state === "DRAFT"
                    ? "Continue draft"
                    : "View application"}
                <ArrowRight size={14} />
              </Link>
            </td>
          </tr>
        ))}
        {!items.length && (
          <tr>
            <td colSpan={6}>No applications match these filters.</td>
          </tr>
        )}
      </tbody>
    </DataTable>
  );
}
export function PortalDashboard({ officer = false }: { officer?: boolean }) {
  const q = usePortalApplications();
  const [selected, setSelected] = useState("");
  const cases = q.data?.data ?? [];
  const institutions = Array.from(
    new Map(cases.map((a) => [a.institution.id, a.institution])).values(),
  );
  const primary =
    selected || (institutions.find((i) => i.id === "INS-1-4412")?.id ?? institutions[0]?.id);
  const list = officer
    ? cases.filter((a) => a.state !== "DRAFT")
    : cases.filter((a) => a.institution.id === primary);
  const counts = {
    draft: list.filter((a) => a.state === "DRAFT").length,
    submitted: list.filter((a) => a.state === "SUBMITTED").length,
    review: list.filter((a) => ["UNDER_REVIEW", "PENDING_VERIFICATION"].includes(a.state)).length,
    deficiency: list.filter((a) => a.state === "CLARIFICATION_REQUESTED").length,
    complete: list.filter((a) => a.state === "REVIEW_COMPLETED").length,
  };
  const allDetails = useQuery({
    queryKey: ["portal-dashboard-details", officer, primary, cases.length],
    queryFn: async () =>
      Promise.all(
        list
          .filter((a) => a.state === "CLARIFICATION_REQUESTED")
          .map((a) => api<PortalApplication>(`/portal/applications/${a.id}`)),
      ),
    enabled: !!q.data,
  });
  const responses = (allDetails.data ?? []).flatMap(
    (r) =>
      r.data.queries
        ?.filter((x) => x.status === "Responded")
        .map((x) => ({ app: r.data, query: x })) ?? [],
  );
  if (q.isPending || q.error) return <Load error={q.error} retry={() => void q.refetch()} />;
  return (
    <>
      {!officer && (
        <Card className="portal-institution-banner">
          <Building2 size={28} />
          <div>
            <span className="eyebrow">YOUR INSTITUTION</span>
            <h2>{institutions.find((i) => i.id === primary)?.name}</h2>
            <p>
              Permanent ID {institutions.find((i) => i.id === primary)?.aicteId} ·{" "}
              {institutions.find((i) => i.id === primary)?.city || "Institution profile"}
            </p>
          </div>
          {institutions.length > 1 && (
            <label className="field">
              Institution
              <select value={primary} onChange={(e) => setSelected(e.target.value)}>
                {institutions.map((i) => (
                  <option key={i.id} value={i.id}>
                    {i.name}
                  </option>
                ))}
              </select>
            </label>
          )}
        </Card>
      )}
      <div className="metrics-grid portal-metrics">
        <MetricCard
          label={officer ? "New submissions" : "Applications"}
          value={officer ? counts.submitted : list.length}
          hint={officer ? "Ready to take up" : "Open your applications"}
          icon={Files}
          to={officer ? "/officer/queue" : "/institution/applications"}
          search={officer ? { status: "Submitted" } : undefined}
          tone="teal"
        />
        <MetricCard
          label={officer ? "Under scrutiny" : "Drafts to complete"}
          value={officer ? counts.review : counts.draft}
          hint={officer ? "Continue case review" : "Resume your preparation"}
          icon={Clock3}
          to={officer ? "/officer/queue" : "/institution/applications"}
          search={{ status: officer ? "Under Scrutiny" : "Draft" }}
          tone="blue"
        />
        <MetricCard
          label="Clarifications"
          value={counts.deficiency}
          hint={officer ? "Check pending responses" : "Review the officer’s requests"}
          icon={MessageSquare}
          to={officer ? "/officer/queue" : "/institution/deficiencies"}
          tone="amber"
        />
        <MetricCard
          label={officer ? "Responses received" : "Reviews completed"}
          value={officer ? responses.length : counts.complete}
          hint={officer ? "Ready for re-verification" : "View recorded outcomes"}
          icon={officer ? FileCheck2 : CheckCircle2}
          to={officer ? "/officer/queue" : "/institution/applications"}
          search={{ status: officer ? "Deficiency Raised" : "Approved" }}
          tone="purple"
        />
      </div>
      <div className="dashboard-split">
        <div className="space-y-6">
          <Panel title={officer ? "Cases assigned to you" : "Your applications"}>
            <AppTable items={list} officer={officer} />
          </Panel>
          {officer && (
            <Panel title="Responses awaiting re-verification">
              {responses.length ? (
                responses.map(({ app, query }) => (
                  <article className="portal-response-preview" key={query.id}>
                    <div>
                      <b>
                        {query.id} · {app.id}
                      </b>
                      <p>{query.responses[0]?.explanation}</p>
                      <small>
                        {query.responses[0]?.documents.length ?? 0} supporting document(s)
                      </small>
                    </div>
                    <Link className="btn btn-outline" to={`/officer/cases/${app.id}/review`}>
                      Review response <ArrowRight size={14} />
                    </Link>
                  </article>
                ))
              ) : (
                <p>No submitted responses are awaiting review.</p>
              )}
            </Panel>
          )}
        </div>
        <div className="space-y-6">
          <Panel title={officer ? "Review pipeline" : "At a glance"}>
            {[
              ["Submitted", counts.submitted],
              ["Under scrutiny", counts.review],
              ["Clarification requested", counts.deficiency],
              ["Review completed", counts.complete],
            ].map(([name, count]) => (
              <div className="portal-pipeline-row" key={name}>
                <span>{name}</span>
                <b>{count}</b>
                <div>
                  <i
                    style={{ width: `${list.length ? (Number(count) / list.length) * 100 : 0}%` }}
                  />
                </div>
              </div>
            ))}
          </Panel>
          <Panel title="Your next step">
            <p>
              {officer
                ? "Open a case to review institution details, supporting documents, clarifications and reports."
                : "Continue a draft or start an application. Your checklist will follow the selected application type and the information you provide."}
            </p>
            <Link
              className="btn btn-primary"
              to={officer ? "/officer/queue" : "/institution/applications/new"}
            >
              {officer ? "Open case queue" : "Start application"}
              <ArrowRight size={15} />
            </Link>
          </Panel>
        </div>
      </div>
    </>
  );
}
export function PortalApplications({ officer = false }: { officer?: boolean }) {
  const q = usePortalApplications();
  const [params] = useSearchParams();
  const [search, setSearch] = useState(""),
    [status, setStatus] = useState(params.get("status") ?? ""),
    [type, setType] = useState(""),
    [institution, setInstitution] = useState("");
  if (q.isPending || q.error) return <Load error={q.error} retry={() => void q.refetch()} />;
  const items = q.data.data.filter(
    (a) =>
      (!officer || a.state !== "DRAFT") &&
      (!status || a.status === status) &&
      (!type || a.type === type) &&
      (!institution || a.institution.id === institution) &&
      `${a.id} ${a.reference} ${a.institution.name} ${a.details.course}`
        .toLowerCase()
        .includes(search.toLowerCase()),
  );
  return (
    <>
      <Card>
        <div className="portal-filter-grid">
          <label className="field">
            Search application or institution
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Application ID, course or institution"
            />
          </label>
          <label className="field">
            Status
            <select value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="">All statuses</option>
              {Array.from(new Set(q.data.data.map((a) => a.status))).map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </label>
          <label className="field">
            Application type
            <select value={type} onChange={(e) => setType(e.target.value)}>
              <option value="">All types</option>
              {Array.from(new Set(q.data.data.map((a) => a.type))).map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </label>
          <label className="field">
            Institution
            <select value={institution} onChange={(e) => setInstitution(e.target.value)}>
              <option value="">All your institutions</option>
              {Array.from(
                new Map(q.data.data.map((a) => [a.institution.id, a.institution])).values(),
              ).map((i) => (
                <option key={i.id} value={i.id}>
                  {i.name}
                </option>
              ))}
            </select>
          </label>
        </div>
      </Card>
      <Panel title={`${items.length} application${items.length === 1 ? "" : "s"}`}>
        <AppTable items={items} officer={officer} />
      </Panel>
      {!officer && (
        <div className="form-actions">
          <Link className="btn btn-primary" to="/institution/applications/new">
            New application <ArrowRight size={16} />
          </Link>
        </div>
      )}
    </>
  );
}
function InstitutionDetails({ app }: { app: PortalApplication }) {
  return (
    <Panel title="Institution and application details">
      <dl className="portal-detail-grid">
        {[
          ["Institution", app.institution.name],
          ["Permanent ID", app.institution.aicteId],
          [
            "State / city",
            [app.institution.state, app.institution.city].filter(Boolean).join(" · "),
          ],
          ["Institution type", app.institution.type],
          ["Principal / authorized signatory", app.details.principal],
          ["Campus address", app.details.address],
          ["Application", app.id.startsWith("APP-") ? app.id : app.reference],
          ["Application type", app.type],
          ["Programme", app.details.programme],
          ["Course", app.details.course],
          ["Requested intake", app.details.intake],
          [
            "Land area",
            app.details.landArea !== undefined ? `${app.details.landArea} acres` : undefined,
          ],
          [
            "Built-up area",
            app.details.builtUpArea !== undefined
              ? `${app.details.builtUpArea.toLocaleString("en-IN")} m²`
              : undefined,
          ],
          ["Faculty", app.details.facultyCount],
          ["Academic year", app.academicYear],
          ["Assigned officer", app.assignedOfficer],
        ].map(([name, value]) => (
          <div key={name}>
            <dt>{name}</dt>
            <dd>{value === undefined || value === "" ? "Not recorded" : value}</dd>
          </div>
        ))}
      </dl>
    </Panel>
  );
}
function Answers({ app, officer = false }: { app: PortalApplication; officer?: boolean }) {
  return (
    <Panel title="Clarifications and submitted responses">
      {app.queries?.length ? (
        app.queries.map((q) => (
          <article className="portal-query" key={q.id}>
            <div className="card-heading">
              <h3>{q.id}</h3>
              <Status s={q.status} />
            </div>
            <p>{q.message}</p>
            <p className="portal-subline">
              Raised {date(q.raisedOn)} · Response due {date(q.dueOn)}
            </p>
            {q.responses.length ? (
              q.responses.map((r) => (
                <div className="portal-submitted-response" key={r.id}>
                  <b>Institution response · {date(r.submittedAt)}</b>
                  <p>{r.explanation}</p>
                  {r.documents.map((d) => (
                    <SavedDocument key={d.versionId} doc={d} />
                  ))}
                  {!!r.receipt.acknowledgment && (
                    <small>Acknowledgment {String(r.receipt.acknowledgment)}</small>
                  )}
                </div>
              ))
            ) : (
              <p className="portal-empty-note">
                The institution has not submitted a response to this request yet.
              </p>
            )}
            {officer && q.status === "Responded" && <ResolveResponse app={app} query={q} />}
            {!officer && (
              <Link className="portal-inline-link" to={`/institution/deficiencies/${q.id}/respond`}>
                {q.status === "Open" ? "Prepare response" : "View response and attachments"}
                <ArrowRight size={14} />
              </Link>
            )}
          </article>
        ))
      ) : (
        <p>No clarification requests have been issued for this application.</p>
      )}
    </Panel>
  );
}
function SavedDocument({
  doc,
}: {
  doc: { id: string; version: number; fileName: string; previewable: boolean };
}) {
  const [url, setUrl] = useState(""),
    [error, setError] = useState("");
  return (
    <div className="portal-saved-document">
      <FileCheck2 size={18} />
      <span>
        {doc.fileName} · version {doc.version}
      </span>
      {doc.previewable && (
        <button
          type="button"
          className="portal-inline-link"
          onClick={async () => {
            try {
              const r = await api<Preview>(`/documents/${doc.id}/versions/${doc.version}/preview`, {
                method: "POST",
              });
              setUrl(r.data.url);
              setError("");
            } catch (e) {
              setError((e as Error).message);
            }
          }}
        >
          Open attachment <Eye size={14} />
        </button>
      )}
      {url && (
        <a href={url} target="_blank" rel="noreferrer">
          View document ↗
        </a>
      )}
      {error && <p role="alert">{error}</p>}
    </div>
  );
}
function Documents({ app, officer = false }: { app: PortalApplication; officer?: boolean }) {
  const qc = useQueryClient();
  const [selected, setSelected] = useState<PortalDocument | null>(null),
    [status, setStatus] = useState("Reviewed"),
    [reason, setReason] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  async function save() {
    if (!selected?.versionId) return;
    setBusy(true);
    try {
      await call(`/portal/applications/${app.id}/document-review`, {
        expected_version: app.reviewVersion,
        version_id: selected.versionId,
        status,
        reason,
      });
      setSelected(null);
      setReason("");
      await qc.invalidateQueries({ queryKey: ["portal-case", app.id] });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Panel title="Supporting documents">
        <DataTable className="gov-table">
          <thead>
            <tr>
              <th>Document</th>
              <th>Uploaded file</th>
              <th>Review status</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {app.documents.map((d) => (
              <tr key={d.id}>
                <td>
                  <b>{d.name}</b>
                  <details>
                    <summary>What this document should contain</summary>
                    <p>{d.description}</p>
                  </details>
                  {d.findings && <p className="portal-doc-finding">{d.findings}</p>}
                </td>
                <td>
                  {d.fileName ?? "Not uploaded"}
                  {d.version && (
                    <small className="portal-subline">
                      Version {d.version}
                      {d.reviewer ? ` · ${d.reviewer}` : ""}
                    </small>
                  )}
                </td>
                <td>
                  <DocumentBadge status={d.status} />
                </td>
                <td>
                  {d.versionId && (
                    <SavedDocument
                      doc={{
                        id: d.id,
                        version: d.version!,
                        fileName: "Original document",
                        previewable: !!d.previewable,
                      }}
                    />
                  )}
                  {officer && d.versionId && (
                    <button
                      className="btn btn-outline"
                      onClick={() => {
                        setSelected(d);
                        setError("");
                        setReason(d.findings ?? "");
                      }}
                    >
                      Review document
                    </button>
                  )}
                  {!officer && app.state === "DRAFT" && (
                    <Link
                      className="portal-inline-link"
                      to={`/institution/applications/${app.id}/documents`}
                    >
                      Upload document
                    </Link>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </DataTable>
      </Panel>
      {selected && (
        <Card>
          <h2>Review: {selected.name}</h2>
          <form
            className="form-grid"
            onSubmit={(e) => {
              e.preventDefault();
              void save();
            }}
          >
            <label className="field">
              Review outcome
              <select value={status} onChange={(e) => setStatus(e.target.value)}>
                <option>Reviewed</option>
                <option>Correction required</option>
                <option>Awaiting review</option>
              </select>
            </label>
            <label className="field full-field">
              Review findings
              <textarea
                required
                minLength={10}
                maxLength={2000}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Record what you checked and explain any correction needed."
              />
            </label>
            {error && <p role="alert">{error}</p>}
            <div className="form-actions full-field">
              <Button disabled={busy}>Save document review</Button>
              <Button type="button" variant="outline" onClick={() => setSelected(null)}>
                Cancel
              </Button>
            </div>
          </form>
        </Card>
      )}
    </>
  );
}
function History({ app }: { app: PortalApplication }) {
  return (
    <Panel title="Application history">
      {app.history?.map((e) => (
        <article className="portal-history-row" key={e.id}>
          <span className="audit-dot" />
          <div>
            <b>{e.action}</b>
            <p>{e.remark}</p>
            <small>
              {date(e.at)} · {e.by}
            </small>
          </div>
        </article>
      ))}
      {!app.history?.length && <p>Your saved application activity will appear here.</p>}
    </Panel>
  );
}
function Reports({ app }: { app: PortalApplication }) {
  return (
    <Panel title="Reports and acknowledgment">
      {app.reports?.length ? (
        app.reports.map((r) => (
          <article key={r.id} className="portal-report-row">
            <FileCheck2 size={23} />
            <div>
              <b>Application review report</b>
              <p>{r.message ?? r.payload?.rationale ?? `Review summary for ${app.id}`}</p>
              <small>
                {["READY", "STALE"].includes(r.state)
                  ? r.state === "STALE"
                    ? "Earlier report · newer review activity is available"
                    : "Ready to download"
                  : r.state === "FAILED"
                    ? "Generation needs attention"
                    : "Report generation in progress"}
              </small>
            </div>
            {r.download_url && (
              <a className="btn btn-outline" href={r.download_url}>
                <Download size={15} />
                Download PDF
              </a>
            )}
          </article>
        ))
      ) : (
        <p>
          {app.state === "DRAFT"
            ? "A submission acknowledgment becomes available after you submit."
            : "No report has been published to your institution yet. Your officer will share the permitted review summary."}
        </p>
      )}
      {app.receipt && (
        <a
          className="btn btn-outline"
          href={`/api/v1/applications/${app.id}/acknowledgment`}
          download
        >
          <Download size={15} />
          Download submission acknowledgment
        </a>
      )}
    </Panel>
  );
}
function ReviewActions({ app }: { app: PortalApplication }) {
  const qc = useQueryClient();
  const [action, setAction] = useState("OBSERVATION"),
    [reason, setReason] = useState(""),
    [deadline, setDeadline] = useState(() =>
      new Date(Date.now() + 7 * 86400000).toISOString().slice(0, 10),
    ),
    [document, setDocument] = useState("COMPLETION"),
    [requireDocument, setRequireDocument] = useState(true),
    [error, setError] = useState(""),
    [message, setMessage] = useState(""),
    [busy, setBusy] = useState(false);
  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await call(`/officer/cases/${app.id}/actions`, {
        expected_version: app.reviewVersion,
        action,
        rationale: reason,
        publishable: action !== "OBSERVATION",
        ...(action === "CLARIFICATION"
          ? {
              due_at: Math.floor(new Date(deadline + "T23:59:00").getTime() / 1000),
              allowed_fields: [],
              document_types: [document],
              required_documents: requireDocument ? [document] : [],
            }
          : {}),
      });
      setMessage(
        action === "CLARIFICATION"
          ? "Clarification published. The institution can now respond."
          : "Review action recorded.",
      );
      setReason("");
      await qc.invalidateQueries({ queryKey: ["portal-case", app.id] });
      await qc.invalidateQueries({ queryKey: ["portal-applications"] });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Card>
      <h2>Record your review action</h2>
      <form className="form-grid" onSubmit={save}>
        <label className="field">
          Action
          <select value={action} onChange={(e) => setAction(e.target.value)}>
            <option value="OBSERVATION">Save internal review note</option>
            <option value="CLARIFICATION">Request clarification / correction</option>
            <option value="RECOMMENDATION">Record recommendation</option>
            <option value="COMPLETE">Complete preliminary review</option>
            <option value="REOPEN">Reopen review</option>
          </select>
        </label>
        {action === "CLARIFICATION" && (
          <>
            <label className="field">
              Response deadline
              <input
                type="date"
                required
                value={deadline}
                onChange={(e) => setDeadline(e.target.value)}
              />
            </label>
            <label className="field">
              Supporting document requested
              <select value={document} onChange={(e) => setDocument(e.target.value)}>
                {Array.from(new Map(app.documents.map((d) => [d.type, d])).values()).map((d) => (
                  <option key={d.type} value={d.type}>
                    {d.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="check-field">
              <input
                type="checkbox"
                checked={requireDocument}
                onChange={(e) => setRequireDocument(e.target.checked)}
              />
              A supporting document is required with the response
            </label>
          </>
        )}
        <label className="field full-field">
          Reason / review remarks
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            required
            minLength={10}
            maxLength={2000}
            rows={4}
            placeholder="Explain the finding, correction or recommendation and its supporting evidence."
          />
        </label>
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        {message && (
          <p role="status" className="notice">
            {message}
          </p>
        )}
        <div className="form-actions full-field">
          <Button disabled={busy}>{busy ? "Saving…" : "Record action"}</Button>
          <Button
            type="button"
            variant="outline"
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              try {
                await call(`/officer/cases/${app.id}/reports`, {
                  expected_version: app.reviewVersion,
                  rationale:
                    reason.length >= 10
                      ? reason
                      : `Prepare the current evidence-linked review summary for ${app.id}.`,
                });
                setMessage("Report requested. It will appear here when generation completes.");
                await qc.invalidateQueries({ queryKey: ["portal-case", app.id] });
              } catch (e) {
                setError((e as Error).message);
              } finally {
                setBusy(false);
              }
            }}
          >
            Generate review report
          </Button>
        </div>
      </form>
    </Card>
  );
}
function Inspection({ app }: { app: PortalApplication }) {
  const qc = useQueryClient();
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [message, setMessage] = useState("");
  return (
    <>
      <Panel title="Infrastructure declared by the institution">
        <dl className="portal-detail-grid">
          <div>
            <dt>Campus land</dt>
            <dd>{app.details.landArea ?? "Not recorded"} acres</dd>
          </div>
          <div>
            <dt>Built-up area</dt>
            <dd>{app.details.builtUpArea ?? "Not recorded"} m²</dd>
          </div>
          <div>
            <dt>Requested intake</dt>
            <dd>{app.details.intake ?? "Not recorded"}</dd>
          </div>
        </dl>
      </Panel>
      <Card>
        <h2>Inspection record</h2>
        {app.inspection && (
          <div className="portal-submitted-response">
            <b>
              {date(app.inspection.date)} · {app.inspection.inspector}
            </b>
            <p>{app.inspection.observations}</p>
            <p>{app.inspection.recommendation}</p>
          </div>
        )}
        <form
          className="form-grid"
          onSubmit={async (e) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            setBusy(true);
            try {
              await call(`/portal/applications/${app.id}/inspection`, {
                expected_version: app.reviewVersion,
                date: f.get("date"),
                inspector: f.get("inspector"),
                observations: f.get("observations"),
                recommendation: f.get("recommendation"),
              });
              await qc.invalidateQueries({ queryKey: ["portal-case", app.id] });
              setMessage("Inspection observations saved.");
            } catch (e) {
              setError((e as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          <label className="field">
            Inspection date
            <input name="date" type="date" required defaultValue={app.inspection?.date} />
          </label>
          <label className="field">
            Inspector / reviewing officer
            <input
              name="inspector"
              required
              minLength={3}
              defaultValue={app.inspection?.inspector ?? app.assignedOfficer}
            />
          </label>
          <label className="field full-field">
            Observations
            <textarea
              name="observations"
              required
              minLength={10}
              maxLength={2000}
              defaultValue={app.inspection?.observations}
            />
          </label>
          <label className="field full-field">
            Recommendation
            <textarea
              name="recommendation"
              required
              minLength={5}
              maxLength={2000}
              defaultValue={app.inspection?.recommendation}
            />
          </label>
          {error && <p role="alert">{error}</p>}
          {message && <p role="status">{message}</p>}
          <Button disabled={busy}>Save inspection record</Button>
        </form>
      </Card>
    </>
  );
}
export function PortalCasePage({
  id,
  section = "overview",
  user,
}: {
  id: string;
  section?: string;
  user: User;
}) {
  const q = usePortalCase(id);
  const officer = user.roles.some((r) => ["officer", "supervisor", "specialist"].includes(r));
  if (q.isPending || q.error) return <Load error={q.error} retry={() => void q.refetch()} />;
  const app = q.data.data;
  return (
    <>
      <div className="portal-case-heading">
        <div>
          <span className="eyebrow">{app.id.startsWith("APP-") ? app.id : app.reference}</span>
          <h2>{app.institution.name}</h2>
          <p>
            {app.type} · AY {app.academicYear}
          </p>
        </div>
        <Status s={app.status} />
      </div>
      {section === "overview" && (
        <>
          <div className="portal-summary-cards">
            {[
              [Files, "Application", app.status, "mint"],
              [
                FileCheck2,
                "Documents",
                `${app.documents.filter((d) => d.versionId).length} uploaded`,
                "blue",
              ],
              [
                MessageSquare,
                "Clarifications",
                `${app.queries.filter((q) => q.status !== "Closed").length} active`,
                "peach",
              ],
              [
                CheckCircle2,
                "Reports",
                `${app.reports.filter((r) => ["READY", "STALE"].includes(r.state)).length} ready`,
                "lavender",
              ],
            ].map(([Icon, name, value, tone]) => {
              const Component = Icon as typeof Files;
              return (
                <div key={String(name)} className={`portal-summary-card ${tone}`}>
                  <Component size={22} />
                  <span>{String(name)}</span>
                  <strong>{String(value)}</strong>
                </div>
              );
            })}
          </div>
          <InstitutionDetails app={app} />
          {app.decision && (
            <Panel title="Recorded outcome">
              <Status s={app.decision.decision} />
              <p>{app.decision.reason}</p>
              <small>
                {app.decision.officer} · {date(app.decision.at)}
              </small>
            </Panel>
          )}
          {!officer && <Documents app={app} />}
          <Answers app={app} officer={officer} />
          <Reports app={app} />
          <History app={app} />
        </>
      )}
      {section === "documents" && (
        <>
          <Documents app={app} officer={officer} />
          {officer && (
            <details className="card">
              <summary>Inspect extracted fields and source regions</summary>
              <EvidenceViewer id={app.id} user={user} />
            </details>
          )}
        </>
      )}
      {section === "authenticity" && (
        <>
          <Panel title="Document authentication and review">
            <p>
              Check the original document, the issuing authority and available signature or
              provenance evidence. A recorded document review is separate from an issuer
              confirmation.
            </p>
            <div className="portal-summary-cards">
              <div className="portal-summary-card mint">
                <strong>{app.documents.filter((d) => d.status === "Reviewed").length}</strong>
                <span>Document reviews recorded</span>
              </div>
              <div className="portal-summary-card peach">
                <strong>
                  {app.documents.filter((d) => d.status === "Correction required").length}
                </strong>
                <span>Corrections requested</span>
              </div>
            </div>
          </Panel>
          <Documents app={app} officer />
          <details className="card">
            <summary>Issuer, digital-signature and provenance checks</summary>
            <ScrutinyContent routeId="O05" caseId={id} user={user} />
          </details>
        </>
      )}
      {section === "compliance" && (
        <>
          <Panel title="Preliminary compliance checklist">
            <p>
              Review the institution's supporting documents and outstanding corrections. Rule
              findings must be supported by the applicable provision and evidence.
            </p>
            {app.documents.map((d) => (
              <div key={d.id} className="portal-check-row">
                <ClipboardCheck size={18} />
                <div>
                  <b>{d.name}</b>
                  <p>{d.findings || d.description}</p>
                </div>
                <DocumentBadge status={d.status} />
              </div>
            ))}
          </Panel>
          <details className="card">
            <summary>Run versioned regulatory and source checks</summary>
            <ScrutinyContent routeId="O06" caseId={id} user={user} />
          </details>
        </>
      )}
      {section === "inspection" && (
        <>
          <Inspection app={app} />
          <details className="card">
            <summary>Compare certified room-area evidence</summary>
            <ScrutinyContent routeId="O07" caseId={id} user={user} />
          </details>
        </>
      )}
      {section === "review" && (
        <>
          <InstitutionDetails app={app} />
          <Answers app={app} officer />
          <ReviewActions app={app} />
          <Reports app={app} />
          <Panel title="Officer review history">
            {app.actions.length ? (
              app.actions.map((a) => (
                <article key={a.id} className="portal-history-row">
                  <ClipboardCheck size={18} />
                  <div>
                    <b>{a.action.replaceAll("_", " ")}</b>
                    <p>{a.reason}</p>
                    <small>
                      {a.by} · {date(a.at)}
                    </small>
                  </div>
                </article>
              ))
            ) : (
              <p>
                No new review actions have been recorded yet. The application history below retains
                earlier recorded activity.
              </p>
            )}
          </Panel>
          <History app={app} />
        </>
      )}
    </>
  );
}
export function PortalClarifications() {
  const q = usePortalApplications();
  const details = useQuery({
    queryKey: ["portal-clarifications", q.data?.data.length],
    enabled: !!q.data,
    queryFn: async () =>
      Promise.all(
        (q.data?.data ?? [])
          .filter((a) => a.state !== "DRAFT")
          .map((a) => api<PortalApplication>(`/portal/applications/${a.id}`)),
      ),
  });
  if (q.isPending || details.isPending || q.error || details.error)
    return <Load error={q.error ?? details.error} retry={() => void details.refetch()} />;
  const list = (details.data ?? []).flatMap((r) =>
    r.data.queries.map((query) => ({ app: r.data, query })),
  );
  return (
    <Panel title="Clarifications and responses">
      <DataTable className="gov-table">
        <thead>
          <tr>
            <th>Request</th>
            <th>Application</th>
            <th>Details</th>
            <th>Due date</th>
            <th>Status</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {list.map(({ app, query }) => (
            <tr key={query.id}>
              <td>
                <b>{query.id}</b>
              </td>
              <td>{app.id}</td>
              <td>{query.message}</td>
              <td>{date(query.dueOn)}</td>
              <td>
                <Status s={query.status} />
              </td>
              <td>
                <Link
                  className="portal-inline-link"
                  to={`/institution/deficiencies/${query.id}/respond`}
                >
                  {query.responses.length ? "View submitted response" : "Respond"}
                  <ArrowRight size={14} />
                </Link>
              </td>
            </tr>
          ))}
          {!list.length && (
            <tr>
              <td colSpan={6}>No clarifications have been issued for your applications.</td>
            </tr>
          )}
        </tbody>
      </DataTable>
    </Panel>
  );
}
export function PortalResponse({ id, user }: { id: string; user: User }) {
  const request = useQuery({
    queryKey: ["portal-response-request", id],
    queryFn: () => api<{ application_id: string }>(`/clarifications/${id}`),
  });
  const q = useQuery({
    queryKey: ["portal-response-case", id],
    enabled: !!request.data,
    queryFn: () =>
      api<PortalApplication>(`/portal/applications/${request.data!.data.application_id}`),
  });
  if (request.isPending || q.isPending || request.error || q.error)
    return (
      <Load
        error={request.error ?? q.error}
        retry={() => {
          void request.refetch();
          void q.refetch();
        }}
      />
    );
  const app = { ...q.data.data, queries: q.data.data.queries.filter((x) => x.id === id) };
  const submitted = app.queries.some((x) => x.responses.length);
  return (
    <>
      <div className="portal-case-heading">
        <div>
          <span className="eyebrow">
            {app.id} · {id}
          </span>
          <h2>{submitted ? "Your submitted response" : "Respond to the officer’s request"}</h2>
          <p>{app.institution.name}</p>
        </div>
        <Status s={app.queries[0]?.status ?? "Open"} />
      </div>
      <Answers app={app} />
      <details className="card" open={!submitted}>
        <summary>
          {submitted
            ? "Original documents and response acknowledgment"
            : "Prepare your response and attach documents"}
        </summary>
        <ClarificationResponsePage id={id} user={user} />
      </details>
    </>
  );
}
export function PortalVerificationQueue({ user }: { user: User }) {
  const q = usePortalApplications();
  const details = useQuery({
    queryKey: ["portal-document-queue", q.data?.data.length],
    enabled: !!q.data,
    queryFn: async () =>
      Promise.all(
        (q.data?.data ?? [])
          .filter((a) => a.state !== "DRAFT")
          .map((a) => api<PortalApplication>(`/portal/applications/${a.id}`)),
      ),
  });
  if (q.isPending || details.isPending || q.error || details.error)
    return <Load error={q.error ?? details.error} retry={() => void details.refetch()} />;
  const list = (details.data ?? []).flatMap((r) =>
    r.data.documents
      .filter((d) => d.versionId && d.status !== "Reviewed")
      .map((doc) => ({ app: r.data, doc })),
  );
  return (
    <>
      <Panel title="Documents awaiting verification">
        <DataTable className="gov-table">
          <thead>
            <tr>
              <th>Application / institution</th>
              <th>Document</th>
              <th>Current finding</th>
              <th>Status</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {list.map(({ app, doc }) => (
              <tr key={doc.versionId}>
                <td>
                  <b>{app.id}</b>
                  <small className="portal-subline">{app.institution.name}</small>
                </td>
                <td>{doc.name}</td>
                <td>{doc.findings || "Review the original and record your findings."}</td>
                <td>
                  <DocumentBadge status={doc.status} />
                </td>
                <td>
                  <Link to={`/officer/cases/${app.id}/evidence`} className="portal-inline-link">
                    Verify document
                    <ArrowRight size={14} />
                  </Link>
                </td>
              </tr>
            ))}
            {!list.length && (
              <tr>
                <td colSpan={5}>
                  All uploaded documents in your current queue have a recorded review.
                </td>
              </tr>
            )}
          </tbody>
        </DataTable>
      </Panel>
      <details className="card">
        <summary>Assigned specialist verification tasks</summary>
        <ScrutinyContent routeId="O09" user={user} />
      </details>
    </>
  );
}
export function PortalReports({ user }: { user: User }) {
  return <ReportLibrary user={user} />;
}
export function PortalNotifications() {
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [filter, setFilter] = useState("all"),
    [error, setError] = useState("");
  const q = useQuery({
    queryKey: ["portal-notifications", filter, page],
    queryFn: () =>
      api<
        {
          id: string;
          summary: string;
          at: number;
          read_at?: number;
          link?: string;
          target_url?: string;
          url?: string;
        }[]
      >(`/notifications?state=${filter}&page=${page}`),
    refetchInterval: 10000,
  });
  async function mark(id?: string) {
    try {
      await api(id ? `/notifications/${id}/read` : "/notifications/read-all", {
        method: "PATCH",
        body: "{}",
      });
      await q.refetch();
      await qc.invalidateQueries({ queryKey: ["notification-count"] });
    } catch (e) {
      setError((e as Error).message);
    }
  }
  if (q.isPending || q.error) return <Load error={q.error} retry={() => void q.refetch()} />;
  return (
    <Card>
      <div className="card-heading">
        <h2>Your notifications</h2>
        <Button variant="outline" onClick={() => void mark()}>
          Mark all as read
        </Button>
      </div>
      <div className="portal-notification-tabs" role="group" aria-label="Filter notifications">
        {[
          ["all", "All"],
          ["unread", "Unread"],
          ["read", "Read"],
        ].map(([key, name]) => (
          <button
            key={key}
            className={filter === key ? "selected" : ""}
            aria-pressed={filter === key}
            onClick={() => {
              setFilter(key);
              setPage(1);
            }}
          >
            {name}
          </button>
        ))}
      </div>
      {error && <p role="alert">{error}</p>}
      {q.data.data.map((n) => (
        <article className={`portal-notification ${n.read_at ? "" : "unread"}`} key={n.id}>
          <MessageSquare size={20} />
          <div>
            <p>{n.summary}</p>
            <small>{date(n.at)}</small>
            {(n.link || n.target_url || n.url) && (
              <Link
                className="portal-inline-link"
                to={portalPath(n.link ?? n.target_url ?? n.url!)}
                onClick={() => void mark(n.id)}
              >
                Open application <ArrowRight size={14} />
              </Link>
            )}
          </div>
          {!n.read_at && (
            <button className="btn btn-outline" onClick={() => void mark(n.id)}>
              Mark as read
            </button>
          )}
        </article>
      ))}
      {!q.data.data.length && <p>No {filter === "all" ? "" : filter + " "}notifications.</p>}
      {(q.data.meta.total ?? 0) > 20 && (
        <div className="form-actions">
          <Button variant="outline" disabled={page === 1} onClick={() => setPage((p) => p - 1)}>
            Previous
          </Button>
          <span>Page {page}</span>
          <Button
            variant="outline"
            disabled={page * 20 >= (q.data.meta.total ?? 0)}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </Button>
        </div>
      )}
    </Card>
  );
}

function ResolveResponse({ app, query }: { app: PortalApplication; query: Query }) {
  const qc = useQueryClient();
  const [reason, setReason] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  return (
    <form
      className="portal-resolution"
      onSubmit={async (e) => {
        e.preventDefault();
        setBusy(true);
        try {
          await call(`/officer/clarifications/${query.id}/resolve`, {
            expected_version: app.reviewVersion,
            rationale: reason,
          });
          await qc.invalidateQueries({ queryKey: ["portal-case", app.id] });
          await qc.invalidateQueries({ queryKey: ["portal-dashboard-details"] });
        } catch (e) {
          setError((e as Error).message);
        } finally {
          setBusy(false);
        }
      }}
    >
      <label className="field">
        Re-verification remarks
        <textarea
          required
          minLength={10}
          maxLength={2000}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Explain how the response and attachments address the request."
        />
      </label>
      {error && <p role="alert">{error}</p>}
      <Button disabled={busy}>Record re-verification and close request</Button>
    </form>
  );
}
