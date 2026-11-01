import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type User } from "../api";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { type Row, record, rows, value, mutate, Fields, Loading } from "./common";

export function GovernanceContent({ routeId, user }: { routeId: string; user: User }) {
  if (routeId === "A04") return <AuditGovernance />;
  if (routeId === "A01") return <AccessGovernance />;
  if (routeId === "A03") return <ConnectorGovernance />;
  return <VersionGovernance source={routeId === "A05"} user={user} />;
}
function AccessGovernance() {
  const qc = useQueryClient();
  const [target, setTarget] = useState("");
  const [command, setCommand] = useState("REVOKE_SESSIONS");
  const [role, setRole] = useState("officer");
  const [tenant, setTenant] = useState("");
  const [application, setApplication] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const q = useQuery({
    queryKey: ["governance", "users"],
    queryFn: () => api<Row[]>("/governance/users"),
  });
  if (q.isPending || q.error) return <Loading error={q.error} retry={() => void q.refetch()} />;
  async function submit() {
    setBusy(true);
    setError("");
    try {
      await mutate(`/governance/users/${target}`, {
        action: command,
        rationale: reason,
        role,
        institution_id: tenant || null,
        application_id: application || null,
      });
      setNotice("Access change recorded. Existing sessions are revoked where required.");
      await qc.invalidateQueries({ queryKey: ["governance"] });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Card>
        <h2>Identity and membership directory</h2>
        {!q.data.data.length && <p>No identities are available in this authorized directory.</p>}
        {q.data.data.map((u) => (
          <article key={value(u.id)} className="observation-row">
            <h3>{value(u.name)}</h3>
            <p>
              {value(u.email)} · {u.active ? "Active" : "Suspended"}
            </p>
            <details>
              <summary>Current role and tenant memberships</summary>
              {rows(u.memberships).map((m) => (
                <Fields key={value(m.id)} data={m} />
              ))}
            </details>
          </article>
        ))}
      </Card>
      <Card>
        <h2>Audited access change</h2>
        <label className="field">
          Target user
          <select value={target} onChange={(e) => setTarget(e.target.value)}>
            <option value="">Choose user</option>
            {q.data.data.map((u) => (
              <option key={value(u.id)} value={value(u.id)}>
                {value(u.name)} · {value(u.email)}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          Access operation
          <select value={command} onChange={(e) => setCommand(e.target.value)}>
            {[
              "ACTIVATE",
              "DEACTIVATE",
              "REVOKE_SESSIONS",
              "GRANT_ROLE",
              "REVOKE_ROLE",
              "GRANT_CONTENT",
            ].map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </label>
        <label className="field">
          Role
          <select value={role} onChange={(e) => setRole(e.target.value)}>
            {[
              "institution_admin",
              "institution_submitter",
              "officer",
              "specialist",
              "supervisor",
              "admin",
              "auditor",
            ].map((r) => (
              <option key={r}>{r}</option>
            ))}
          </select>
        </label>
        <label className="field">
          Institution ID (required for institution roles)
          <input value={tenant} onChange={(e) => setTenant(e.target.value)} />
        </label>
        <label className="field">
          Application ID for explicit one-hour content grant
          <input value={application} onChange={(e) => setApplication(e.target.value)} />
        </label>
        <label className="field">
          Access-change rationale
          <textarea value={reason} maxLength={2000} onChange={(e) => setReason(e.target.value)} />
        </label>
        <Button disabled={busy || !target || reason.length < 10} onClick={() => void submit()}>
          Apply audited access change
        </Button>
        {error && <p role="alert">{error}</p>}
        {notice && <p role="status">{notice}</p>}
        <p>
          Platform administration alone does not grant document access. Self-suspension and
          self-privilege removal require another administrator.
        </p>
      </Card>
    </>
  );
}
function ConnectorGovernance() {
  const qc = useQueryClient();
  const [id, setId] = useState("");
  const [mode, setMode] = useState("MOCK");
  const [status, setStatus] = useState("AVAILABLE");
  const [reference, setReference] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const q = useQuery({
    queryKey: ["governance", "connectors"],
    queryFn: () => api<Row[]>("/admin/integrations"),
  });
  if (q.isPending || q.error) return <Loading error={q.error} retry={() => void q.refetch()} />;
  async function submit() {
    setError("");
    try {
      await mutate(`/governance/connectors/${id}`, {
        mode,
        status,
        secret_reference: reference || null,
        rationale: reason,
      });
      setNotice("Connector configuration saved with audit attribution.");
      await qc.invalidateQueries({ queryKey: ["governance"] });
    } catch (e) {
      setError((e as Error).message);
    }
  }
  return (
    <>
      <Card>
        <h2>Provider capability and mode</h2>
        {!q.data.data.length && <p>No connectors have been configured.</p>}
        {q.data.data.map((c) => (
          <Fields key={value(c.id)} data={c} />
        ))}
        <p>
          MOCK registry outcomes are synthetic. C2PA and PDF signatures run locally with offline
          trust configuration. Live issuer and provider watermark services remain unavailable
          without approved adapters and credentials. Missing signals never mean genuine or forged.
        </p>
        <p>
          Issuer retries are capped at three per original/provider. Service outages retain explicit
          pending/manual states.
        </p>
      </Card>
      <Card>
        <h2>Govern connector configuration</h2>
        <label className="field">
          Connector
          <select value={id} onChange={(e) => setId(e.target.value)}>
            <option value="">Choose connector</option>
            {q.data.data.map((c) => (
              <option key={value(c.id)} value={value(c.id)}>
                {value(c.name)}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          Adapter mode
          <select value={mode} onChange={(e) => setMode(e.target.value)}>
            <option>MOCK</option>
            <option>LIVE</option>
          </select>
        </label>
        <label className="field">
          Support/health status
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option>AVAILABLE</option>
            <option>UNAVAILABLE</option>
            <option>MAINTENANCE</option>
          </select>
        </label>
        <label className="field">
          Secret-manager reference only
          <input
            placeholder="secret://issuer/demo"
            value={reference}
            onChange={(e) => setReference(e.target.value)}
          />
        </label>
        <label className="field">
          Configuration rationale
          <textarea value={reason} onChange={(e) => setReason(e.target.value)} />
        </label>
        <Button disabled={!id || reason.length < 10} onClick={() => void submit()}>
          Save connector configuration
        </Button>
        {error && <p role="alert">{error}</p>}
        {notice && <p role="status">{notice}</p>}
      </Card>
    </>
  );
}
function AuditGovernance() {
  const [operation, setOperation] = useState("");
  const [actor, setActor] = useState("");
  const [page, setPage] = useState(1);
  const params = new URLSearchParams({
    operation,
    actor_id: actor,
    page: String(page),
  });
  const q = useQuery({
    queryKey: ["governance", "audit", params.toString()],
    queryFn: () => api<Row[]>(`/governance/audit?${params}`),
  });
  return (
    <>
      <Card>
        <h2>Restricted append-only audit metadata</h2>
        <div className="filter-grid">
          <label className="field">
            Operation filter
            <input
              value={operation}
              onChange={(e) => {
                setOperation(e.target.value);
                setPage(1);
              }}
            />
          </label>
          <label className="field">
            Actor ID filter
            <input
              value={actor}
              onChange={(e) => {
                setActor(e.target.value);
                setPage(1);
              }}
            />
          </label>
        </div>
        <a className="audit-export-link" href={`/api/v1/governance/audit/export?${params}`}>
          Export this filtered metadata subset (maximum 2,000 events)
        </a>
        <p>
          Exports contain identifiers, actions, timestamps and metadata digests; document contents
          and secret values are excluded. Export access is itself audited.
        </p>
      </Card>
      {q.isPending || q.error ? (
        <Loading error={q.error} retry={() => void q.refetch()} />
      ) : (
        <Card>
          {q.data.data.map((r) => (
            <Fields key={value(r.id)} data={r} />
          ))}
          {!q.data.data.length && <p>No audit events match this filter.</p>}
          <div className="form-actions">
            <Button disabled={page === 1} onClick={() => setPage(page - 1)}>
              Previous audit page
            </Button>
            <span>Page {page}</span>
            <Button
              disabled={page * 20 >= (q.data.meta.total ?? 0)}
              onClick={() => setPage(page + 1)}
            >
              Next audit page
            </Button>
          </div>
        </Card>
      )}
    </>
  );
}
function VersionGovernance({ source, user }: { source: boolean; user: User }) {
  const qc = useQueryClient();
  const [code, setCode] = useState("");
  const [reason, setReason] = useState("");
  const [sourceId, setSourceId] = useState("");
  const [text, setText] = useState("");
  const [title, setTitle] = useState("");
  const [url, setUrl] = useState("https://www.aicte.gov.in/sites/default/files/APH%20Final.pdf");
  const [clause, setClause] = useState("Annexure 3.2.1");
  const [printed, setPrinted] = useState(87);
  const [pdf, setPdf] = useState(103);
  const [minimum, setMinimum] = useState(66);
  const [division, setDivision] = useState(60);
  const [year, setYear] = useState("2026-27");
  const [programme, setProgramme] = useState("Engineering & Technology");
  const [category, setCategory] = useState("EOA");
  const [stage, setStage] = useState("SCRUTINY");
  const [effectiveFrom, setEffectiveFrom] = useState("2026-01-01");
  const [effectiveUntil, setEffectiveUntil] = useState("2027-12-31");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [dry, setDry] = useState<Row | null>(null);
  const [query, setQuery] = useState("engineering classroom carpet area");
  const [retrieval, setRetrieval] = useState<Row | null>(null);
  const [busy, setBusy] = useState(false);
  const q = useQuery({
    queryKey: ["governance", "versions"],
    queryFn: () => api<Row[]>("/governance/versions"),
  });
  const health = useQuery({
    queryKey: ["governance", "knowledge-health"],
    queryFn: () => api<Row>("/governance/knowledge-health"),
    enabled: source,
  });
  if (q.isPending || q.error) return <Loading error={q.error} retry={() => void q.refetch()} />;
  const kind = source ? "SOURCE" : "RULE";
  const items = q.data.data.filter((v) => v.kind === kind);
  async function run(path: string, body: Row) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await mutate(path, body);
      setNotice("Governed change saved with approval/audit attribution.");
      await qc.invalidateQueries({ queryKey: ["governance"] });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function create() {
    const scope = {
      years: [year],
      categories: [category],
      programmes: [programme],
      stages: [stage],
      effective_from: effectiveFrom,
      effective_until: effectiveUntil,
      roles: ["officer", "specialist", "supervisor", "admin"],
    };
    const payload = source
      ? {
          scope,
          title,
          source_url: url,
          publication_date: effectiveFrom,
          clause,
          printed_page: printed,
          pdf_page: pdf,
          text,
          interpretation: "SRS_DEMO_TRANSCRIPTION",
        }
      : {
          scope,
          metric: "CLASSROOM_AREA_MINIMUM",
          minimum,
          division,
          exception_codes: [],
        };
    await run("/governance/versions", {
      kind,
      code,
      source_id: source ? null : sourceId,
      payload,
      rationale: reason,
    });
  }
  async function dryRun(id: string) {
    try {
      setDry((await api<Row>(`/governance/versions/${id}/dry-run`)).data);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function search() {
    try {
      const r = await mutate("/knowledge/retrieve", {
        query,
        academic_year: year,
        category,
        programme,
        stage,
        reference_date: effectiveFrom,
      });
      setRetrieval(r.data);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  return (
    <>
      <Card>
        <h2>{source ? "Approved-source manager" : "Versioned rule library"}</h2>
        {source && health.data && <Fields data={health.data.data} />}
        <p>
          Draft, source approval and rule publication are separate operations. A different
          administrative identity must approve and publish a draft. Ingestion never publishes a
          regulatory rule.
        </p>
        <p>
          Signed in: {user.name}. Seed records are reviewed SRS demonstration transcriptions;
          current official interpretation remains a production sign-off dependency.
        </p>
        {error && <p role="alert">{error}</p>}
        {notice && <p role="status">{notice}</p>}
        {items.length ? (
          items.map((v) => (
            <article key={value(v.id)} className="observation-row">
              <h3>
                {value(v.code)} · version {value(v.number)} · {value(v.status)}
              </h3>
              <p>
                Content checksum: <span className="hash">{value(v.checksum)}</span> ·{" "}
                {value(v.checksum_scope)}
              </p>
              <p>
                Approved{" "}
                {v.approved_at
                  ? new Date(Number(v.approved_at) * 1000).toLocaleString()
                  : "Pending"}{" "}
                · published{" "}
                {v.published_at
                  ? new Date(Number(v.published_at) * 1000).toLocaleString()
                  : "Pending"}
              </p>
              <p>
                Drafted by {value(v.author_id)} · approved by {value(v.approver_id)} ·{" "}
                {new Date(Number(v.created_at) * 1000).toLocaleString()}
              </p>
              <details>
                <summary>Scope, source and immutable definition</summary>
                <Fields data={record(v.payload)} />
              </details>
              <div className="form-actions">
                {v.kind === "RULE" && (
                  <Button variant="outline" onClick={() => void dryRun(value(v.id))}>
                    Dry-run saved rule
                  </Button>
                )}
                {v.status === "DRAFT" && (
                  <Button
                    disabled={busy || reason.length < 10 || v.author_id === user.id}
                    onClick={() =>
                      void run(`/governance/versions/${value(v.id)}/action`, {
                        action: "APPROVE",
                        rationale: reason,
                      })
                    }
                  >
                    Approve with separate identity
                  </Button>
                )}
                {v.status === "APPROVED" && v.kind === "RULE" && (
                  <Button
                    disabled={busy || reason.length < 10 || v.author_id === user.id}
                    onClick={() =>
                      void run(`/governance/versions/${value(v.id)}/action`, {
                        action: "PUBLISH",
                        rationale: reason,
                      })
                    }
                  >
                    Publish approved rule
                  </Button>
                )}
                {source && v.status === "APPROVED" && (
                  <Button
                    variant="outline"
                    disabled={busy || reason.length < 10}
                    onClick={() =>
                      void run(`/governance/versions/${value(v.id)}/reindex`, {
                        rationale: reason,
                      })
                    }
                  >
                    Append source reindex
                  </Button>
                )}
                {["APPROVED", "PUBLISHED"].includes(value(v.status)) && (
                  <Button
                    variant="outline"
                    disabled={busy || reason.length < 10}
                    onClick={() =>
                      void run(`/governance/versions/${value(v.id)}/action`, {
                        action: "SUPERSEDE",
                        rationale: reason,
                      })
                    }
                  >
                    Supersede this version
                  </Button>
                )}
              </div>
            </article>
          ))
        ) : (
          <p>No governed versions yet. Register a draft below.</p>
        )}
        {dry && (
          <>
            <h3>Saved-rule synthetic dry run</h3>
            <Fields data={dry} />
          </>
        )}
      </Card>
      <Card>
        <h2>Create an additional immutable {source ? "source" : "rule"} draft</h2>
        <div className="filter-grid">
          <label className="field">
            Version family code
            <input
              placeholder="CLASSROOM_REVIEW"
              value={code}
              onChange={(e) => setCode(e.target.value.toUpperCase())}
            />
          </label>
          <label className="field">
            Applicable academic year
            <input value={year} onChange={(e) => setYear(e.target.value)} />
          </label>
          <label className="field">
            Category
            <select value={category} onChange={(e) => setCategory(e.target.value)}>
              <option>EOA</option>
              <option>INTAKE_INCREASE</option>
            </select>
          </label>
          <label className="field">
            Programme
            <select value={programme} onChange={(e) => setProgramme(e.target.value)}>
              <option>Engineering &amp; Technology</option>
              <option>Management</option>
            </select>
          </label>
          <label className="field">
            Due/evaluation stage
            <select value={stage} onChange={(e) => setStage(e.target.value)}>
              <option>SCRUTINY</option>
              <option>EVC</option>
              <option>SUBMISSION</option>
            </select>
          </label>
          <label className="field">
            Effective from
            <input
              type="date"
              value={effectiveFrom}
              onChange={(e) => setEffectiveFrom(e.target.value)}
            />
          </label>
          <label className="field">
            Effective until
            <input
              type="date"
              value={effectiveUntil}
              onChange={(e) => setEffectiveUntil(e.target.value)}
            />
          </label>
        </div>
        {source ? (
          <>
            <label className="field">
              Source title
              <input value={title} onChange={(e) => setTitle(e.target.value)} />
            </label>
            <label className="field">
              Official/source HTTPS URL
              <input type="url" value={url} onChange={(e) => setUrl(e.target.value)} />
            </label>
            <label className="field">
              Exact clause
              <input value={clause} onChange={(e) => setClause(e.target.value)} />
            </label>
            <div className="form-actions">
              <label className="field">
                Printed page
                <input
                  type="number"
                  min={1}
                  value={printed}
                  onChange={(e) => setPrinted(Number(e.target.value))}
                />
              </label>
              <label className="field">
                PDF page
                <input
                  type="number"
                  min={1}
                  value={pdf}
                  onChange={(e) => setPdf(Number(e.target.value))}
                />
              </label>
            </div>
            <label className="field">
              Curated source passage
              <textarea maxLength={10000} value={text} onChange={(e) => setText(e.target.value)} />
            </label>
            <p>
              The source URL is recorded as provenance. It is not fetched automatically. Passage
              checksum and approval attribution are saved before retrieval is enabled.
            </p>
          </>
        ) : (
          <>
            <label className="field">
              Approved controlling source
              <select value={sourceId} onChange={(e) => setSourceId(e.target.value)}>
                <option value="">Choose approved source</option>
                {q.data.data
                  .filter((v) => v.kind === "SOURCE" && v.status === "APPROVED")
                  .map((v) => (
                    <option key={value(v.id)} value={value(v.id)}>
                      {value(v.code)} v{value(v.number)}
                    </option>
                  ))}
              </select>
            </label>
            <label className="field">
              Selected classroom minimum m²
              <input
                type="number"
                min={1}
                max={1000}
                value={minimum}
                onChange={(e) => setMinimum(Number(e.target.value))}
              />
            </label>
            <label className="field">
              Applicable division size
              <select value={division} onChange={(e) => setDivision(Number(e.target.value))}>
                <option value={60}>60</option>
                <option value={30}>30</option>
              </select>
            </label>
          </>
        )}
        <label className="field">
          Governance rationale (also used for approval/publication actions)
          <textarea value={reason} maxLength={2000} onChange={(e) => setReason(e.target.value)} />
        </label>
        <Button
          disabled={
            busy ||
            code.length < 3 ||
            reason.length < 10 ||
            (source ? title.length < 5 || text.length < 20 : !sourceId)
          }
          onClick={() => void create()}
        >
          Create {source ? "source" : "rule"} draft
        </Button>
      </Card>
      {source && (
        <Card>
          <h2>Retrieval capability and citation test</h2>
          <p>
            Only approved, effective, applicable, access-permitted passages are ranked. The result
            identifies PostgreSQL full-text, keyword fallback, or actual pgvector hybrid mode; a
            missing citation produces abstention.
          </p>
          <label className="field">
            Retrieval test question
            <input value={query} onChange={(e) => setQuery(e.target.value)} />
          </label>
          <Button onClick={() => void search()}>Test approved retrieval</Button>
          {retrieval && <Fields data={retrieval} />}
        </Card>
      )}
    </>
  );
}
