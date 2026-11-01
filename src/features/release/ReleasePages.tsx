import guidance from "../../../config/document-guidance.json";
import { useEffect, useState, useRef } from "react";
import { Link, useNavigate } from "@/features/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type User, type Preview } from "../api";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { type Row, record, rows, value, Loading, Fields } from "../officer/common";

const send = (path: string, body: unknown = {}, method = "POST") =>
  api<Row>(path, {
    method,
    headers: { "Idempotency-Key": crypto.randomUUID() },
    body: JSON.stringify(body),
  });

export function PreferenceEffect({ user }: { user: User }) {
  const q = useQuery({
    queryKey: ["preferences", user.id],
    queryFn: () => api<Row>("/me/preferences"),
  });
  useEffect(() => {
    document.documentElement.dataset.reducedMotion = String(Boolean(q.data?.data.reduced_motion));
    document.documentElement.dataset.highContrast = String(Boolean(q.data?.data.high_contrast));
  }, [q.data]);
  return null;
}

export function NotificationsPage() {
  const [state, setState] = useState("all"),
    [kind, setKind] = useState(""),
    [app, setApp] = useState(""),
    [page, setPage] = useState(1),
    [error, setError] = useState("");
  const q = useQuery({
    queryKey: ["notifications", state, kind, app, page],
    queryFn: () =>
      api<Row[]>(
        `/notifications?${new URLSearchParams({ state, event_type: kind, application_id: app, page: String(page) })}`,
      ),
    refetchInterval: 10000,
  });
  async function read(id?: string) {
    try {
      await send(id ? `/notifications/${id}/read` : "/notifications/read-all", {}, "PATCH");
      await q.refetch();
    } catch (e) {
      setError((e as Error).message);
    }
  }
  return (
    <>
      <Card>
        <h2>In-app updates</h2>
        <p>
          Delivered updates refresh every ten seconds. Opening a linked record rechecks your current
          access.
        </p>
        <div className="release-filters">
          <label className="field">
            Read state
            <select
              value={state}
              onChange={(e) => {
                setState(e.target.value);
                setPage(1);
              }}
            >
              <option value="all">All</option>
              <option value="unread">Unread</option>
              <option value="read">Read</option>
            </select>
          </label>
          <label className="field">
            Event type
            <input
              value={kind}
              onChange={(e) => {
                setKind(e.target.value);
                setPage(1);
              }}
            />
          </label>
          <label className="field">
            Application ID
            <input
              value={app}
              onChange={(e) => {
                setApp(e.target.value);
                setPage(1);
              }}
            />
          </label>
        </div>
        <Button variant="outline" onClick={() => void read()}>
          Mark all read
        </Button>{" "}
        <Button variant="outline" onClick={() => void q.refetch()}>
          Refresh notifications
        </Button>
        {error && <p role="alert">{error}</p>}
      </Card>
      {q.isPending || q.error ? (
        <Loading error={q.error} retry={() => void q.refetch()} />
      ) : (
        <Card>
          {q.data.data.length ? (
            q.data.data.map((n) => (
              <article className="observation-row" key={value(n.id)}>
                <h3>{value(n.summary)}</h3>
                <p>
                  {value(n.type)} · {new Date(Number(n.at) * 1000).toLocaleString()} ·{" "}
                  {n.read_at ? "Read" : "Unread"}
                </p>
                <p>Delivery: {value(n.delivery)}</p>
                <Link to={value(n.link)}>Open authorized record</Link>
                {!n.read_at && (
                  <Button variant="outline" onClick={() => void read(value(n.id))}>
                    Mark read
                  </Button>
                )}
              </article>
            ))
          ) : (
            <p>No notifications match this authorized scope and filter.</p>
          )}
        </Card>
      )}
      <div className="pagination">
        <Button disabled={page === 1} onClick={() => setPage(page - 1)}>
          Previous notification page
        </Button>
        <span>Page {page}</span>
        <Button
          disabled={!q.data || page * 20 >= (q.data.meta.total ?? 0)}
          onClick={() => setPage(page + 1)}
        >
          Next notification page
        </Button>
      </div>
    </>
  );
}

export function AccountPage({ user }: { user: User }) {
  const qc = useQueryClient(),
    navigate = useNavigate();
  const pref = useQuery({
    queryKey: ["preferences", user.id],
    queryFn: () => api<Row>("/me/preferences"),
  });
  const sessions = useQuery({
    queryKey: ["own-sessions"],
    queryFn: () => api<Row[]>("/me/sessions"),
  });
  const [name, setName] = useState(user.name),
    [notice, setNotice] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  async function save(form: HTMLFormElement) {
    const f = new FormData(form);
    setBusy(true);
    setError("");
    try {
      await send(
        "/me/profile",
        {
          expected_version: pref.data!.data.version,
          name,
          in_app: f.has("in_app"),
          reduced_motion: f.has("reduced_motion"),
          high_contrast: f.has("high_contrast"),
        },
        "PATCH",
      );
      await qc.invalidateQueries({ queryKey: ["preferences"] });
      await qc.invalidateQueries({ queryKey: ["me"] });
      setNotice("Profile and preferences saved.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function revoke(id: string) {
    try {
      const r = await api<Row>(`/me/sessions/${id}`, { method: "DELETE" });
      if (r.data.current) {
        qc.clear();
        navigate("/login");
      } else {
        await sessions.refetch();
        setNotice("Session revoked.");
      }
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function password(form: HTMLFormElement) {
    const f = new FormData(form);
    setBusy(true);
    try {
      await send("/me/password", {
        current_password: f.get("current"),
        password: f.get("password"),
      });
      form.reset();
      await sessions.refetch();
      setNotice("Password changed; other sessions revoked.");
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
      <Card>
        <h2>Authenticated identity</h2>
        <p>{user.email}</p>
        <p>Server-resolved roles: {user.roles.join(", ")}</p>
        <p>
          Institution scope:{" "}
          {user.institution_ids.join(", ") || "Assigned cases or governance only"}
        </p>
      </Card>
      {pref.isPending || pref.error ? (
        <Loading error={pref.error} retry={() => void pref.refetch()} />
      ) : (
        <Card>
          <h2>Profile and preferences</h2>
          <form
            key={Number(pref.data.data.version)}
            onSubmit={(e) => {
              e.preventDefault();
              void save(e.currentTarget);
            }}
          >
            <label className="field">
              Display name
              <input
                value={name}
                minLength={2}
                maxLength={160}
                autoComplete="name"
                onChange={(e) => setName(e.target.value)}
                required
              />
            </label>
            <label className="check-field">
              <input
                name="in_app"
                type="checkbox"
                defaultChecked={Boolean(pref.data.data.in_app)}
              />
              Receive in-app notifications
            </label>
            <label className="check-field">
              <input
                name="reduced_motion"
                type="checkbox"
                defaultChecked={Boolean(pref.data.data.reduced_motion)}
              />
              Reduce motion
            </label>
            <label className="check-field">
              <input
                name="high_contrast"
                type="checkbox"
                defaultChecked={Boolean(pref.data.data.high_contrast)}
              />
              Increase contrast
            </label>
            <Button disabled={busy}>Save profile and preferences</Button>
          </form>
          <p>Email and roles are controlled by the identity and governance services.</p>
        </Card>
      )}
      <Card>
        <h2>Password</h2>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void password(e.currentTarget);
          }}
        >
          <label className="field">
            Current password
            <input name="current" type="password" autoComplete="current-password" required />
          </label>
          <label className="field">
            New password (at least 12 characters)
            <input
              name="password"
              type="password"
              autoComplete="new-password"
              minLength={12}
              maxLength={200}
              required
            />
          </label>
          <Button disabled={busy}>Change password</Button>
        </form>
      </Card>
      <Card>
        <h2>Active sessions</h2>
        {sessions.isPending || sessions.error ? (
          <Loading error={sessions.error} retry={() => void sessions.refetch()} />
        ) : (
          sessions.data.data.map((s) => (
            <article className="observation-row" key={value(s.id)}>
              <p>
                {s.current ? "This session" : "Other session"} · expires{" "}
                {new Date(Number(s.expires_at) * 1000).toLocaleString()}
              </p>
              <Button variant="outline" onClick={() => void revoke(value(s.id))}>
                {s.current ? "Sign out this session" : "Revoke other session"}
              </Button>
            </article>
          ))
        )}
      </Card>
    </>
  );
}

export function RecoveryPage() {
  const [token] = useState(() =>
    typeof window === "undefined"
      ? ""
      : (new URLSearchParams(window.location.hash.slice(1)).get("token") ?? ""),
  );
  const [notice, setNotice] = useState<Row | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    if (token) window.history.replaceState(null, "", window.location.pathname);
  }, [token]);
  async function submit(form: HTMLFormElement) {
    const f = new FormData(form);
    setError("");
    setBusy(true);
    try {
      const r = await send(
        token ? "/auth/recovery/confirm" : "/auth/recovery",
        token ? { token, password: f.get("password") } : { email: f.get("email") },
      );
      setNotice(r.data);
      form.reset();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <main id="main-content" className="release-recovery">
      <Link to="/">URANIUM VERIFY</Link>
      <h1>Password recovery</h1>
      <Card>
        <h2>{token ? "Confirm secure reset" : "Request recovery instructions"}</h2>
        <p>
          No email or SMS provider is configured in this local demo. Eligible recovery requests can
          use an explicitly enabled local operator preview.
        </p>
        {error && <p role="alert">{error}</p>}
        {notice ? (
          <div role="status">
            {notice.reset ? (
              <p>Password reset. All previous sessions were revoked.</p>
            ) : (
              <>
                <p>{value(notice.message)}</p>
                <p>Delivery: {value(notice.delivery)}</p>
                <p>Operator reference: {value(notice.reference)}</p>
              </>
            )}
          </div>
        ) : (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void submit(e.currentTarget);
            }}
          >
            {token ? (
              <label className="field">
                New password (at least 12 characters)
                <input
                  name="password"
                  type="password"
                  autoComplete="new-password"
                  minLength={12}
                  maxLength={200}
                  required
                />
              </label>
            ) : (
              <label className="field">
                Registered email address
                <input name="email" type="email" autoComplete="email" required maxLength={254} />
              </label>
            )}
            <Button disabled={busy}>
              {busy ? "Submitting…" : token ? "Reset password" : "Request reset link"}
            </Button>
          </form>
        )}
        <Link to="/login">Return to sign in</Link>
      </Card>
    </main>
  );
}

export function ClarificationInbox() {
  const [page, setPage] = useState(1);
  const [state, setState] = useState("all");
  const q = useQuery({
    queryKey: ["clarifications", page, state],
    queryFn: () => api<Row[]>(`/clarifications?page=${page}&state=${state}`),
    refetchInterval: 10000,
  });
  if (q.isPending || q.error) return <Loading error={q.error} retry={() => void q.refetch()} />;
  return (
    <>
      <Card>
        <h2>Published clarification requests</h2>
        <label className="field">
          Request state
          <select
            value={state}
            onChange={(e) => {
              setState(e.target.value);
              setPage(1);
            }}
          >
            {["all", "open", "submitted", "closed", "overdue"].map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </label>
        {q.data.data.length ? (
          q.data.data.map((r) => (
            <article className="observation-row" key={value(r.id)}>
              <h3>{value(r.message)}</h3>
              <p>Application {value(r.application_id)}</p>
              <p>
                Deadline {new Date(Number(r.deadline) * 1000).toLocaleString()} ·{" "}
                {r.closed
                  ? "Reviewed and closed"
                  : rows(r.responses).length
                    ? "Response submitted"
                    : r.can_respond
                      ? "Response open"
                      : "Window closed or policy unavailable"}
              </p>
              <Link to={`/institution/deficiencies/${value(r.id)}`}>Open focused response</Link>
            </article>
          ))
        ) : (
          <p>No published requests in your institution.</p>
        )}
      </Card>
      <div className="pagination">
        <Button disabled={page === 1} onClick={() => setPage(page - 1)}>
          Previous requests
        </Button>
        <span>Page {page}</span>
        <Button disabled={page * 20 >= (q.data.meta.total ?? 0)} onClick={() => setPage(page + 1)}>
          Next requests
        </Button>
      </div>
    </>
  );
}

export function ClarificationResponsePage({ id, user }: { id: string; user: User }) {
  const q = useQuery({
    queryKey: ["response", id],
    queryFn: () => api<Row>(`/clarifications/${id}`),
    refetchInterval: 3000,
  });
  const [explanation, setExplanation] = useState(""),
    [changes, setChanges] = useState<Record<string, string>>({}),
    [kind, setKind] = useState(""),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false),
    [progress, setProgress] = useState<number | null>(null),
    [preview, setPreview] = useState<Preview | null>(null),
    [declaration, setDeclaration] = useState(false);
  const draft = record(q.data?.data.draft);
  const loaded = useRef("");
  useEffect(() => {
    const key = `${id}:${draft.version}`;
    if (loaded.current === key) return;
    loaded.current = key;
    setExplanation(typeof draft.explanation === "string" ? draft.explanation : "");
    setChanges((draft.changes as Record<string, string>) ?? {});
  }, [id, draft.version, draft.explanation, draft.changes]);
  async function act(action: () => Promise<unknown>, message: string) {
    setBusy(true);
    setError("");
    try {
      await action();
      setNotice(message);
      await q.refetch();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function save() {
    return send(
      `/clarifications/${id}/draft`,
      { expected_version: draft.version, explanation, changes },
      "PATCH",
    );
  }
  async function upload(file: File) {
    if (!kind) throw new Error("Choose a permitted document type.");
    const limit = file.name.toLowerCase().endsWith(".pdf") ? 20 : 10;
    if (
      !["application/pdf", "image/png", "image/jpeg"].includes(file.type) ||
      file.size > limit * 1024 * 1024
    )
      throw new Error("Choose a PDF, PNG or JPEG within the stated file size limit.");
    const saved = await save();
    const v = record(saved.data.draft).version;
    await new Promise<void>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open(
        "POST",
        `/api/v1/clarifications/${id}/documents/upload?${new URLSearchParams({ expected_version: String(v), document_type: kind, filename: file.name })}`,
      );
      xhr.setRequestHeader("Content-Type", file.type);
      xhr.setRequestHeader("Idempotency-Key", crypto.randomUUID());
      xhr.setRequestHeader(
        "X-CSRF-Token",
        document.cookie
          .split("; ")
          .find((x) => x.startsWith("uv_csrf="))
          ?.slice(8) ?? "",
      );
      xhr.timeout = 120000;
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) setProgress(Math.round((e.loaded / e.total) * 100));
      };
      xhr.onerror = () =>
        reject(new Error("Upload failed. Your saved response remains available."));
      xhr.ontimeout = () => reject(new Error("Upload timed out. Retry with a stable connection."));
      xhr.onload = () => {
        setProgress(null);
        if (xhr.status >= 200 && xhr.status < 300) resolve();
        else {
          let message = "Upload failed.";
          try {
            message = JSON.parse(xhr.responseText).error?.message ?? message;
          } catch {
            /* transport response was not JSON */
          }
          reject(new Error(message));
        }
      };
      xhr.send(file);
    });
  }
  if (q.isPending || q.error) return <Loading error={q.error} retry={() => void q.refetch()} />;
  const data = q.data.data;
  return (
    <>
      {error && <p role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}
      <Card>
        <h2>Clarification requested by the officer</h2>
        <p>{value(data.message)}</p>
        <p>Deadline: {new Date(Number(data.deadline) * 1000).toLocaleString()}</p>
        <p>Original revision: {value(data.original_revision_id)}</p>
        <p>
          Permitted fields: {value(data.allowed_fields)}. Permitted document types:{" "}
          {value(data.document_types)}. Required response documents:{" "}
          {value(data.required_documents)}.
        </p>
        <Link to={`/institution/applications/${value(data.application_id)}/status`}>
          Application timeline
        </Link>
      </Card>
      {data.can_respond && !data.draft && (
        <Card>
          <Button
            disabled={busy}
            onClick={() =>
              void act(() => send(`/clarifications/${id}/draft`), "Response draft started.")
            }
          >
            Prepare response
          </Button>
        </Card>
      )}
      {data.can_respond && Boolean(data.draft) && (
        <Card>
          <h2>Permitted correction and explanation</h2>
          {(data.allowed_fields as string[]).map((f) => (
            <label className="field" key={f}>
              {f.replaceAll("_", " ")}
              <small>Previously submitted: {value(record(data.original)[f])}</small>
              <input
                value={changes[f] ?? value(record(data.original)[f])}
                maxLength={f === "proposed_address" ? 500 : 160}
                onChange={(e) => setChanges({ ...changes, [f]: e.target.value })}
              />
            </label>
          ))}
          <label className="field">
            Response explanation
            <textarea
              value={explanation}
              maxLength={2000}
              onChange={(e) => setExplanation(e.target.value)}
              required
            />
          </label>
          <Button
            disabled={busy}
            onClick={() => void act(() => save(), "Response saved on the server.")}
          >
            Save response draft
          </Button>
          <p>
            Saved version {value(draft.version)}. Reload resumes the saved explanation and changes.
          </p>
          <h3>Old and proposed values</h3>
          {Object.entries(changes).map(([f, v]) => (
            <p key={f}>
              {f}: {value(record(data.original)[f])} → {v}
            </p>
          ))}
          <label className="field">
            Permitted response document type
            <select value={kind} onChange={(e) => setKind(e.target.value)}>
              <option value="">Choose type</option>
              {(data.document_types as string[]).map((t) => (
                <option key={t} value={t}>
                  {(guidance as Record<string, string[]>)[t]?.[0] ?? t.replaceAll("_", " ")}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            Upload response original
            <input
              type="file"
              accept="application/pdf,image/png,image/jpeg"
              disabled={busy || !kind}
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file)
                  void act(
                    () => upload(file),
                    "Document uploaded. Safety and readability checks are in progress.",
                  );
                e.target.value = "";
              }}
            />
          </label>
          <p>
            Upload limits: PDF 20 MB, image 10 MB, 50 pages. Use readable scans at preferably
            200–300 DPI. A response permits ten versions. Original bytes remain quarantined until
            actual validation finishes.
          </p>
          {progress !== null && (
            <p role="status">Transferred {progress}% · processing is separate</p>
          )}
          <label className="check-field">
            <input
              type="checkbox"
              checked={declaration}
              onChange={(e) => setDeclaration(e.target.checked)}
            />
            I confirm these permitted corrections and the response explanation.
          </label>
          <Button
            disabled={
              busy ||
              !declaration ||
              explanation.trim().length < 10 ||
              !user.roles.includes("institution_admin")
            }
            onClick={() =>
              void act(async () => {
                const saved = await save();
                await send(`/clarifications/${id}/responses`, {
                  expected_version: record(saved.data.draft).version,
                  declaration: true,
                });
              }, "Response submitted. The original submission is preserved.")
            }
          >
            Submit response
          </Button>
          <p>Only an institution administrator may finalize this response.</p>
        </Card>
      )}
      <Card>
        <h2>Documents in your original application</h2>
        {rows(data.original_evidence).length ? (
          rows(data.original_evidence).map((v) => (
            <article className="observation-row" key={value(v.id)}>
              <h3>
                {value(v.type)} · {value(v.name)} · v{value(v.number)}
              </h3>
              <p>Original SHA-256 {value(v.sha256)}</p>
              {Boolean(v.previewable) && (
                <Button
                  variant="outline"
                  onClick={() =>
                    void act(async () => {
                      const result = await api<Preview>(
                        `/documents/${value(v.document_id)}/versions/${value(v.number)}/preview`,
                        { method: "POST" },
                      );
                      setPreview(result.data);
                    }, "Authorized prior original preview opened.")
                  }
                >
                  Preview prior submitted original
                </Button>
              )}
            </article>
          ))
        ) : (
          <p>No previous supporting document is available for this request.</p>
        )}
        <h2>Response attachments</h2>
        {rows(data.documents).length ? (
          rows(data.documents).map((v) => (
            <article className="observation-row" key={value(v.id)}>
              <h3>
                {value(v.name)} · v{value(v.number)}
              </h3>
              <p>SHA-256 {value(v.sha256)}</p>
              <p>
                {value(record(v.processing).state)} · {value(record(v.processing).message)}
              </p>
              {Boolean(v.previewable) && (
                <Button
                  variant="outline"
                  onClick={() =>
                    void act(async () => {
                      const r = await api<Preview>(
                        `/documents/${value(v.document_id)}/versions/${value(v.number)}/preview`,
                        { method: "POST" },
                      );
                      setPreview(r.data);
                    }, "Authorized preview opened.")
                  }
                >
                  Preview saved original
                </Button>
              )}
              {Boolean(data.can_respond) &&
                ["PROCESSING_FAILED", "SAFETY_UNAVAILABLE", "NEEDS_REUPLOAD"].includes(
                  value(record(v.processing).state),
                ) && (
                  <Button
                    disabled={busy}
                    onClick={() =>
                      void act(
                        () =>
                          send(`/clarifications/${id}/documents/${value(v.id)}/retry`, {
                            expected_version: draft.version,
                          }),
                        "Bounded processing retry queued.",
                      )
                    }
                  >
                    Retry response processing
                  </Button>
                )}
            </article>
          ))
        ) : (
          <p>No supporting documents were attached to this response.</p>
        )}
      </Card>
      {preview && (
        <Card>
          <iframe title="Authorized response original" src={preview.url} />
          <Button onClick={() => setPreview(null)}>Close response preview</Button>
        </Card>
      )}
      <Card>
        <h2>Submitted responses and acknowledgments</h2>
        {rows(data.responses).length ? (
          rows(data.responses).map((r) => (
            <article key={value(r.id)}>
              <p>{value(r.explanation)}</p>
              <Fields data={record(r.receipt)} />
            </article>
          ))
        ) : (
          <p>No response has been submitted.</p>
        )}
        <p>
          {data.closed
            ? "Officer reviewed and closed this clarification."
            : data.can_respond
              ? "Response window is open."
              : "This response is read-only. Contact the assigned officer if the deadline has passed."}
        </p>
      </Card>
    </>
  );
}

export function ReportLibrary({ user }: { user: User }) {
  const [error, setError] = useState("");
  const [publicMessage, setPublicMessage] = useState("");
  const q = useQuery({
    queryKey: ["reports"],
    queryFn: () => api<Row[]>("/reports"),
    refetchInterval: 3000,
  });
  if (q.isPending || q.error) return <Loading error={q.error} retry={() => void q.refetch()} />;
  return (
    <Card>
      <h2>Application review reports</h2>
      <p>
        Download the recorded review summary for an assigned application. If the review has changed,
        the earlier report is identified and remains available in the history.
      </p>
      {error && <p role="alert">{error}</p>}
      {user.roles.some((role) => ["officer", "supervisor"].includes(role)) && (
        <label className="field">
          Institution-visible report message
          <textarea
            maxLength={2000}
            value={publicMessage}
            onChange={(e) => setPublicMessage(e.target.value)}
          />
          <small>
            Write the message the institution should receive. Only the permitted summary is shared;
            internal review notes remain private.
          </small>
        </label>
      )}
      {q.data.data.length ? (
        q.data.data.map((r) => (
          <article className="observation-row" key={value(r.id)}>
            <h3>
              Application {value(r.application_id)} ·{" "}
              {r.state === "STALE" ? "Earlier report" : value(r.state).replaceAll("_", " ")}
            </h3>
            <p>Captured {new Date(Number(r.created_at) * 1000).toLocaleDateString("en-IN")}</p>
            <p>{value(record(r.payload).rationale)}</p>
            <details>
              <summary>Report reference and integrity</summary>
              <p>Revision {value(r.revision_id)}</p>
              <p>
                Generation attempt {value(r.attempt)}/3 · {value(r.code)}
              </p>
              {Boolean(r.sha256) && <p className="hash">SHA-256 {value(r.sha256)}</p>}
            </details>
            {Boolean(r.download_url) && (
              <a href={value(r.download_url)}>Download review report PDF</a>
            )}
            {r.state === "READY" &&
              !r.publication_id &&
              user.roles.some((role) => ["officer", "supervisor"].includes(role)) && (
                <Button
                  disabled={publicMessage.trim().length < 10}
                  onClick={() =>
                    void send(`/reports/${value(r.id)}/publish-summary`, {
                      public_message: publicMessage,
                    })
                      .then(() => q.refetch())
                      .catch((e) => setError((e as Error).message))
                  }
                >
                  Share summary with institution
                </Button>
              )}
            {Boolean(r.publication_id) && (
              <p>Separate institution summary published with audit attribution.</p>
            )}
            {r.state === "FAILED" && Number(r.attempt) < 3 && (
              <Button
                onClick={() =>
                  void send(`/reports/${value(r.id)}/retry`)
                    .then(() => q.refetch())
                    .catch((e) => setError((e as Error).message))
                }
              >
                Retry report generation
              </Button>
            )}
          </article>
        ))
      ) : (
        <p>
          No reports have been generated yet. Open an assigned case, choose Review and generate a
          review report.
        </p>
      )}
    </Card>
  );
}

export function PublishedReports({ id }: { id: string }) {
  const q = useQuery({
    queryKey: ["published-reports", id],
    queryFn: () => api<Row[]>(`/applications/${id}/published-reports`),
    refetchInterval: 5000,
  });
  return (
    <Card>
      <h2>Permitted published reports</h2>
      {q.isPending || q.error ? (
        <Loading error={q.error} retry={() => void q.refetch()} />
      ) : q.data.data.length ? (
        q.data.data.map((r) => (
          <article key={value(r.id)}>
            <p>{value(r.message)}</p>
            <p>
              Revision {value(r.revision_id)} · SHA-256 {value(r.sha256)}
            </p>
            <a href={value(r.download_url)}>Download institution-published summary PDF</a>
          </article>
        ))
      ) : (
        <p>
          No report summary has been explicitly published to your institution. Private officer
          reports are restricted.
        </p>
      )}
    </Card>
  );
}
