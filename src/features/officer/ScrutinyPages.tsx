import { useState } from "react";
import { Link } from "@/features/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type User } from "../api";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { EvidenceViewer } from "./EvidenceViewer";
import { label } from "../presentation";
import { type Row, record, rows, value, mutate, Loading, Fields } from "./common";

const endpoint: Record<string, string> = {
  O01: "/officer/workload",
  O02: "/officer/queue",
  O03: "",
  O05: "/authenticity",
  O06: "/compliance",
  O07: "/infrastructure",
  O08: "",
  O09: "/officer/tasks",
  O10: "/officer/reports",
};
export function ScrutinyContent({
  routeId,
  caseId,
  user,
}: {
  routeId: string;
  caseId?: string;
  user: User;
}) {
  if (routeId === "O04" && caseId) return <EvidenceViewer key={caseId} id={caseId} user={user} />;
  return (
    <ScrutinyPage
      key={`${routeId}:${caseId ?? ""}`}
      routeId={routeId}
      caseId={caseId}
      user={user}
    />
  );
}
function ScrutinyPage({ routeId, caseId, user }: { routeId: string; caseId?: string; user: User }) {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [year, setYear] = useState("");
  const [category, setCategory] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [unassigned, setUnassigned] = useState(false);
  const [finding, setFinding] = useState("");
  const [disposition, setDisposition] = useState("ACKNOWLEDGED");
  const [rationale, setRationale] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [command, setCommand] = useState("OBSERVATION");
  const [published, setPublished] = useState(false);
  const [responseFields, setResponseFields] = useState<string[]>([]);
  const [responseType, setResponseType] = useState("FIRE_SAFETY");
  const [requireResponseDocument, setRequireResponseDocument] = useState(false);
  const [responseDeadline, setResponseDeadline] = useState(() =>
    new Date(Date.now() + 7 * 86400000 - new Date().getTimezoneOffset() * 60000)
      .toISOString()
      .slice(0, 16),
  );
  const [priority, setPriority] = useState(50);
  const [assignee, setAssignee] = useState("");
  const [kind, setKind] = useState("ISSUER");
  const [selected, setSelected] = useState("");
  const [provider, setProvider] = useState("");
  const [scenario, setScenario] = useState("match");
  const [cert, setCert] = useState("");
  const [area, setArea] = useState(58);
  const [division, setDivision] = useState(60);
  const [room, setRoom] = useState("");
  const [sourceRef, setSourceRef] = useState("");
  const [sourcePage, setSourcePage] = useState(1);
  const [sourceBox, setSourceBox] = useState([0, 0, 595, 842]);
  const [reliable, setReliable] = useState(false);
  const [ragQuery, setRagQuery] = useState("engineering classroom carpet area");
  const [rag, setRag] = useState<Row | null>(null);
  const caseRoute = !!caseId;
  const params = new URLSearchParams({
    page: String(page),
    ...(unassigned ? { unassigned: "true" } : {}),
    ...(search ? { search } : {}),
    ...(year ? { year } : {}),
    ...(category ? { category } : {}),
    ...(status ? { status } : {}),
  });
  const path = caseRoute
    ? `/officer/cases/${caseId}${endpoint[routeId]}`
    : endpoint[routeId] + (routeId === "O02" ? `?${params}` : "");
  const q = useQuery({
    queryKey: ["scrutiny", routeId, caseId, params.toString()],
    queryFn: () => api<Row | Row[]>(path),
    refetchInterval: routeId === "O08" ? 5000 : false,
  });
  const evidence = useQuery({
    queryKey: ["scrutiny", "evidence", caseId],
    queryFn: () => api<Row>(`/officer/cases/${caseId}/evidence`),
    enabled: !!caseId && ["O05", "O07"].includes(routeId),
  });
  const people = useQuery({
    queryKey: ["scrutiny", "routing-users"],
    queryFn: () => api<Row[]>("/officer/routing-users"),
    enabled: routeId === "O08",
  });
  const clarificationReview = useQuery({
    queryKey: ["scrutiny", "clarification-review", caseId],
    queryFn: () => api<Row[]>(`/officer/cases/${caseId}/clarifications`),
    enabled: routeId === "O08",
    refetchInterval: 5000,
  });
  if (q.isPending || q.error) return <Loading error={q.error} retry={() => void q.refetch()} />;
  const data = record(q.data.data);
  const list = rows(q.data.data);
  const review = record(data.review);
  const canWrite = user.roles.some((r) => ["officer", "supervisor"].includes(r));
  async function send(suffix: string, fields: Row = {}) {
    setError("");
    setNotice("");
    setBusy(true);
    try {
      const result = await mutate(`/officer/cases/${caseId}/${suffix}`, {
        expected_version: review.version,
        rationale,
        ...fields,
      });
      setNotice("Saved with attribution. " + value(result.data.status ?? result.data.state ?? ""));
      await qc.invalidateQueries({ queryKey: ["scrutiny"] });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function retrieve() {
    setBusy(true);
    setError("");
    try {
      const r = await mutate("/knowledge/retrieve", {
        query: ragQuery,
        ...Object.fromEntries(
          ["academic_year", "category", "programme", "stage", "reference_date"].map((k) => [
            k,
            record(data.context)[k],
          ]),
        ),
      });
      setRag(r.data);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      {error && <p role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}
      {routeId === "O01" && (
        <>
          <Card>
            <h2>Assigned workload</h2>
            <Fields
              data={{
                assigned: data.assigned,
                overdue: data.overdue,
                pending_verification: data.pending_verification,
              }}
            />
          </Card>
          <CaseRows items={rows(data.cases)} />
        </>
      )}
      {routeId === "O02" && (
        <>
          <Card>
            <div className="filter-grid">
              {user.roles.includes("supervisor") && (
                <label className="check-field">
                  <input
                    type="checkbox"
                    checked={unassigned}
                    onChange={(e) => {
                      setUnassigned(e.target.checked);
                      setPage(1);
                    }}
                  />
                  Permitted unassigned cases only
                </label>
              )}
              <label className="field">
                Institution search
                <input
                  value={search}
                  onChange={(e) => {
                    setSearch(e.target.value);
                    setPage(1);
                  }}
                />
              </label>
              <label className="field">
                Academic year
                <input
                  placeholder="2026-27"
                  value={year}
                  onChange={(e) => {
                    setYear(e.target.value);
                    setPage(1);
                  }}
                />
              </label>
              <label className="field">
                Category
                <select
                  value={category}
                  onChange={(e) => {
                    setCategory(e.target.value);
                    setPage(1);
                  }}
                >
                  <option value="">All categories</option>
                  <option>EOA</option>
                  <option>INTAKE_INCREASE</option>
                  <option>Routine EoA</option>
                </select>
              </label>
              <label className="field">
                Status
                <select
                  value={status}
                  onChange={(e) => {
                    setStatus(e.target.value);
                    setPage(1);
                  }}
                >
                  <option value="">All statuses</option>
                  {[
                    "SUBMITTED",
                    "UNDER_REVIEW",
                    "PENDING_VERIFICATION",
                    "CLARIFICATION_REQUESTED",
                    "INSPECTION_RECOMMENDED",
                    "REVIEW_COMPLETED",
                  ].map((s) => (
                    <option key={s}>{s}</option>
                  ))}
                </select>
              </label>
            </div>
          </Card>
          <CaseRows items={list} />
          <div className="form-actions">
            <Button disabled={page === 1} onClick={() => setPage(page - 1)}>
              Previous queue page
            </Button>
            <span>
              Page {page} · {q.data.meta.total} cases
            </span>
            <Button
              disabled={page * 20 >= (q.data.meta.total ?? 0)}
              onClick={() => setPage(page + 1)}
            >
              Next queue page
            </Button>
          </div>
        </>
      )}
      {["O03", "O08"].includes(routeId) && (
        <>
          <Card>
            <h2>{value(record(data.case).institution_name)}</h2>
            <h3>Submitted case and current review</h3>
            <Fields
              data={{
                ...record(data.case),
                review_version: review.version,
                due_at: new Date(Number(review.due_at) * 1000).toLocaleString(),
              }}
            />
            <h3>Requested changes and approved history</h3>
            {data.workflow ? (
              <>
                <Fields data={record(record(data.workflow).details)} />
                <details>
                  <summary>Read-only approved baseline</summary>
                  <Fields data={record(record(record(data.workflow).baseline).profile)} />
                </details>
              </>
            ) : (
              <Fields data={record(data.requested)} />
            )}
            <h3>Service progress and limitations</h3>
            {rows(data.services).map((s) => (
              <Fields key={value(s.service)} data={s} />
            ))}
            <h3>Interpretable priority</h3>
            <Fields data={record(data.priority)} />
          </Card>
          <Findings
            id={caseId!}
            items={rows(data.findings).map((f) => ({
              ...record(f.payload),
              id: f.id,
            }))}
          />
          <Card>
            <h2>Attributed human actions</h2>
            {rows(data.actions).map((a) => (
              <article key={value(a.id)}>
                <strong>{value(a.action)}</strong>
                <p>{value(a.rationale)}</p>
                <small>
                  Actor {value(a.actor_id)} ·{" "}
                  {new Date(Number(a.created_at) * 1000).toLocaleString()} ·{" "}
                  {a.publishable ? "Explicitly institution-visible" : "Officer private"}
                </small>
              </article>
            ))}
            {!rows(data.actions).length && <p>No human actions recorded.</p>}
          </Card>
        </>
      )}
      {routeId === "O05" && (
        <>
          <Card>
            <h2>Issuer results</h2>
            {rows(data.issuer).length ? (
              rows(data.issuer).map((r) => <Fields key={value(r.id)} data={r} />)
            ) : (
              <p>No issuer response. Verification has not occurred.</p>
            )}
          </Card>
          <Card>
            <h2>Independent provenance methods</h2>
            {rows(data.provenance).length ? (
              rows(data.provenance).map((r) => (
                <article key={value(r.id)}>
                  <h3>
                    {value(r.method)} · {value(r.outcome)}
                  </h3>
                  <Fields data={record(r.payload)} />
                </article>
              ))
            ) : (
              <p>No provenance check yet. No signal is inconclusive.</p>
            )}
          </Card>
        </>
      )}
      {routeId === "O06" && (
        <>
          <Card>
            <h2>Saved rule evaluation</h2>
            <Fields data={record(data.context)} />
            <p>{value(data.state)}</p>
          </Card>
          <Findings id={caseId!} items={rows(data.results)} />
          <Card>
            <h2>Approved-source explanation</h2>
            <label className="field">
              Search applicable approved passages
              <input value={ragQuery} onChange={(e) => setRagQuery(e.target.value)} />
            </label>
            <Button disabled={busy} onClick={() => void retrieve()}>
              Retrieve cited explanation
            </Button>
            {rag && (
              <>
                <p>Retrieval mode: {value(rag.mode)}</p>
                <p>{value(rag.answer ?? rag.reason)}</p>
                {rows(rag.citations).map((c) => (
                  <blockquote key={value(c.id)}>
                    <p>{value(c.excerpt)}</p>
                    <a href={value(c.source_url)} target="_blank" rel="noreferrer">
                      {value(c.clause)} · printed {value(c.printed_page)} / PDF {value(c.pdf_page)}
                    </a>
                    <small>
                      Source version {value(c.source_version)} · checksum {value(c.checksum)}
                    </small>
                  </blockquote>
                ))}
              </>
            )}
          </Card>
        </>
      )}
      {routeId === "O07" && (
        <>
          <Card>
            <h2>Declared and certified rooms</h2>
            {rows(data.rooms).map((r) => (
              <article key={value(r.id)}>
                <h3>
                  {value(r.room_code)} · declared {value(r.declared_area)} m²
                </h3>
                {rows(r.certified).map((c) => (
                  <Fields key={value(c.id)} data={c} />
                ))}
              </article>
            ))}
            {!rows(data.rooms).length && (
              <p>
                No room inventory. A targeted evidence request is required; no deficiency is
                inferred.
              </p>
            )}
            <Link to={`/officer/applications/${caseId}/compliance`}>
              Inspect separate factual mismatch and potential rule deficiency
            </Link>
            <p>
              Photographs alone do not establish certified carpet area. Inspection recommendations
              require sourced reasons.
            </p>
          </Card>
        </>
      )}
      {canWrite && caseRoute && (
        <Card>
          <h2>Authorized review action</h2>
          <label className="field">
            Action rationale
            <textarea
              minLength={10}
              maxLength={2000}
              value={rationale}
              onChange={(e) => setRationale(e.target.value)}
            />
          </label>
          {routeId === "O03" && (
            <>
              <label className="field">
                Review priority override (0–100)
                <input
                  type="number"
                  min={0}
                  max={100}
                  value={priority}
                  onChange={(e) => setPriority(Number(e.target.value))}
                />
              </label>
              <Button
                disabled={busy || rationale.length < 10}
                onClick={() => void send("priority", { priority })}
              >
                Save priority override
              </Button>
            </>
          )}
          {routeId === "O05" && (
            <>
              <label className="field">
                Checked original
                <select value={selected} onChange={(e) => setSelected(e.target.value)}>
                  <option value="">Choose original</option>
                  {rows(evidence.data?.data.versions).map((v) => (
                    <option key={value(v.id)} value={value(v.id)}>
                      {value(v.name)} · v{value(v.number)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                Issuer provider
                <select value={provider} onChange={(e) => setProvider(e.target.value)}>
                  <option value="">Choose provider</option>
                  {rows(data.connectors).map((c) => (
                    <option key={value(c.id)} value={value(c.id)}>
                      {value(c.name)} · {value(c.mode)} / {value(c.status)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                Certificate identifier
                <input value={cert} onChange={(e) => setCert(e.target.value)} />
              </label>
              <label className="field">
                Demonstration issuer response
                <select value={scenario} onChange={(e) => setScenario(e.target.value)}>
                  {["match", "conflict", "timeout", "unsupported"].map((s) => (
                    <option key={s}>{s}</option>
                  ))}
                </select>
              </label>
              <div className="form-actions">
                <Button
                  disabled={busy || !selected || !provider || !cert || rationale.length < 10}
                  onClick={() =>
                    void send("issuer", {
                      version_id: selected,
                      provider_id: provider,
                      certificate_id: cert,
                      fixture: scenario,
                    })
                  }
                >
                  Run labelled issuer check
                </Button>
                <Button
                  variant="outline"
                  disabled={busy || !selected || rationale.length < 10}
                  onClick={() => void send(`provenance/${selected}`)}
                >
                  Verify available local provenance
                </Button>
              </div>
            </>
          )}
          {routeId === "O06" && (
            <>
              <Button
                disabled={busy || rationale.length < 10}
                onClick={() => void send("compliance")}
              >
                Save deterministic recheck
              </Button>
              <label className="field">
                Saved finding to review
                <select value={finding} onChange={(e) => setFinding(e.target.value)}>
                  <option value="">Choose finding</option>
                  {rows(data.findings).map((f) => (
                    <option key={value(f.id)} value={value(f.id)}>
                      {value(f.code)} · {value(f.amount_m2)} m²
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                Human disposition
                <select value={disposition} onChange={(e) => setDisposition(e.target.value)}>
                  <option>ACKNOWLEDGED</option>
                  <option>DISPUTED</option>
                </select>
              </label>
              <Button
                variant="outline"
                disabled={busy || !finding || rationale.length < 10}
                onClick={() => void send(`findings/${finding}/review`, { disposition })}
              >
                Append human finding review
              </Button>
              <p>
                The original deterministic result remains immutable. A human disposition is a
                separate attributed record.
              </p>
            </>
          )}
          {routeId === "O07" && (
            <>
              <label className="field">
                Room
                <select value={room} onChange={(e) => setRoom(e.target.value)}>
                  <option value="">Choose room</option>
                  {rows(data.rooms).map((r) => (
                    <option key={value(r.id)} value={value(r.id)}>
                      {value(r.room_code)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                Certified schedule original
                <select value={selected} onChange={(e) => setSelected(e.target.value)}>
                  <option value="">Choose original</option>
                  {rows(evidence.data?.data.versions).map((v) => (
                    <option key={value(v.id)} value={value(v.id)}>
                      {value(v.name)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                Certified carpet area m²
                <input
                  type="number"
                  min={0}
                  step="0.01"
                  value={area}
                  onChange={(e) => setArea(Number(e.target.value))}
                />
              </label>
              <label className="field">
                Sourced division size
                <select value={division} onChange={(e) => setDivision(Number(e.target.value))}>
                  <option value={60}>60</option>
                  <option value={30}>30</option>
                </select>
              </label>
              <label className="field">
                Schedule reference
                <input value={sourceRef} onChange={(e) => setSourceRef(e.target.value)} />
              </label>
              <label className="field">
                Source PDF/image page
                <input
                  type="number"
                  min={1}
                  value={sourcePage}
                  onChange={(e) => setSourcePage(Number(e.target.value))}
                />
              </label>
              <fieldset>
                <legend>Source region in original page coordinates</legend>
                {["Left", "Top", "Right", "Bottom"].map((label, index) => (
                  <label className="field" key={label}>
                    {label}
                    <input
                      type="number"
                      min={0}
                      value={sourceBox[index]}
                      onChange={(e) =>
                        setSourceBox(
                          sourceBox.map((v, i) => (i === index ? Number(e.target.value) : v)),
                        )
                      }
                    />
                  </label>
                ))}
              </fieldset>
              <label className="check-row">
                <input
                  type="checkbox"
                  checked={reliable}
                  onChange={(e) => setReliable(e.target.checked)}
                />
                I inspected this source and consider the schedule reliable for this measurement.
              </label>
              <Button
                disabled={
                  busy || !room || !selected || sourceRef.length < 5 || rationale.length < 10
                }
                onClick={() =>
                  void send("infrastructure", {
                    room_id: room,
                    version_id: selected,
                    certified_area: area,
                    division,
                    source_ref: sourceRef,
                    reliable,
                    page: sourcePage,
                    bbox: sourceBox,
                  })
                }
              >
                Record inspected schedule values
              </Button>
              <p>
                Recording values requires inspecting the linked source. This action does not claim
                automated plan measurement.
              </p>
            </>
          )}
          {routeId === "O08" && (
            <>
              <label className="field">
                Human review action
                <select value={command} onChange={(e) => setCommand(e.target.value)}>
                  {[
                    "OBSERVATION",
                    "RECOMMENDATION",
                    "CLARIFICATION",
                    "COMPLETE",
                    ...(user.roles.includes("supervisor") ? ["REOPEN"] : []),
                  ].map((a) => (
                    <option key={a}>{a}</option>
                  ))}
                </select>
              </label>
              <label className="check-field">
                <input
                  type="checkbox"
                  checked={published}
                  onChange={(e) => setPublished(e.target.checked)}
                />
                Explicitly publish clarification text to the institution
              </label>
              {command === "CLARIFICATION" && (
                <fieldset>
                  <legend>Published correction scope</legend>
                  <label className="field">
                    Response deadline
                    <input
                      type="datetime-local"
                      value={responseDeadline}
                      onChange={(e) => setResponseDeadline(e.target.value)}
                    />
                  </label>
                  {["proposed_name", "proposed_address", "affiliation", "signatory"].map(
                    (field) => (
                      <label className="check-field" key={field}>
                        <input
                          type="checkbox"
                          checked={responseFields.includes(field)}
                          onChange={(e) =>
                            setResponseFields(
                              e.target.checked
                                ? [...responseFields, field]
                                : responseFields.filter((f) => f !== field),
                            )
                          }
                        />
                        Permit {field.replaceAll("_", " ")}
                      </label>
                    ),
                  )}
                  <label className="field">
                    Permitted replacement document
                    <select value={responseType} onChange={(e) => setResponseType(e.target.value)}>
                      {[
                        "FIRE_SAFETY",
                        "AFFIDAVIT_2",
                        "PAYMENT_RECEIPT",
                        "OCCUPANCY",
                        "COMPLETION",
                        "STRUCTURAL_STABILITY",
                        "SATELLITE_MAP",
                        "AUDITED_ACCOUNTS",
                      ].map((t) => (
                        <option key={t}>{t}</option>
                      ))}
                    </select>
                  </label>
                  <label className="check-field">
                    <input
                      type="checkbox"
                      checked={requireResponseDocument}
                      onChange={(e) => setRequireResponseDocument(e.target.checked)}
                    />
                    Require a fresh processed document of this type
                  </label>
                </fieldset>
              )}
              <Button
                disabled={busy || rationale.length < 10}
                onClick={() =>
                  void send("actions", {
                    action: command,
                    publishable: command === "CLARIFICATION" && published,
                    ...(command === "CLARIFICATION"
                      ? {
                          due_at: Math.floor(new Date(responseDeadline).getTime() / 1000),
                          allowed_fields: responseFields,
                          document_types: [responseType],
                          required_documents: requireResponseDocument ? [responseType] : [],
                        }
                      : {}),
                  })
                }
              >
                Record human action
              </Button>
              <hr />
              <label className="field">
                Route to verified user
                <select value={assignee} onChange={(e) => setAssignee(e.target.value)}>
                  <option value="">Choose assignee</option>
                  {rows(people.data?.data).map((p) => (
                    <option key={value(p.id)} value={value(p.id)}>
                      {value(p.name)} · {value(p.roles)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                Task purpose
                <select value={kind} onChange={(e) => setKind(e.target.value)}>
                  {["ISSUER", "INSPECTION", "SUPERVISION"].map((k) => (
                    <option key={k}>{k}</option>
                  ))}
                </select>
              </label>
              <Button
                disabled={busy || !assignee || rationale.length < 10}
                onClick={() =>
                  void send("tasks", {
                    assignee_id: assignee,
                    kind,
                    due_at: Math.floor(Date.now() / 1000) + 7 * 86400,
                  })
                }
              >
                Route sourced task
              </Button>
              {user.roles.includes("supervisor") && (
                <Button
                  variant="outline"
                  disabled={busy || !assignee || rationale.length < 10}
                  onClick={() => void send("assignment", { assignee_id: assignee })}
                >
                  Reassign scrutiny officer
                </Button>
              )}
              <Button
                variant="outline"
                disabled={busy || rationale.length < 10}
                onClick={() => void send("reports")}
              >
                Request immutable review report
              </Button>
            </>
          )}
        </Card>
      )}
      {routeId === "O09" && <TaskList items={list} />}
      {routeId === "O08" && (
        <Card>
          <h2>Published requests and institution responses</h2>
          {clarificationReview.isPending || clarificationReview.error ? (
            <Loading
              error={clarificationReview.error}
              retry={() => void clarificationReview.refetch()}
            />
          ) : clarificationReview.data?.data.length ? (
            clarificationReview.data.data.map((c) => (
              <article className="observation-row" key={value(c.id)}>
                <h3>{value(c.message)}</h3>
                <p>
                  Deadline {new Date(Number(c.deadline) * 1000).toLocaleString()} ·{" "}
                  {c.closed ? "Reviewed/withdrawn" : "Open for human resolution"}
                </p>
                <p>
                  Allowed fields: {value(c.allowed_fields)} · required documents:{" "}
                  {value(c.required_documents)}
                </p>
                {rows(c.responses).map((r) => (
                  <div key={value(r.id)}>
                    <p>{value(r.explanation)}</p>
                    <Fields data={record(r.receipt)} />
                  </div>
                ))}
                <Fields data={record(record(c.draft).changes)} />
                {!c.closed && (
                  <Button
                    disabled={busy || rationale.length < 10}
                    onClick={() => {
                      setBusy(true);
                      void api<Row>(`/officer/cases/${caseId}`)
                        .then((current) =>
                          mutate(
                            `/officer/clarifications/${value(c.id)}/${rows(c.responses).length ? "resolve" : "withdraw"}`,
                            {
                              expected_version: record(current.data.review).version,
                              rationale,
                            },
                          ),
                        )
                        .then(async () => {
                          setNotice("Clarification resolution saved with attribution.");
                          await qc.invalidateQueries({
                            queryKey: ["scrutiny"],
                          });
                        })
                        .catch((e) => setError((e as Error).message))
                        .finally(() => setBusy(false));
                    }}
                  >
                    {rows(c.responses).length
                      ? "Record human response resolution"
                      : "Withdraw request with rationale"}
                  </Button>
                )}
              </article>
            ))
          ) : (
            <p>No published requests for this case.</p>
          )}
        </Card>
      )}
      {routeId === "O10" && (
        <Card>
          <h2>Persisted report requests</h2>
          {list.length ? (
            list.map((r) => (
              <article key={value(r.id)}>
                <h3>{value(r.state)}</h3>
                <Fields data={r} />
              </article>
            ))
          ) : (
            <p>
              No authorized report requests. Create an immutable review snapshot from an assigned
              case.
            </p>
          )}
        </Card>
      )}
    </>
  );
}
function CaseRows({ items }: { items: Row[] }) {
  return (
    <Card>
      <h2>Scoped cases</h2>
      {items.length ? (
        <div className="review-case-list">
          {items.map((c) => (
            <article key={value(c.id)}>
              <h3>
                <Link to={`/officer/applications/${value(c.id)}/overview`}>
                  {value(c.institution_name)}
                </Link>
              </h3>
              <p>
                {label(value(c.category))} · {value(c.academic_year)} · {label(value(c.status))}
              </p>
              <p>
                Priority {value(record(c.priority).score)} · {value(record(c.priority).meaning)}
              </p>
              {rows(record(c.priority).reasons).length ? (
                <ul>
                  {rows(record(c.priority).reasons).map((reason, i) => (
                    <li key={i}>
                      {value(reason.factor)}: {value(reason.count)}
                    </li>
                  ))}
                </ul>
              ) : (
                <small>No additional priority factors</small>
              )}
              <p>
                {Array.isArray(c.assignment_ids) && c.assignment_ids.length
                  ? `${c.assignment_ids.length} assigned reviewers`
                  : "Awaiting assignment"}
              </p>
            </article>
          ))}
        </div>
      ) : (
        <p>No cases match this authorized scope and filter.</p>
      )}
    </Card>
  );
}
function Findings({ id, items }: { id: string; items: Row[] }) {
  return (
    <Card>
      <h2>Findings and supporting evidence</h2>
      {items.length ? (
        items.map((r, i) => (
          <article key={value(r.id ?? i)} className="observation-row">
            <h3>{value(r.message ?? r.code ?? r.state)}</h3>
            <details>
              <summary>How this finding was produced</summary>
              <Fields data={r} />
            </details>
            {Boolean(r.version_id) && (
              <Link
                to={`/officer/applications/${id}/evidence?${new URLSearchParams({ version: value(r.version_id), page: value(r.page ?? 1), ...(Array.isArray(r.bbox) ? { region: r.bbox.join(",") } : {}) })}`}
              >
                Open exact original version and page
              </Link>
            )}
            {Boolean(r.clause) && (
              <p>
                Rule {value(r.rule_code)} v{value(r.rule_version)} · {value(r.clause)} · printed{" "}
                {value(r.printed_page)} / PDF {value(r.pdf_page)}
                {Boolean(r.source_url) && (
                  <>
                    {" "}
                    ·{" "}
                    <a href={value(r.source_url)} target="_blank" rel="noreferrer">
                      Controlling source
                    </a>
                  </>
                )}
              </p>
            )}
          </article>
        ))
      ) : (
        <p>No saved results yet. Unrun checks are not presented as passed.</p>
      )}
    </Card>
  );
}
function TaskList({ items }: { items: Row[] }) {
  const qc = useQueryClient();
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  async function respond(t: Row, form: HTMLFormElement) {
    setError("");
    const data = new FormData(form);
    try {
      await mutate(`/officer/tasks/${value(t.id)}/response`, {
        expected_version: t.version,
        outcome: data.get("outcome"),
        source_ref: data.get("source"),
        rationale: data.get("rationale"),
        observed_at: Math.floor(Date.now() / 1000),
      });
      setNotice("Sourced response recorded with attribution.");
      await qc.invalidateQueries({ queryKey: ["scrutiny"] });
    } catch (e) {
      setError((e as Error).message);
    }
  }
  return (
    <>
      {error && <p role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}
      {items.length ? (
        items.map((t) => (
          <Card key={value(t.id)}>
            <h2>
              {value(t.kind)} · {value(t.status)}
            </h2>
            <p>
              Due {new Date(Number(t.due_at) * 1000).toLocaleString()} · attempts{" "}
              {value(t.attempts)}/3
            </p>
            <Link to={`/officer/applications/${value(t.application_id)}/evidence`}>
              Inspect routed evidence
            </Link>
            <Fields data={record(t.evidence)} />
            {rows(t.responses).map((r, i) => (
              <Fields key={i} data={r} />
            ))}
            {t.status !== "RESOLVED" && (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  void respond(t, e.currentTarget);
                }}
              >
                <label className="field">
                  Sourced outcome
                  <select name="outcome">
                    {["CONFIRMED", "CONFLICT", "UNRESOLVED", "TIMEOUT", "UNSUPPORTED"].map((o) => (
                      <option key={o}>{o}</option>
                    ))}
                  </select>
                </label>
                <label className="field">
                  Source or proof reference
                  <input name="source" minLength={5} maxLength={500} required />
                </label>
                <label className="field">
                  Response rationale
                  <textarea name="rationale" minLength={10} maxLength={2000} required />
                </label>
                <Button>Record sourced response</Button>
              </form>
            )}
          </Card>
        ))
      ) : (
        <Card>
          <p>No tasks routed to your authorized scope.</p>
        </Card>
      )}
    </>
  );
}
