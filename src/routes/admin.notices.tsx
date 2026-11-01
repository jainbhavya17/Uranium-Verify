import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { InnerPage, AccessDenied } from "@/components/portal";
import { api } from "@/features/api";
import { useCurrentUser } from "@/lib/backend-session";
import {
  isSafeNoticeLink,
  usePortalContent,
  type PortalContent,
  type ServerNotice,
} from "@/lib/portal-content";
export const Route = createFileRoute("/admin/notices")({ component: Page });
const schema = z.object({
  title: z.string().min(3).max(180),
  summary: z.string().min(3).max(400),
  body: z.string().min(3).max(12000),
  category: z.enum(["Guidance", "Updates", "Maintenance"]),
  status: z.enum(["Draft", "Published", "Archived"]),
  publishedOn: z.string().min(10),
  pinned: z.boolean(),
  link: z
    .string()
    .max(2048)
    .refine((v) => !v || isSafeNoticeLink(v), "Use a portal path or HTTPS URL"),
});
type Fields = z.infer<typeof schema>;
function Page() {
  const user = useCurrentUser();
  return (
    <InnerPage role="admin" title="Portal notices" crumbs={[{ label: "Portal notices" }]}>
      {user?.roles.includes("admin") ? <Manager /> : user ? <AccessDenied /> : null}
    </InnerPage>
  );
}
function Manager() {
  const q = usePortalContent(true),
    qc = useQueryClient();
  const [editing, setEditing] = useState<ServerNotice | null>(null),
    [error, setError] = useState(""),
    [message, setMessage] = useState(""),
    [busy, setBusy] = useState(false);
  async function save(data: PortalContent) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const result = await api<PortalContent>("/admin/portal/content", {
        method: "PUT",
        body: JSON.stringify(data),
      });
      qc.setQueryData(["portal-content", true], result);
      await qc.invalidateQueries({ queryKey: ["portal-content"] });
      setMessage("Changes saved and recorded in the audit trail.");
      setEditing(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  if (q.isPending) return <p role="status">Loading notices…</p>;
  if (q.error)
    return (
      <div role="alert">
        <p>{q.error.message}</p>
        <button className="btn btn-navy" onClick={() => void q.refetch()}>
          Retry
        </button>
      </div>
    );
  const data = q.data.data;
  return (
    <div className="workflow-content">
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
      <section className="card">
        <div className="card-heading">
          <h2>Notice library</h2>
          <button
            className="btn btn-navy"
            onClick={() =>
              setEditing({
                id: crypto.randomUUID(),
                title: "",
                summary: "",
                body: "",
                category: "Updates",
                status: "Draft",
                publishedOn: new Date().toISOString().slice(0, 10),
                pinned: false,
                link: "",
              })
            }
          >
            New notice
          </button>
        </div>
        {data.notices.map((n) => (
          <article className="observation-row" key={n.id}>
            <div>
              <b>{n.title}</b>
              <p>
                {n.status} · {n.category} · {n.publishedOn}
                {n.pinned ? " · Pinned" : ""}
              </p>
            </div>
            <button className="btn btn-outline" onClick={() => setEditing(n)}>
              Edit notice
            </button>
          </article>
        ))}
        {!data.notices.length && <p>No notices yet. Create a draft to begin.</p>}
      </section>
      {editing && (
        <Editor
          key={editing.id}
          notice={editing}
          busy={busy}
          cancel={() => setEditing(null)}
          save={(fields) =>
            void save({
              ...data,
              notices: [
                ...data.notices.filter((n) => n.id !== editing.id),
                { ...fields, id: editing.id },
              ],
            })
          }
        />
      )}
      <section className="card">
        <h2>Homepage announcement</h2>
        <form
          key={data.version}
          className="form-grid"
          onSubmit={(e) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            const link = String(f.get("link"));
            if (!isSafeNoticeLink(link)) {
              setError("Use a portal path or HTTPS URL.");
              return;
            }
            void save({
              ...data,
              announcement: { enabled: f.has("enabled"), text: String(f.get("text")), link },
            });
          }}
        >
          <label className="check-field">
            <input name="enabled" type="checkbox" defaultChecked={data.announcement.enabled} />
            Show announcement
          </label>
          <label className="field">
            Announcement text
            <input name="text" maxLength={240} required defaultValue={data.announcement.text} />
          </label>
          <label className="field">
            Destination
            <input name="link" required defaultValue={data.announcement.link} />
          </label>
          <button disabled={busy} className="btn btn-navy">
            Save announcement
          </button>
        </form>
      </section>
    </div>
  );
}
function Editor({
  notice,
  busy,
  save,
  cancel,
}: {
  notice: ServerNotice;
  busy: boolean;
  save: (data: Fields) => void;
  cancel: () => void;
}) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<Fields>({ resolver: zodResolver(schema), defaultValues: notice });
  return (
    <section className="card">
      <h2>Edit notice</h2>
      <form className="form-grid" onSubmit={handleSubmit(save)}>
        {(["title", "summary", "body", "publishedOn", "link"] as const).map((key) => (
          <label key={key} className={`field ${key === "body" ? "full-field" : ""}`}>
            {
              {
                title: "Title",
                summary: "Summary",
                body: "Notice text",
                publishedOn: "Publication date",
                link: "Resource link (optional)",
              }[key]
            }
            {key === "body" ? (
              <textarea
                rows={6}
                aria-invalid={!!errors[key]}
                aria-describedby={errors[key] ? `notice-${key}-error` : undefined}
                {...register(key)}
              />
            ) : (
              <input
                type={key === "publishedOn" ? "date" : "text"}
                aria-invalid={!!errors[key]}
                aria-describedby={errors[key] ? `notice-${key}-error` : undefined}
                {...register(key)}
              />
            )}{" "}
            {errors[key] && (
              <span role="alert" className="error">
                {errors[key]?.message}
              </span>
            )}
          </label>
        ))}
        <label className="field">
          Category
          <select {...register("category")}>
            {["Guidance", "Updates", "Maintenance"].map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </label>
        <label className="field">
          Publication status
          <select {...register("status")}>
            {["Draft", "Published", "Archived"].map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </label>
        <label className="check-field">
          <input type="checkbox" {...register("pinned")} />
          Pin this notice
        </label>
        <div className="form-actions full-field">
          <button className="btn btn-navy" disabled={busy}>
            {busy ? "Saving…" : "Save notice"}
          </button>
          <button className="btn btn-outline" type="button" onClick={cancel}>
            Cancel
          </button>
        </div>
      </form>
    </section>
  );
}
