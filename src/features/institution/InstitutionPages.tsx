import guidance from "../../../config/document-guidance.json";
import { PublishedReports } from "../release/ReleasePages";
import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { Link, NavLink, useNavigate, useSearchParams } from "@/features/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  Building2,
  ChevronRight,
  FileText,
  History,
  Plus,
  Search,
  ShieldCheck,
} from "lucide-react";
import {
  api,
  ApiError,
  type Case,
  type Evidence,
  type Institution,
  type Preview,
  type User,
} from "../api";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { ProcessingSlot } from "./ProcessingSlot";
import { SavedEvidenceSource } from "./SavedEvidenceSource";
import { label } from "../presentation";
import type {
  Catalogue,
  Change,
  Checklist,
  Details,
  Item,
  Readiness,
  Receipt,
  Snapshot,
  Workflow,
} from "./types";

const categoryDescription: Record<string, string> = {
  PORTAL_EOA: "Renew approval with current safety, affiliation, faculty and financial records.",
  PORTAL_INTAKE_INCREASE:
    "Propose higher course intake with infrastructure, faculty, Affidavit 8 and the governing-body resolution where applicable.",
  PORTAL_NEW_COURSE:
    "Add a course with its proposed intake, supporting facilities and applicable declarations.",
  PORTAL_NEW_INSTITUTION:
    "Prepare a new-institution proposal with campus land, buildings, staffing and applicable lease undertakings.",
  PORTAL_CLOSURE:
    "Provide the closure resolution, reasons and plan to protect enrolled students and academic records.",
};
const stateKey = (id: string) => ["institution", "state", id];
const unique = (): string => crypto.randomUUID();
const jsonOptions = (body: unknown, method = "POST", key = unique()): RequestInit => ({
  method,
  body: JSON.stringify(body),
  headers: { "Idempotency-Key": key },
});
function Tag({ children }: { children: ReactNode }) {
  return <span className="badge badge-neutral">{children}</span>;
}
function Notice({ children }: { children?: ReactNode }) {
  return (
    <div className="phase2-notice">
      <ShieldCheck size={19} />
      <p>
        {children ??
          "Prepare your application, check the evidence, and resolve any issues before submitting."}
      </p>
    </div>
  );
}
function Wait({ error, retry }: { error?: Error | null; retry?: () => void }) {
  return (
    <Card className="state" role={error ? "alert" : "status"}>
      <h2>{error ? "This section could not be loaded" : "Loading saved records…"}</h2>
      <p>{error?.message ?? "Retrieving your institution’s authorized data."}</p>
      {retry && (
        <Button variant="outline" onClick={retry}>
          Try again
        </Button>
      )}
    </Card>
  );
}
function SourceLink({ item }: { item: Item }) {
  return (
    <a className="source-link" href={item.source.url} target="_blank" rel="noreferrer">
      {item.source.clause}
      {item.source.pdf_page > 0 &&
        ` · printed p.${item.source.printed_page} / PDF p.${item.source.pdf_page}`}
    </a>
  );
}
function ErrorMessage({ error }: { error: string }) {
  return error ? (
    <p className="error" role="alert">
      {error}
    </p>
  ) : null;
}
function ChangeList({ changes }: { changes: Change[] }) {
  return (
    <div className="change-list">
      {changes.length ? (
        changes.map((c) => (
          <div key={c.field}>
            <strong>{c.field}</strong>
            <span>
              {String(c.approved ?? "Not recorded")} <ArrowRight size={14} />{" "}
              <b>{String(c.requested)}</b>
            </span>
            <Tag>
              {c.interpretation === "APPROVED_HISTORY_CHANGE"
                ? "Approved history change"
                : "Proposed change"}
            </Tag>
          </div>
        ))
      ) : (
        <p>No changes from the selected approved baseline.</p>
      )}
    </div>
  );
}
function useWorkflow(id: string) {
  return useQuery({
    queryKey: stateKey(id),
    queryFn: () => api<Workflow>(`/applications/${id}/state`),
    staleTime: 0,
  });
}
function Legacy({ error }: { error: Error }) {
  return (
    <Card>
      <h2>This sample record is read-only</h2>
      <p>{error.message}</p>
      <Button asChild variant="outline">
        <Link to="/institution/applications/new">
          Start a new application <ArrowRight size={16} />
        </Link>
      </Button>
    </Card>
  );
}

export function InstitutionSteps({ routeId, caseId }: { routeId: string; caseId?: string }) {
  const [params] = useSearchParams();
  const id = caseId ?? params.get("resume");
  const steps = [
    ["I03", "Application type", "new"],
    ["I04", "Request details", "details"],
    ["I05", "Checklist", "checklist"],
    ["I06", "Documents", "documents"],
    ["I07", "Precheck", "validation"],
    ["I08", "Review & submit", "review-submit"],
  ];
  return (
    <nav className="section-nav phase2-steps" aria-label="Application sections">
      {steps.map(([key, title, path], index) =>
        id || key === "I03" ? (
          <NavLink
            key={key}
            className={routeId === key ? "active" : ""}
            aria-current={routeId === key ? "step" : undefined}
            aria-label={`Step ${index + 1} of ${steps.length}: ${title}`}
            to={
              key === "I03"
                ? `/institution/applications/new${id ? "?resume=" + id : ""}`
                : `/institution/applications/${id}/${path}`
            }
          >
            <span>{index + 1}</span>
            {title}
          </NavLink>
        ) : (
          <span key={key} className="disabled-step" aria-disabled="true">
            <span>{index + 1}</span>
            {title}
          </span>
        ),
      )}
    </nav>
  );
}

export function InstitutionContent({
  routeId,
  caseId,
  recordId,
  user,
  legacyEvidence,
}: {
  routeId: string;
  caseId?: string;
  recordId?: string;
  user: User;
  legacyEvidence?: ReactNode;
}) {
  if (routeId === "I01") return <InstitutionDashboard user={user} />;
  if (routeId === "I02") return <ApplicationList />;
  if (routeId === "I03") return <ChooseApplication />;
  if (routeId === "I10" || routeId === "I11")
    return <HistoryPage user={user} recordId={recordId} />;
  if (routeId === "I09") return <ApplicationStatus id={caseId!} />;
  return (
    <WorkflowPage routeId={routeId} id={caseId!} user={user} legacyEvidence={legacyEvidence} />
  );
}

function InstitutionDashboard({ user }: { user: User }) {
  const [selected, setSelected] = useState("");
  const institution = selected || user.institution_ids[0];
  const institutions = useQuery({
    queryKey: ["institutions"],
    queryFn: () => api<Institution[]>("/institutions"),
  });
  const q = useQuery({
    queryKey: ["institution", "dashboard", institution],
    queryFn: () =>
      api<{
        counts: Record<string, number>;
        recent: Case[];
        latest_baseline: Snapshot | null;
      }>(`/institutions/${institution}/dashboard`),
  });
  if (q.isPending) return <Wait />;
  if (q.error) return <Wait error={q.error} retry={() => void q.refetch()} />;
  const total = Object.values(q.data.data.counts).reduce((a, b) => a + b, 0);
  return (
    <>
      {user.institution_ids.length > 1 && (
        <label className="field">
          Institution
          <select value={institution} onChange={(e) => setSelected(e.target.value)}>
            {institutions.data?.data.map((i) => (
              <option key={i.id} value={i.id}>
                {i.name}
              </option>
            ))}
          </select>
        </label>
      )}
      <Notice>
        Continue an application or start a new one. Previous approvals stay separate from the
        changes you are requesting.
      </Notice>
      <div className="metrics">
        {[
          ["Applications", total],
          ["Drafts to resume", q.data.data.counts.DRAFT ?? 0],
          ["Submitted", q.data.data.counts.SUBMITTED ?? 0],
        ].map(([title, value]) => (
          <Card className="metric" key={title}>
            <div>
              {title}
              <FileText size={18} />
            </div>
            <strong>{value}</strong>
            <small>Saved applications for your institution</small>
          </Card>
        ))}
      </div>
      <div className="section-heading">
        <div>
          <h2>Application activity</h2>
          <p>Recent drafts and submitted cases.</p>
        </div>
        <Link to="/institution/applications">
          View all <ArrowRight size={16} />
        </Link>
      </div>
      <ApplicationRows rows={q.data.data.recent} />
      <div className="two-columns">
        <Card>
          <div className="card-heading">
            <History size={20} />
            <h2>Last approved baseline</h2>
            <Tag>Previous approval</Tag>
          </div>
          {q.data.data.latest_baseline ? (
            <>
              <h3>{q.data.data.latest_baseline.academic_year}</h3>
              <p>
                {q.data.data.latest_baseline.profile.courses
                  .map((c) => `${c.course}: ${c.approved_intake} approved places`)
                  .join("; ")}
              </p>
              <Link
                to={`/institution/history/${q.data.data.latest_baseline.id}?institution=${institution}`}
              >
                View immutable record <ArrowRight size={16} />
              </Link>
            </>
          ) : (
            <p>No eligible approved baseline has been imported.</p>
          )}
        </Card>
        <Card>
          <h2>Pending next steps</h2>
          <p>
            {q.data.data.counts.DRAFT
              ? "Resume a saved draft, check applicable evidence and review its readiness."
              : "Start a new application when you are ready. Submitted versions stay locked."}
          </p>
          <p className="notice">
            Open an application to see its current checks and review progress.
          </p>
        </Card>
      </div>
    </>
  );
}

function ApplicationRows({ rows }: { rows: Case[] }) {
  return (
    <Card className="table-card">
      {rows.length ? (
        <div className="table-scroll">
          <table>
            <caption className="sr-only">Institution applications</caption>
            <thead>
              <tr>
                <th>Institution / application</th>
                <th>Application type</th>
                <th>Academic year</th>
                <th>Status / updated</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((a) => (
                <tr key={a.id}>
                  <td>
                    <div className="record-name">
                      <span className="record-icon">
                        <Building2 size={18} />
                      </span>
                      <div>
                        <strong>{a.institution_name}</strong>
                        <small>Reference {a.id.slice(0, 8).toUpperCase()}</small>
                      </div>
                    </div>
                  </td>
                  <td>{a.category}</td>
                  <td>{a.academic_year}</td>
                  <td>
                    <Tag>{a.status.replaceAll("_", " ")}</Tag>
                    <small className="updated-at">
                      {new Date(a.updated_at * 1000).toLocaleString()}
                    </small>
                  </td>
                  <td>
                    <Link
                      className="open-link"
                      to={`/institution/applications/${a.id}/${a.status === "DRAFT" ? "details" : "status"}`}
                    >
                      {a.status === "DRAFT" ? "Resume draft" : "View status"}
                      <ChevronRight size={16} />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="empty">
          <FileText size={28} />
          <h2>No applications found</h2>
          <p>Change the filters or create a new application.</p>
        </div>
      )}
    </Card>
  );
}

function ApplicationList() {
  const [params, setParams] = useSearchParams();
  const page = Number(params.get("page") || 1);
  const search = params.get("search") || "";
  const filters = new URLSearchParams({
    page: String(Number.isFinite(page) && page > 0 ? page : 1),
    page_size: "10",
    search,
    year: params.get("year") || "",
    category: params.get("category") || "",
    status: params.get("status") || "",
  });
  const q = useQuery({
    queryKey: ["institution", "applications", filters.toString()],
    queryFn: () => api<Case[]>(`/applications?${filters}`),
  });
  const catalog = useQuery({
    queryKey: ["institution", "catalogue"],
    queryFn: () => api<Catalogue[]>("/catalog/applications"),
  });
  function change(key: string, value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    if (key !== "page") next.delete("page");
    setParams(next, { replace: key === "search" });
  }
  return (
    <>
      <Card className="filter-panel">
        <label className="field search-label">
          <span>Search all authorized applications</span>
          <div className="search-field">
            <Search size={16} />
            <input
              value={search}
              placeholder="Institution, application ID or type"
              onChange={(e) => change("search", e.target.value)}
            />
          </div>
        </label>
        <label className="field">
          Academic year
          <select value={params.get("year") || ""} onChange={(e) => change("year", e.target.value)}>
            <option value="">All years</option>
            {[...new Set(catalog.data?.data.map((c) => c.academic_year))]
              .sort()
              .reverse()
              .map((y) => (
                <option key={y}>{y}</option>
              ))}
          </select>
        </label>
        <label className="field">
          Application type
          <select
            value={params.get("category") || ""}
            onChange={(e) => change("category", e.target.value)}
          >
            <option value="">All types</option>
            {[
              ...new Set(
                catalog.data?.data
                  .filter((c) => c.availability === "enabled")
                  .map((c) => c.display_name),
              ),
            ].map((c) => (
              <option key={c}>{c}</option>
            ))}
            <option>Routine EoA</option>
          </select>
        </label>
        <label className="field">
          Status
          <select
            value={params.get("status") || ""}
            onChange={(e) => change("status", e.target.value)}
          >
            <option value="">All statuses</option>
            {[
              "DRAFT",
              "SUBMITTED",
              "UNDER_REVIEW",
              "CLARIFICATION_REQUESTED",
              "PENDING_VERIFICATION",
              "REVIEW_COMPLETED",
            ].map((s) => (
              <option key={s} value={s}>
                {label(s)}
              </option>
            ))}
          </select>
        </label>
      </Card>
      {q.isPending ? (
        <Wait />
      ) : q.error ? (
        <Wait error={q.error} retry={() => void q.refetch()} />
      ) : (
        <>
          <ApplicationRows rows={q.data.data} />
          <div className="pagination">
            <Button
              variant="outline"
              disabled={page <= 1}
              onClick={() => change("page", String(page - 1))}
            >
              Previous
            </Button>
            <span aria-live="polite">
              Page {page} · {q.data.meta.total} matching records
            </span>
            <Button
              variant="outline"
              disabled={page * 10 >= (q.data.meta.total ?? 0)}
              onClick={() => change("page", String(page + 1))}
            >
              Next
            </Button>
          </div>
        </>
      )}
    </>
  );
}

function ChooseApplication() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [params] = useSearchParams();
  const resume = params.get("resume");
  const catalogs = useQuery({
    queryKey: ["institution", "catalogue"],
    queryFn: () => api<Catalogue[]>("/catalog/applications"),
  });
  const institutions = useQuery({
    queryKey: ["institutions"],
    queryFn: () => api<Institution[]>("/institutions"),
  });
  const existing = useQuery({
    queryKey: ["institution", "draft-list"],
    queryFn: () => api<Case[]>("/applications?status=DRAFT&page_size=100"),
    staleTime: 0,
  });
  const old = useQuery({
    queryKey: stateKey(resume ?? ""),
    queryFn: () => api<Workflow>(`/applications/${resume}/state`),
    enabled: !!resume,
    staleTime: 0,
  });
  const [year, setYear] = useState("");
  const [institution, setInstitution] = useState("");
  const [choice, setChoice] = useState("PORTAL_EOA");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const attempt = useRef<{ signature: string; key: string } | null>(null);
  const selectedYear =
    year || old.data?.data.catalogue.academic_year || catalogs.data?.data[0]?.academic_year || "";
  const institutionId =
    institution ||
    old.data?.data.institution_id ||
    institutions.data?.data.find((i) => i.id === "INS-1-4412")?.id ||
    institutions.data?.data[0]?.id ||
    "";
  const preferredCatalogues = catalogs.data?.data.some((c) => c.definition.portal_revision === 2)
    ? catalogs.data.data.filter(
        (c) => c.definition.portal_revision === 2 || c.id === old.data?.data.catalogue.id,
      )
    : catalogs.data?.data;
  const rows =
    preferredCatalogues
      ?.filter((c) => c.academic_year === selectedYear)
      .sort(
        (a, b) =>
          Number(b.availability === "enabled") - Number(a.availability === "enabled") ||
          a.code.localeCompare(b.code),
      ) ?? [];
  const current = rows.find((c) => c.code === choice) ?? rows[0];
  const duplicate = existing.data?.data.find(
    (a) => a.catalogue_id === current?.id && a.institution_id === institutionId && a.id !== resume,
  );
  async function go() {
    if (!current || !institutionId) return;
    setError("");
    setPending(true);
    try {
      if (duplicate) {
        navigate(`/institution/applications/${duplicate.id}/details`);
        return;
      }
      const prior = old.data?.data;
      const body =
        prior && prior.editable
          ? {
              expected_version: prior.version,
              details: prior.details,
              catalogue_id: current.id,
            }
          : { institution_id: institutionId, catalogue_id: current.id };
      const signature = JSON.stringify(body);
      if (attempt.current?.signature !== signature) attempt.current = { signature, key: unique() };
      const result = await api<Workflow>(
        prior && prior.editable ? `/applications/${prior.application_id}/draft` : "/applications",
        jsonOptions(body, prior && prior.editable ? "PATCH" : "POST", attempt.current!.key),
      );
      qc.setQueryData(stateKey(result.data.application_id), result);
      await qc.invalidateQueries({ queryKey: ["institution", "applications"] });
      await qc.invalidateQueries({ queryKey: ["institution", "dashboard"] });
      navigate(`/institution/applications/${result.data.application_id}/details`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setPending(false);
    }
  }
  if (catalogs.isPending || institutions.isPending || (resume && old.isPending)) return <Wait />;
  if (catalogs.error || institutions.error)
    return <Wait error={catalogs.error ?? institutions.error} />;
  return (
    <>
      <Notice />
      <Card className="form-card">
        <div className="form-grid">
          <label className="field">
            Institution
            <select
              value={institutionId}
              disabled={!!old.data?.data.editable}
              onChange={(e) => setInstitution(e.target.value)}
            >
              {institutions.data?.data.map((i) => (
                <option key={i.id} value={i.id}>
                  {i.name} · {i.permanent_id}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            Academic year
            <select
              value={selectedYear}
              onChange={(e) => {
                setYear(e.target.value);
                attempt.current = null;
              }}
            >
              {[...new Set(catalogs.data?.data.map((c) => c.academic_year))].map((y) => (
                <option key={y}>{y}</option>
              ))}
            </select>
          </label>
        </div>
        {old.error && (
          <p className="notice">{old.error.message} This selection will create a new draft.</p>
        )}
        <h2>Choose an application category</h2>
        <div className="catalogue-grid">
          {rows
            .filter((c) => c.availability === "enabled")
            .map((c) => (
              <button
                type="button"
                key={c.id}
                className={`catalogue-card ${current?.id === c.id ? "selected" : ""}`}
                aria-pressed={current?.id === c.id}
                onClick={() => {
                  setChoice(c.code);
                  setError("");
                  attempt.current = null;
                }}
              >
                <Tag>
                  {c.availability === "enabled"
                    ? "Available"
                    : c.availability === "external"
                      ? "External guidance"
                      : "Preview"}
                </Tag>
                <h3>{c.display_name}</h3>
                <p>{categoryDescription[c.code] ?? c.definition.document_package}</p>
              </button>
            ))}
        </div>
      </Card>
      {rows.some((c) => c.availability !== "enabled") && (
        <details className="card">
          <summary>Other application types</summary>
          <p>
            These categories provide guidance until their individual procedures and rule packages
            have been reviewed.
          </p>
          <div className="catalogue-grid">
            {rows
              .filter((c) => c.availability !== "enabled")
              .map((c) => (
                <button
                  type="button"
                  key={c.id}
                  className="catalogue-card"
                  aria-pressed={current?.id === c.id}
                  onClick={() => {
                    setChoice(c.code);
                    setError("");
                  }}
                >
                  <Tag>{c.availability === "external" ? "External guidance" : "Guidance only"}</Tag>
                  <h3>{c.display_name}</h3>
                  <p>{categoryDescription[c.code] ?? c.definition.document_package}</p>
                </button>
              ))}
          </div>
        </details>
      )}
      {current && (
        <Card className="catalogue-detail">
          <div className="card-heading">
            <h2>{current.display_name}</h2>
            <Tag>{current.academic_year}</Tag>
          </div>
          <p>
            {current.code === "EOA"
              ? "For an existing institution seeking an extension of its approval."
              : (categoryDescription[current.code] ?? current.definition.eligibility)}
          </p>
          <dl className="details">
            <dt>Next steps</dt>
            <dd>
              Prepare details, upload applicable documents, resolve checks, and submit for review.
            </dd>
            <dt>Stages</dt>
            <dd>{current.definition.procedural_stages.map((stage) => label(stage)).join(" → ")}</dd>

            <dt>Source</dt>
            <dd>
              <a href={current.definition.source.url} target="_blank" rel="noreferrer">
                {current.definition.source.clause}
              </a>
            </dd>
          </dl>
          {current.availability === "external" ? (
            <p>
              <a href={current.definition.external_url!} target="_blank" rel="noreferrer">
                Read the approval process notice
              </a>
              . This prototype does not submit new-institution applications to government systems.
            </p>
          ) : current.availability === "preview" ? (
            <p>
              This category needs its own reviewed procedure and document package. Local draft
              creation is unavailable.
            </p>
          ) : null}
          {duplicate && (
            <p className="phase2-inline-note">
              A draft already exists for this category and year. Resume it to preserve your work.
            </p>
          )}
          <ErrorMessage error={error} />
          <div className="form-actions">
            <Button asChild variant="ghost">
              <Link to="/institution/applications">Cancel</Link>
            </Button>
            <Button
              disabled={pending || current.availability !== "enabled" || !institutionId}
              onClick={() => void go()}
            >
              {pending
                ? "Saving…"
                : duplicate
                  ? "Resume draft"
                  : old.data?.data.editable
                    ? "Save category & continue"
                    : "Create draft & continue"}
              <ArrowRight size={16} />
            </Button>
          </div>
        </Card>
      )}
    </>
  );
}

function WorkflowPage({
  routeId,
  id,
  user,
  legacyEvidence,
}: {
  routeId: string;
  id: string;
  user: User;
  legacyEvidence?: ReactNode;
}) {
  const q = useWorkflow(id);
  if (q.isPending) return <Wait />;
  if (q.error) {
    if (q.error instanceof ApiError && q.error.status === 409)
      return (
        <>
          {routeId === "I06" && legacyEvidence}
          <Legacy error={q.error} />
        </>
      );
    return <Wait error={q.error} retry={() => void q.refetch()} />;
  }
  const s = q.data.data;
  return (
    <>
      <Notice>
        {s.catalogue.display_name} · {s.catalogue.academic_year}.{" "}
        {s.editable ? "Draft changes are versioned." : "This submitted revision is read-only."}{" "}
        Checks use reference date {s.catalogue.definition.reference_date}.
      </Notice>
      {routeId === "I04" ? (
        <DetailsEditor initial={s} />
      ) : routeId === "I05" ? (
        <>
          <ChecklistCards checklist={s.checklist} />
          <StepActions id={id} back="details" next="documents" />
        </>
      ) : routeId === "I06" ? (
        <DocumentSlots s={s} />
      ) : routeId === "I07" ? (
        <Precheck s={s} />
      ) : (
        <ReviewSubmit s={s} user={user} />
      )}
    </>
  );
}

function StepActions({
  id,
  back,
  next,
  nextLabel = "Continue",
}: {
  id: string;
  back?: string;
  next?: string;
  nextLabel?: string;
}) {
  return (
    <div className="form-actions">
      {back && (
        <Button asChild variant="outline">
          <Link to={`/institution/applications/${id}/${back}`}>Back</Link>
        </Button>
      )}
      {next && (
        <Button asChild>
          <Link to={`/institution/applications/${id}/${next}`}>
            {nextLabel}
            <ArrowRight size={16} />
          </Link>
        </Button>
      )}
    </div>
  );
}

function DetailsEditor({ initial }: { initial: Workflow }) {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const storageKey = `uranium-draft:${initial.application_id}`;
  const recovered = useRef<{ version: number; details: Details } | null>(null);
  if (!recovered.current) {
    try {
      const raw = sessionStorage.getItem(storageKey);
      if (raw) recovered.current = JSON.parse(raw);
    } catch {
      /* Invalid local recovery never affects server state. */
    }
  }
  const validRecovery = recovered.current?.version === initial.version;
  const [form, setForm] = useState<Details>(
    validRecovery ? recovered.current!.details : initial.details,
  );
  const formRef = useRef(form);
  const version = useRef(initial.version);
  const [dirty, setDirty] = useState(!!validRecovery);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [conflict, setConflict] = useState(!!recovered.current && !validRecovery);
  const [backup, setBackup] = useState<Details | null>(() => {
    if (!validRecovery && recovered.current) return recovered.current.details;
    try {
      return JSON.parse(
        sessionStorage.getItem(storageKey + ":recovery") ?? "null",
      ) as Details | null;
    } catch {
      return null;
    }
  });
  const [savedAt, setSavedAt] = useState(initial.updated_at);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const request = useRef<{ body: unknown; key: string } | null>(null);
  const saving = useRef(false);
  const continueAfterSave = useRef(false);
  function update(next: Details) {
    formRef.current = next;
    setForm(next);
    setDirty(true);
    setError("");
    setFieldErrors({});
    sessionStorage.setItem(storageKey, JSON.stringify({ version: version.current, details: next }));
  }
  function field<K extends keyof Details>(key: K, value: Details[K]) {
    update({ ...formRef.current, [key]: value });
  }
  async function persist() {
    if (saving.current || !initial.editable || conflict) return false;
    saving.current = true;
    setPending(true);
    setError("");
    if (!request.current)
      request.current = {
        body: { expected_version: version.current, details: formRef.current },
        key: unique(),
      };
    const attempt = request.current;
    const sent = JSON.stringify((attempt.body as { details: Details }).details);
    try {
      const result = await api<Workflow>(
        `/applications/${initial.application_id}/draft`,
        jsonOptions(attempt.body, "PATCH", attempt.key),
      );
      request.current = null;
      version.current = result.data.version;
      setSavedAt(result.data.updated_at);
      qc.setQueryData(stateKey(initial.application_id), result);
      const changed = JSON.stringify(formRef.current) !== sent;
      setDirty(changed);
      if (changed)
        sessionStorage.setItem(
          storageKey,
          JSON.stringify({
            version: version.current,
            details: formRef.current,
          }),
        );
      else sessionStorage.removeItem(storageKey);
      void qc.invalidateQueries({ queryKey: ["institution", "applications"] });
      void qc.invalidateQueries({ queryKey: ["institution", "dashboard"] });
      if (!changed && continueAfterSave.current) {
        continueAfterSave.current = false;
        navigate(`/institution/applications/${initial.application_id}/checklist`);
      }
      return !changed;
    } catch (e) {
      continueAfterSave.current = false;
      const err = e as ApiError;
      setError(err.message);
      setFieldErrors(err.fields ?? {});
      if (err.status === 409) setConflict(true);
      return false;
    } finally {
      saving.current = false;
      setPending(false);
    }
  }
  const persistRef = useRef(persist);
  persistRef.current = persist;
  useEffect(() => {
    if (!dirty || pending || conflict || error || !initial.editable) return;
    const timer = setTimeout(() => void persistRef.current(), 800);
    return () => clearTimeout(timer);
  }, [dirty, pending, conflict, error, form, initial.editable]);
  async function loadSaved() {
    try {
      const r = await api<Workflow>(`/applications/${initial.application_id}/state`);
      const localCopy = backup ?? formRef.current;
      setBackup(localCopy);
      sessionStorage.setItem(storageKey + ":recovery", JSON.stringify(localCopy));
      request.current = null;
      version.current = r.data.version;
      formRef.current = r.data.details;
      setForm(r.data.details);
      setDirty(false);
      setConflict(false);
      setError("");
      setSavedAt(r.data.updated_at);
      sessionStorage.removeItem(storageKey);
      qc.setQueryData(stateKey(initial.application_id), r);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function next(e: FormEvent) {
    e.preventDefault();
    if (!dirty && !pending) {
      navigate(`/institution/applications/${initial.application_id}/checklist`);
      return;
    }
    continueAfterSave.current = true;
    await persist();
  }
  const base = initial.baseline.profile;
  return (
    <form className="institution-form" onSubmit={(e) => void next(e)} noValidate>
      {!!Object.keys(fieldErrors).length && (
        <div className="error-summary" role="alert" tabIndex={-1}>
          <h2>Check these details</h2>
          <ul>
            {Object.entries(fieldErrors).map(([key, text]) => (
              <li key={key}>
                <a href={`#detail-${key.replace("body.details.", "").split(".")[0]}`}>
                  {label(key.replace("body.details.", ""))}: {text}
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}
      <div className="save-bar">
        <span role="status" aria-live="polite">
          {pending
            ? "Saving draft…"
            : conflict
              ? "Conflict requires review"
              : dirty
                ? "Unsaved local changes"
                : `Saved at ${new Date(savedAt * 1000).toLocaleTimeString()} · version ${version.current}`}
        </span>
        <div>
          <Button
            type="button"
            variant="outline"
            disabled={pending || conflict || !initial.editable}
            onClick={() => void persist()}
          >
            Save draft
          </Button>
          <Button type="submit" disabled={pending || conflict}>
            Save & continue <ArrowRight size={16} />
          </Button>
        </div>
      </div>
      <Card>
        <div className="card-heading">
          <h2>
            {initial.catalogue.code.endsWith("NEW_INSTITUTION")
              ? "Registration profile"
              : "Previous approval"}
          </h2>
          <Tag>
            {initial.catalogue.code.endsWith("NEW_INSTITUTION")
              ? "New institution proposal"
              : initial.baseline.academic_year}
          </Tag>
        </div>
        <dl className="details">
          <dt>Institution</dt>
          <dd>{base.name}</dd>
          <dt>Permanent ID</dt>
          <dd>{base.permanent_id}</dd>
          <dt>Approved address</dt>
          <dd>{base.address ?? "Not recorded"}</dd>
          <dt>Institution type</dt>
          <dd>{base.institution_type?.replaceAll("_", " ") ?? "Not recorded"}</dd>
        </dl>
        {!initial.catalogue.code.endsWith("NEW_INSTITUTION") && (
          <Link
            to={`/institution/history/${initial.baseline.id}?institution=${initial.institution_id}`}
          >
            Open read-only approval record
          </Link>
        )}
        {base.prefill_source_year !== initial.baseline.academic_year && (
          <p className="notice">
            Name, address and building fields use{" "}
            {base.prefill_source_year
              ? `the ${base.prefill_source_year} profile`
              : "labelled directory metadata"}{" "}
            as prefill. Course and approved intake values remain tied to the{" "}
            {initial.baseline.academic_year} snapshot.
          </p>
        )}
      </Card>
      {conflict && (
        <div className="conflict-banner" role="alert">
          <h2>A newer saved version needs review</h2>
          <p>
            Your local edits have been preserved. Load the saved version before deciding whether to
            restore them.
          </p>
          <Button type="button" variant="outline" onClick={() => void loadSaved()}>
            Load saved version and keep a recovery copy
          </Button>
        </div>
      )}
      {backup && (
        <Card>
          <h2>Recovered local changes</h2>
          <p>
            {backup.proposed_name} · {backup.proposed_address} · Signatory:{" "}
            {backup.signatory || "Not recorded"} ·{" "}
            {backup.courses.map((c) => `${c.course}: ${c.requested_intake}`).join("; ")}
          </p>
          <Button
            type="button"
            variant="outline"
            disabled={conflict || !initial.editable}
            onClick={() => {
              update(backup);
              setBackup(null);
              sessionStorage.removeItem(storageKey + ":recovery");
            }}
          >
            Restore these edits for review
          </Button>
        </Card>
      )}
      <Card>
        <h2>Institution and request details</h2>
        <p>Proposed values are stored separately from approved history.</p>
        <fieldset disabled={!initial.editable || conflict}>
          <div className="form-grid">
            <label className="field">
              Proposed institution name
              <input
                id="detail-proposed_name"
                aria-describedby={
                  fieldErrors["body.details.proposed_name"]
                    ? "detail-proposed_name-error"
                    : undefined
                }
                aria-invalid={!!fieldErrors["body.details.proposed_name"]}
                value={form.proposed_name}
                maxLength={200}
                onChange={(e) => field("proposed_name", e.target.value)}
                autoComplete="organization"
              />
              {fieldErrors["body.details.proposed_name"] && (
                <small className="error" id="detail-proposed_name-error">
                  {fieldErrors["body.details.proposed_name"]}
                </small>
              )}
            </label>
            <label className="field">
              Affiliating university / board
              <input
                id="detail-affiliation"
                aria-describedby={
                  fieldErrors["body.details.affiliation"] ? "detail-affiliation-error" : undefined
                }
                aria-invalid={!!fieldErrors["body.details.affiliation"]}
                value={form.affiliation}
                maxLength={200}
                onChange={(e) => field("affiliation", e.target.value)}
              />
              {fieldErrors["body.details.affiliation"] && (
                <small className="error" id="detail-affiliation-error">
                  {fieldErrors["body.details.affiliation"]}
                </small>
              )}
            </label>
            <label className="field full-field">
              Proposed campus address
              <textarea
                id="detail-proposed_address"
                aria-describedby={
                  fieldErrors["body.details.proposed_address"]
                    ? "detail-proposed_address-error"
                    : undefined
                }
                aria-invalid={!!fieldErrors["body.details.proposed_address"]}
                value={form.proposed_address}
                maxLength={500}
                onChange={(e) => field("proposed_address", e.target.value)}
                autoComplete="street-address"
              />
              {fieldErrors["body.details.proposed_address"] && (
                <small className="error" id="detail-proposed_address-error">
                  {fieldErrors["body.details.proposed_address"]}
                </small>
              )}
            </label>
            <label className="field">
              Campus land tenure
              <select
                value={form.land_tenure ?? "OWNED"}
                onChange={(e) => field("land_tenure", e.target.value as Details["land_tenure"])}
              >
                <option value="OWNED">Owned land</option>
                <option value="LEASED">Registered lease</option>
              </select>
              <small>Leased-land proposals may require an additional undertaking.</small>
            </label>
            {(
              [
                ["land_area_acres", "Campus land area (acres)", 0.01],
                ["built_up_area_m2", "Certified built-up area (m²)", 0.01],
                ["faculty_count", "Number of appointed faculty", 1],
              ] as const
            ).map(([key, title, step]) => (
              <label className="field" key={key}>
                {title}
                <input
                  type="number"
                  min="0"
                  step={step}
                  value={form[key] ?? ""}
                  onChange={(e) =>
                    field(key, e.target.value === "" ? null : Number(e.target.value))
                  }
                />
              </label>
            ))}
            <label className="field">
              Programme
              <select
                value={form.programme}
                onChange={(e) => field("programme", e.target.value as Details["programme"])}
              >
                {initial.catalogue.definition.programmes.map((p) => (
                  <option key={p}>{p}</option>
                ))}
              </select>
            </label>
            <label className="field">
              Authorized signatory
              <input
                id="detail-signatory"
                aria-describedby={
                  fieldErrors["body.details.signatory"] ? "detail-signatory-error" : undefined
                }
                aria-invalid={!!fieldErrors["body.details.signatory"]}
                value={form.signatory}
                maxLength={160}
                onChange={(e) => field("signatory", e.target.value)}
                autoComplete="name"
              />
              <small>Required before submission.</small>
              {fieldErrors["body.details.signatory"] && (
                <small className="error" id="detail-signatory-error">
                  {fieldErrors["body.details.signatory"]}
                </small>
              )}
            </label>
          </div>
        </fieldset>
      </Card>
      <Card>
        <div className="card-heading">
          <h2>Course and intake proposals</h2>
          <Tag>Approved ≠ requested</Tag>
        </div>
        <fieldset disabled={!initial.editable || conflict}>
          {form.courses.map((course, index) => (
            <div className="course-row" key={index}>
              <label className="field">
                Course name {index + 1}
                <input
                  value={course.course}
                  maxLength={100}
                  onChange={(e) =>
                    field(
                      "courses",
                      form.courses.map((c, i) =>
                        i === index ? { ...c, course: e.target.value } : c,
                      ),
                    )
                  }
                />
              </label>
              <label className="field">
                Level {index + 1}
                <select
                  value={course.level ?? "UG"}
                  onChange={(e) =>
                    field(
                      "courses",
                      form.courses.map((c, i) =>
                        i === index
                          ? {
                              ...c,
                              level: e.target.value as "UG" | "PG" | "FELLOW",
                            }
                          : c,
                      ),
                    )
                  }
                >
                  {["UG", "PG", "FELLOW"].map((l) => (
                    <option key={l}>{l}</option>
                  ))}
                </select>
              </label>
              <div className="approved-number">
                <small>Approved intake</small>
                <strong>
                  {base.courses.find((c) => c.course.toLowerCase() === course.course.toLowerCase())
                    ?.approved_intake ?? 0}
                </strong>
              </div>
              <label className="field">
                Requested intake {index + 1}
                <input
                  type="number"
                  min={0}
                  max={5000}
                  value={course.requested_intake}
                  onChange={(e) =>
                    field(
                      "courses",
                      form.courses.map((c, i) =>
                        i === index ? { ...c, requested_intake: Number(e.target.value) } : c,
                      ),
                    )
                  }
                />
              </label>
              <Button
                type="button"
                variant="ghost"
                onClick={() =>
                  field(
                    "courses",
                    form.courses.filter((_, i) => i !== index),
                  )
                }
              >
                Remove course {index + 1}
              </Button>
            </div>
          ))}
          <Button
            type="button"
            variant="outline"
            disabled={form.courses.length >= 30}
            onClick={() =>
              field("courses", [
                ...form.courses,
                {
                  course: `New course ${form.courses.length + 1}`,
                  level: "UG",
                  requested_intake: 0,
                },
              ])
            }
          >
            <Plus size={16} />
            Add course
          </Button>
        </fieldset>
        <p className="notice">
          An intake increase is a proposed change. Its supporting requirements depend on the
          selected category.
        </p>
      </Card>
      <Card>
        <h2>Building and documentary context</h2>
        <fieldset disabled={!initial.editable || conflict}>
          <div className="form-grid">
            <label className="field">
              Completion certificate issue date
              <input
                type="date"
                value={form.completion_date ?? ""}
                onChange={(e) => field("completion_date", e.target.value || null)}
              />
              <small>
                Used for the structural-certificate age condition, not a model estimate.
              </small>
            </label>
            <label className="check-field">
              <input
                type="checkbox"
                checked={form.payment_applicable}
                onChange={(e) => field("payment_applicable", e.target.checked)}
              />
              Relevant-year payment receipt is applicable
            </label>
            {base.institution_type === "government" && (
              <label className="check-field full-field">
                <input
                  type="checkbox"
                  checked={form.originals_unavailable}
                  onChange={(e) => field("originals_unavailable", e.target.checked)}
                />
                Original building documents are unavailable. Any alternative still requires a
                recorded review and supporting evidence.
              </label>
            )}
          </div>
        </fieldset>
      </Card>
      <Card>
        <div className="card-heading">
          <h2>Infrastructure declarations</h2>
          <Tag>Optional draft details</Tag>
        </div>
        <fieldset disabled={!initial.editable || conflict}>
          {form.rooms.map((room, index) => (
            <div className="room-row" key={index}>
              <label className="field">
                Room ID {index + 1}
                <input
                  value={room.room_id}
                  maxLength={64}
                  onChange={(e) =>
                    field(
                      "rooms",
                      form.rooms.map((r, i) =>
                        i === index ? { ...r, room_id: e.target.value } : r,
                      ),
                    )
                  }
                />
              </label>
              <label className="field">
                Room type {index + 1}
                <select
                  value={room.room_type ?? "CLASSROOM"}
                  onChange={(e) =>
                    field(
                      "rooms",
                      form.rooms.map((r, i) =>
                        i === index
                          ? {
                              ...r,
                              room_type: e.target.value as "CLASSROOM" | "LABORATORY" | "OTHER",
                            }
                          : r,
                      ),
                    )
                  }
                >
                  {["CLASSROOM", "LABORATORY", "OTHER"].map((t) => (
                    <option key={t}>{t}</option>
                  ))}
                </select>
              </label>
              <label className="field">
                Declared area m² {index + 1}
                <input
                  type="number"
                  min={0}
                  max={100000}
                  step="0.01"
                  value={room.declared_area}
                  onChange={(e) =>
                    field(
                      "rooms",
                      form.rooms.map((r, i) =>
                        i === index ? { ...r, declared_area: Number(e.target.value) } : r,
                      ),
                    )
                  }
                />
              </label>
              <Button
                type="button"
                variant="ghost"
                onClick={() =>
                  field(
                    "rooms",
                    form.rooms.filter((_, i) => i !== index),
                  )
                }
              >
                Remove room {index + 1}
              </Button>
            </div>
          ))}
          <Button
            type="button"
            variant="outline"
            onClick={() =>
              field("rooms", [
                ...form.rooms,
                {
                  room_id: `R-${form.rooms.length + 1}`,
                  room_type: "CLASSROOM",
                  declared_area: 0,
                },
              ])
            }
          >
            <Plus size={16} />
            Add room
          </Button>
        </fieldset>
        <p className="notice">
          These are your declared measurements. Officers compare them with supporting evidence
          during review.
        </p>
      </Card>
      <ErrorMessage error={error} />
      {Object.keys(fieldErrors).length > 0 && (
        <ul className="error" aria-label="Field errors">
          {Object.entries(fieldErrors).map(([key, text]) => (
            <li key={key}>
              {key.replace("body.details.", "")}: {text}
            </li>
          ))}
        </ul>
      )}
    </form>
  );
}

function ChecklistCards({ checklist }: { checklist: Checklist }) {
  return (
    <div className="checklist-list">
      {checklist.items.map((item) => (
        <Card key={item.id}>
          <div className="card-heading">
            <h2>{item.label}</h2>
            <Tag>{label(item.applicability)}</Tag>
          </div>
          <p>
            {item.reason === "Required by the selected demo document package."
              ? "Required for this application."
              : item.reason === "The conditional trigger is not met for this saved request."
                ? "Not required for the details you have saved."
                : item.reason}
          </p>
          <div className="requirement-meta">
            <span>
              Needed:{" "}
              {item.stage_due === "SUBMISSION" ? "Before submission" : label(item.stage_due)}
            </span>
            <span>
              {item.satisfied
                ? "Accepted evidence attached"
                : item.mandatory
                  ? "Evidence needed"
                  : "No submission-stage block"}
            </span>
          </div>
          <p className="notice">
            Accept one appropriate alternative:{" "}
            {item.acceptable_alternatives.map((x) => x.replaceAll("_", " ")).join(" / ")}.
          </p>
          <SourceLink item={item} />
          {item.exception && (
            <p className="phase2-inline-note">
              {item.exception.source_ref} · reviewer {item.exception.reviewed_by.slice(0, 8)} ·{" "}
              {new Date(item.exception.reviewed_at * 1000).toLocaleDateString()}
            </p>
          )}
        </Card>
      ))}
    </div>
  );
}

function DocumentSlots({ s }: { s: Workflow }) {
  const [choices, setChoices] = useState<Record<string, string>>({});
  const versions = useQuery({
    queryKey: ["institution", "versions", s.application_id, s.version],
    queryFn: () => api<Evidence[]>(`/applications/${s.application_id}/documents`),
  });
  const required = s.checklist.items.filter((i) => i.mandatory);
  const ready = required.filter((i) => i.evidence?.status === "PROCESSED").length;
  return (
    <>
      <Card>
        <h2>Your documents</h2>
        <p>
          Upload an original PDF, PNG or JPEG for each applicable requirement. Safety and
          readability checks start automatically. You can replace a document while the application
          is a draft.
        </p>
        <p>
          {ready} of {required.length} required documents processed
        </p>
        <p className="notice">
          Documents stay private. If a safety check cannot run, the file stays isolated and cannot
          be used for submission.
        </p>
      </Card>
      <div className="checklist-list">
        {s.checklist.items.map((item) => (
          <Card key={item.id} data-requirement={item.code}>
            <div className="card-heading">
              <h2>{item.label}</h2>
              <Tag>{label(item.applicability)}</Tag>
            </div>
            <p>
              {item.reason === "Required by the selected demo document package."
                ? "Required for this application."
                : item.reason === "The conditional trigger is not met for this saved request."
                  ? "Not required for the details you have saved."
                  : item.reason}
            </p>
            <p className="portal-document-guidance">
              {(guidance as Record<string, string[]>)[item.acceptable_alternatives[0]]?.[1]}
            </p>
            <details className="requirement-source">
              <summary>Why this document is needed</summary>
              <SourceLink item={item} />
            </details>
            {s.editable && !["NOT_APPLICABLE", "NOT_DUE"].includes(item.applicability) && (
              <label className="field">
                Document type
                <select
                  value={choices[item.id] ?? item.acceptable_alternatives[0]}
                  onChange={(e) => setChoices({ ...choices, [item.id]: e.target.value })}
                >
                  {item.acceptable_alternatives.map((t) => (
                    <option key={t} value={t}>
                      {(guidance as Record<string, string[]>)[t]?.[0] ?? label(t)}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <ProcessingSlot
              s={s}
              item={item}
              documentType={choices[item.id] ?? item.acceptable_alternatives[0]}
            />
            {item.evidence?.status === "SYNTHETIC_FIXTURE" && (
              <p className="notice">
                This sample attachment has not been processed. Upload an original to run document
                checks.
              </p>
            )}
          </Card>
        ))}
      </div>
      <SavedEvidenceSource s={s} />
      <details className="card">
        <summary>Document version history</summary>
        {versions.isPending ? (
          <p role="status">Loading document versions…</p>
        ) : versions.error ? (
          <p role="alert">{versions.error.message}</p>
        ) : versions.data?.data.length ? (
          versions.data.data.map((v) => (
            <article className="directory-row" key={v.id}>
              <div>
                <b>{v.original_name}</b>
                <p>
                  Version {v.number} · {label(v.status)}
                </p>
                <Link to={`?sourceVersion=${v.id}`}>
                  View this version and extracted information
                </Link>
              </div>
            </article>
          ))
        ) : (
          <p>No documents uploaded yet.</p>
        )}
      </details>
      <StepActions
        id={s.application_id}
        back="checklist"
        next="validation"
        nextLabel="Check readiness"
      />
    </>
  );
}

function Precheck({ s }: { s: Workflow }) {
  const q = useQuery({
    queryKey: ["institution", "precheck", s.application_id, s.version],
    queryFn: () =>
      api<Readiness>(
        `/applications/${s.application_id}/precheck`,
        s.editable ? { method: "POST" } : {},
      ),
    staleTime: 0,
  });
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  async function run() {
    setPending(true);
    setError("");
    try {
      await api(`/applications/${s.application_id}/precheck`, {
        method: "POST",
      });
      await q.refetch();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setPending(false);
    }
  }
  if (q.isPending) return <Wait />;
  if (q.error) return <Wait error={q.error} retry={() => void q.refetch()} />;
  return (
    <>
      <Card>
        <div className="card-heading">
          <h2>
            {q.data.data.ready ? "Ready for submission" : "Corrections needed before submission"}
          </h2>
          <Tag>Version {q.data.data.version}</Tag>
        </div>
        <Button variant="outline" disabled={pending} onClick={() => void run()}>
          {pending ? "Checking your application…" : "Check again"}
        </Button>
        <ErrorMessage error={error} />
        {q.data.data.blocking.length > 0 && (
          <ul className="blocking-list" aria-label="Blocking issues">
            {q.data.data.blocking.map((b, i) => (
              <li key={i}>
                <strong>{b.message}</strong>
                {b.version_id && (
                  <Link
                    to={`/institution/applications/${s.application_id}/documents?sourceVersion=${b.version_id}`}
                  >
                    View saved source{b.page ? ` · page ${b.page}` : ""}
                  </Link>
                )}
                <Link
                  to={`/institution/applications/${s.application_id}/${b.requirement_id ? "documents" : "details"}`}
                >
                  {b.requirement_id ? "Fix evidence" : "Edit details"} <ArrowRight size={14} />
                </Link>
              </li>
            ))}
          </ul>
        )}
        <h3>Scope of this precheck</h3>
        <ul className="advisory-list">
          {q.data.data.advisory.map((a) => (
            <li key={a}>{a}</li>
          ))}
        </ul>
      </Card>
      <ChecklistCards checklist={q.data.data.checklist} />
      <StepActions
        id={s.application_id}
        back="documents"
        next="review-submit"
        nextLabel="Review application"
      />
    </>
  );
}

function ReviewSubmit({ s, user }: { s: Workflow; user: User }) {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const dialog = useRef<HTMLDialogElement>(null);
  const [declaration, setDeclaration] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const request = useRef<{ version: number; key: string } | null>(null);
  const ready = useQuery({
    queryKey: ["institution", "precheck", s.application_id, s.version],
    queryFn: () =>
      api<Readiness>(
        `/applications/${s.application_id}/precheck`,
        s.editable ? { method: "POST" } : {},
      ),
    staleTime: 0,
  });
  async function submit() {
    setPending(true);
    setError("");
    if (request.current?.version !== s.version)
      request.current = { version: s.version, key: unique() };
    try {
      await api<Receipt>(
        `/applications/${s.application_id}/submit`,
        jsonOptions(
          {
            expected_version: s.version,
            declaration: true,
            precheck_id: ready.data?.data.precheck_id ?? null,
          },
          "POST",
          request.current!.key,
        ),
      );
      dialog.current?.close();
      await qc.invalidateQueries({ queryKey: stateKey(s.application_id) });
      await qc.invalidateQueries({ queryKey: ["institution"] });
      navigate(`/institution/applications/${s.application_id}/status`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setPending(false);
    }
  }
  return (
    <>
      <Card>
        <h2>Application review</h2>
        <dl className="details">
          <dt>Category / year</dt>
          <dd>
            {s.catalogue.display_name} · {s.catalogue.academic_year}
          </dd>
          <dt>Institution</dt>
          <dd>{s.details.proposed_name}</dd>
          <dt>Address</dt>
          <dd>{s.details.proposed_address}</dd>
          <dt>Affiliation</dt>
          <dd>{s.details.affiliation}</dd>
          <dt>Authorized signatory</dt>
          <dd>{s.details.signatory || "Missing"}</dd>
          <dt>Rule package</dt>
          <dd>{s.catalogue.rule_version}</dd>
        </dl>
        <h3>Approved versus requested</h3>
        <ChangeList changes={s.changes} />
      </Card>
      <ChecklistCards checklist={s.checklist} />
      <Card>
        <h2>Declaration and submission</h2>
        {ready.isPending ? (
          <p role="status">Checking the saved revision…</p>
        ) : ready.error ? (
          <ErrorMessage error={ready.error.message} />
        ) : (
          <p>
            {ready.data.data.ready
              ? "Your saved application is ready for submission."
              : "There are unresolved requirements. Return to precheck to review them."}
          </p>
        )}
        {!s.can_submit && (
          <p className="phase2-inline-note">
            Signed in as {user.name}. An administrator for this institution must make the final
            submission. You can continue saving and preparing the draft.
          </p>
        )}
        {!s.editable ? (
          <Button asChild>
            <Link to={`/institution/applications/${s.application_id}/status`}>
              View submitted acknowledgment
            </Link>
          </Button>
        ) : (
          <>
            <label className="check-field">
              <input
                type="checkbox"
                checked={declaration}
                onChange={(e) => setDeclaration(e.target.checked)}
              />
              I confirm that I have reviewed the application and the declared request is ready to
              freeze. This does not submit to AICTE or constitute approval.
            </label>
            <ErrorMessage error={error} />
            <div className="form-actions">
              <Button asChild variant="outline">
                <Link to={`/institution/applications/${s.application_id}/validation`}>
                  Return to precheck
                </Link>
              </Button>
              <Button
                disabled={!declaration || !ready.data?.data.ready || pending || !s.can_submit}
                onClick={() => dialog.current?.showModal()}
              >
                Review submission confirmation
              </Button>
            </div>
          </>
        )}
      </Card>
      <dialog ref={dialog} aria-labelledby="submit-dialog-title" className="submit-dialog">
        <h2 id="submit-dialog-title">Submit this application?</h2>
        <p>
          The saved details, selected evidence versions and checklist will become read-only.
          Repeated requests will reuse the acknowledgment.
        </p>
        <ErrorMessage error={error} />
        <div className="form-actions">
          <Button variant="outline" disabled={pending} onClick={() => dialog.current?.close()}>
            Keep editing
          </Button>
          <Button disabled={pending} onClick={() => void submit()}>
            {pending ? "Submitting saved revision…" : "Confirm submission"}
          </Button>
        </div>
      </dialog>
    </>
  );
}

function ApplicationStatus({ id }: { id: string }) {
  const record = useQuery({
    queryKey: ["institution", "record", id],
    queryFn: () => api<Case>(`/applications/${id}`),
    staleTime: 0,
  });
  const timeline = useQuery({
    queryKey: ["institution", "timeline", id],
    queryFn: () =>
      api<
        {
          id: string;
          event_type: string;
          summary: string;
          created_at: number;
        }[]
      >(`/applications/${id}/timeline`),
  });
  const receipt = useQuery({
    queryKey: ["institution", "receipt", id],
    queryFn: () => api<Receipt>(`/applications/${id}/receipt`),
    staleTime: 0,
  });
  if (record.isPending) return <Wait />;
  if (record.error) return <Wait error={record.error} />;
  const r = receipt.data?.data;
  return (
    <>
      <Card>
        <div className="card-heading">
          <h2>
            {record.data.data.status === "DRAFT" ? "Draft in progress" : "Submission recorded"}
          </h2>
          <Tag>{record.data.data.status.replaceAll("_", " ")}</Tag>
        </div>
        <p>
          {record.data.data.institution_name} · {record.data.data.category} ·{" "}
          {record.data.data.academic_year}
        </p>
        {r ? (
          <>
            <dl className="details">
              <dt>Acknowledgment</dt>
              <dd>{r.acknowledgment}</dd>
              <dt>Submitted at</dt>
              <dd>{new Date(r.submitted_at * 1000).toLocaleString()}</dd>
              <dt>Frozen version</dt>
              <dd>{r.version}</dd>
              <dt>Selected documents</dt>
              <dd>{r.document_count}</dd>
              <dt>Rule version</dt>
              <dd>{r.rule_version}</dd>
              <dt>Manifest SHA-256</dt>
              <dd className="hash">{r.manifest_sha256}</dd>
            </dl>
            <Button asChild variant="outline">
              <a href={`/api/v1/applications/${id}/acknowledgment`} download>
                Download acknowledgment
              </a>
            </Button>
          </>
        ) : receipt.isPending ? (
          <p role="status">Loading acknowledgment…</p>
        ) : receipt.error instanceof ApiError && receipt.error.status === 404 ? (
          <p className="notice">
            {record.data.data.status === "DRAFT"
              ? "An acknowledgment is generated after submission."
              : "This sample record predates the current submission workflow."}
          </p>
        ) : (
          <ErrorMessage error={receipt.error?.message ?? ""} />
        )}
        <div className="form-actions">
          <Button asChild variant="outline">
            <Link to={`/institution/applications/${id}/details`}>
              {record.data.data.status === "DRAFT" ? "Resume draft" : "View locked request"}
            </Link>
          </Button>
          <Button asChild variant="ghost">
            <Link to="/institution/applications">All applications</Link>
          </Button>
        </div>
      </Card>
      <Card>
        <h2>Application timeline</h2>
        {timeline.isPending ? (
          <p role="status">Loading timeline…</p>
        ) : timeline.error ? (
          <ErrorMessage error={timeline.error.message} />
        ) : (
          timeline.data.data.map((t) => (
            <div className="audit-row" key={t.id}>
              <span className="audit-dot" />
              <div>
                <strong>{t.event_type.replaceAll("_", " ")}</strong>
                <p>{t.summary}</p>
                <time>{new Date(t.created_at * 1000).toLocaleString()}</time>
              </div>
            </div>
          ))
        )}
      </Card>
      <Notice>
        Original processing and saved checks are separate from this receipt. No live issuer
        verification or official regulatory approval is implied.
      </Notice>
      <PublishedReports id={id} />
    </>
  );
}

function HistoryPage({ user, recordId }: { user: User; recordId?: string }) {
  const [params, setParams] = useSearchParams();
  const institution =
    params.get("institution") && user.institution_ids.includes(params.get("institution")!)
      ? params.get("institution")!
      : user.institution_ids[0];
  const q = useQuery({
    queryKey: ["institution", "history", institution],
    queryFn: () => api<Snapshot[]>(`/institutions/${institution}/history`),
  });
  const records = useQuery({
    queryKey: ["institution", "history-cases", institution],
    queryFn: () => api<Case[]>("/applications?page_size=100"),
  });
  const [left, setLeft] = useState("");
  const [target, setTarget] = useState("");
  const approved = q.data?.data.filter((s) => s.baseline_eligible) ?? [];
  const imported = q.data?.data.filter((s) => !s.baseline_eligible) ?? [];
  const leftId = left || recordId || approved[1]?.id || approved[0]?.id || "";
  const targetId = target || approved[0]?.id || "";
  const query = new URLSearchParams({
    left_id: leftId,
    ...(targetId.startsWith("app:")
      ? { application_id: targetId.slice(4) }
      : { right_id: targetId }),
  });
  const comparison = useQuery({
    queryKey: ["institution", "history-compare", institution, query.toString()],
    queryFn: () =>
      api<{ changes: Change[] }>(`/institutions/${institution}/history/compare?${query}`),
    enabled: !!leftId && !!targetId,
  });
  const detail = q.data?.data.find((s) => s.id === recordId);
  if (q.isPending) return <Wait />;
  if (q.error) return <Wait error={q.error} retry={() => void q.refetch()} />;
  if (recordId && !detail)
    return (
      <Card>
        <h2>Historical record unavailable</h2>
        <p>Select an authorized snapshot from your history timeline.</p>
        <Link to="/institution/history">Back to history</Link>
      </Card>
    );
  const show = (s: Snapshot) => (
    <Card key={s.id}>
      <div className="card-heading">
        <History size={20} />
        <h2>
          {s.academic_year} {s.baseline_eligible ? "approved baseline" : "imported record"}
        </h2>
        <Tag>{s.source_status.replaceAll("_", " ")}</Tag>
      </div>
      <h3>{s.profile.name}</h3>
      <dl className="details">
        <dt>Approval reference</dt>
        <dd>{s.payload.approval_reference ?? "Synthetic reference in source metadata"}</dd>
        <dt>Provenance</dt>
        <dd>{s.source_ref}</dd>
        <dt>Baseline eligibility</dt>
        <dd>
          {s.baseline_eligible
            ? "Eligible; read-only snapshot"
            : "Unverified; excluded from all approved baselines"}
        </dd>
      </dl>
      <div className="table-scroll">
        <table className="history-courses">
          <caption className="sr-only">Approved course and intake history</caption>
          <thead>
            <tr>
              <th>Course</th>
              <th>Level</th>
              <th>Approved intake</th>
            </tr>
          </thead>
          <tbody>
            {s.profile.courses.map((c) => (
              <tr key={c.course}>
                <td>{c.course}</td>
                <td>{c.level}</td>
                <td>{c.approved_intake}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {recordId ? (
        <>
          <h3 className="subheading">Recorded changes and prior corrective actions</h3>
          {s.payload.changes?.map((c) => (
            <p key={c}>{c}</p>
          ))}
          {s.payload.prior_findings?.map((f) => (
            <p key={f.summary}>
              {f.summary} — {f.corrective_action}
            </p>
          ))}
          <p className="notice">
            No source approval-letter file is attached to this historical reference. No document
            preview is fabricated.
          </p>
          <Link to={`/institution/history?institution=${institution}`}>Back to timeline</Link>
        </>
      ) : (
        <Link to={`/institution/history/${s.id}?institution=${institution}`}>
          View snapshot <ArrowRight size={16} />
        </Link>
      )}
      <p className="readonly-note">
        Read-only source record. Drafts, disputed claims and proposed intake are stored separately.
      </p>
    </Card>
  );
  return (
    <>
      <Notice>
        History is grouped by provenance. Imported/unverified entries never supply the approved
        baseline for a new application.
      </Notice>
      {user.institution_ids.length > 1 && (
        <label className="field">
          Institution scope
          <select
            value={institution}
            onChange={(e) => {
              setParams({ institution: e.target.value });
              setLeft("");
              setTarget("");
            }}
          >
            {user.institution_ids.map((i) => (
              <option key={i}>{i}</option>
            ))}
          </select>
        </label>
      )}
      {recordId && detail ? (
        show(detail)
      ) : (
        <>
          <h2>Approved records</h2>
          <div className="history-list">
            {approved.length ? (
              approved.map(show)
            ) : (
              <Card>
                <p>No approved history available.</p>
              </Card>
            )}
          </div>
          {imported.length > 0 && (
            <>
              <h2 className="subheading">Imported / unverified records</h2>
              <div className="history-list">{imported.map(show)}</div>
            </>
          )}
        </>
      )}
      <Card className="history-comparison">
        <h2>Compare approved history or a current request</h2>
        <div className="form-grid">
          <label className="field">
            Approved baseline to compare
            <select value={leftId} onChange={(e) => setLeft(e.target.value)}>
              {approved.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.academic_year} · {s.source_status}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            Compare with
            <select value={targetId} onChange={(e) => setTarget(e.target.value)}>
              {approved.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.academic_year} approved snapshot
                </option>
              ))}
              {records.data?.data
                .filter((a) => a.institution_id === institution && a.catalogue_id)
                .map((a) => (
                  <option key={a.id} value={`app:${a.id}`}>
                    {a.category} · {a.academic_year} · {a.id.slice(0, 8)} ({a.status})
                  </option>
                ))}
            </select>
          </label>
        </div>
        {comparison.isFetching ? (
          <p role="status">Comparing saved values…</p>
        ) : comparison.error ? (
          <ErrorMessage error={comparison.error.message} />
        ) : comparison.data ? (
          <ChangeList changes={comparison.data.data.changes} />
        ) : (
          <p>Select two eligible records.</p>
        )}
      </Card>
    </>
  );
}
