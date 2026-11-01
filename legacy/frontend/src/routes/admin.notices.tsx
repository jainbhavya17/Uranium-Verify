import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { Plus, Pin, Pencil, Trash2, ArrowUpRight } from "lucide-react";
import { InnerPage } from "@/components/portal";
import { Link } from "@/components/link";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { actions, useStore, useCurrentUser } from "@/lib/store";
import type { Announcement, PortalNotice } from "@/lib/data";
import { noticeDate } from "@/lib/notice-format";
import { seo } from "@/lib/seo";
export const Route = createFileRoute("/admin/notices")({
  head: seo("Manage notices", "Edit prototype portal notices and announcement."),
  component: Page,
});
function Page() {
  return (
    <InnerPage role="admin" title="Portal notices" crumbs={[{ label: "Portal notices" }]}>
      <NoticeManager />
    </InnerPage>
  );
}
function NoticeManager() {
  const notices = useStore((s) => s.portalNotices);
  const savedAnnouncement = useStore((s) => s.announcement);
  const user = useCurrentUser();
  const [editing, setEditing] = useState<PortalNotice | null>(null);
  const [deleting, setDeleting] = useState<PortalNotice | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [announcement, setAnnouncement] = useState<Announcement>(savedAnnouncement);
  if (user?.role !== "admin") return null;
  const perform = (fn: () => void, text: string) => {
    try {
      fn();
      setMessage(text);
      setError("");
    } catch (e) {
      setError((e as Error).message);
    }
  };
  const create = () =>
    setEditing({
      id: `PN-${crypto.randomUUID()}`,
      title: "",
      summary: "",
      body: "",
      category: "Guidance",
      publishedOn: new Date().toLocaleDateString("en-CA"),
      published: false,
      pinned: false,
      link: "",
    });
  return (
    <div className="uv-admin">
      <div className="uv-admin-bar">
        <p>Changes are saved in this browser. Published notices appear on the public page.</p>
        <Link to="/notices" className="uv-button">
          Preview notices <ArrowUpRight size={16} />
        </Link>
        <button onClick={create} className="uv-button uv-coral">
          <Plus size={16} /> Create notice
        </button>
      </div>
      <p role="status" className="uv-feedback">
        {message}
      </p>
      {error && (
        <p role="alert" className="text-destructive">
          {error}
        </p>
      )}
      <div className="uv-admin-list">
        {notices.length ? (
          [...notices]
            .sort(
              (a, b) =>
                Number(b.pinned) - Number(a.pinned) || b.publishedOn.localeCompare(a.publishedOn),
            )
            .map((n) => (
              <article key={n.id}>
                <div>
                  <span className={`uv-tag uv-tag-${n.category.toLowerCase()}`}>{n.category}</span>
                  <span className="uv-admin-state">
                    {n.published
                      ? new Date(`${n.publishedOn}T00:00:00`) > new Date()
                        ? "Scheduled"
                        : "Published"
                      : "Draft"}{" "}
                    · {noticeDate(n.publishedOn)}
                  </span>
                  <h2>{n.title}</h2>
                  <p>{n.summary}</p>
                </div>
                <div className="uv-admin-actions">
                  <button className="uv-button" onClick={() => setEditing(n)}>
                    <Pencil size={14} /> Edit
                  </button>
                  <button
                    className="uv-button"
                    aria-pressed={n.pinned}
                    aria-label={`${n.pinned ? "Unpin" : "Pin"} ${n.title}`}
                    onClick={() =>
                      perform(
                        () => actions.saveNotice({ ...n, pinned: !n.pinned }),
                        n.pinned ? "Notice unpinned." : "Notice pinned.",
                      )
                    }
                  >
                    <Pin size={14} />
                    {n.pinned ? "Unpin" : "Pin"}
                  </button>
                  <button
                    className="uv-button"
                    onClick={() =>
                      perform(
                        () => actions.saveNotice({ ...n, published: !n.published }),
                        n.published ? "Notice unpublished." : "Notice published.",
                      )
                    }
                  >
                    {n.published ? "Unpublish" : "Publish"}
                  </button>
                  <button
                    className="uv-button uv-delete"
                    aria-label={`Delete ${n.title}`}
                    onClick={() => setDeleting(n)}
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </article>
            ))
        ) : (
          <p className="uv-empty">No notices yet. Create your first notice.</p>
        )}
      </div>
      <section className="uv-announcement-editor">
        <h2>Homepage announcement</h2>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            perform(() => actions.saveAnnouncement(announcement), "Announcement saved.");
          }}
        >
          <label>
            Announcement text
            <input
              className="field"
              required
              maxLength={120}
              value={announcement.text}
              onChange={(e) => setAnnouncement({ ...announcement, text: e.target.value })}
            />
          </label>
          <label>
            Link
            <input
              className="field"
              required
              value={announcement.link}
              onChange={(e) => setAnnouncement({ ...announcement, link: e.target.value })}
            />
          </label>
          <label className="uv-checkbox">
            <input
              type="checkbox"
              checked={announcement.enabled}
              onChange={(e) => setAnnouncement({ ...announcement, enabled: e.target.checked })}
            />
            Show announcement
          </label>
          <button className="uv-button uv-navy">Save announcement</button>
        </form>
      </section>
      <Dialog
        open={!!editing}
        onOpenChange={(open) => {
          if (!open) {
            setEditing(null);
            setError("");
          }
        }}
      >
        <DialogContent className="uv-dialog uv-editor">
          <DialogTitle>
            {notices.some((n) => n.id === editing?.id) ? "Edit notice" : "Create notice"}
          </DialogTitle>
          <DialogDescription>
            Drafts remain private to the administrator. Future publication dates schedule a notice.
          </DialogDescription>
          {editing && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                try {
                  actions.saveNotice(editing);
                  setEditing(null);
                  setMessage("Notice saved.");
                  setError("");
                } catch (err) {
                  setError((err as Error).message);
                }
              }}
            >
              <label>
                Title
                <input
                  className="field"
                  required
                  maxLength={180}
                  value={editing.title}
                  onChange={(e) => setEditing({ ...editing, title: e.target.value })}
                />
              </label>
              <label>
                Summary
                <textarea
                  className="field"
                  required
                  maxLength={360}
                  rows={2}
                  value={editing.summary}
                  onChange={(e) => setEditing({ ...editing, summary: e.target.value })}
                />
              </label>
              <label>
                Full notice
                <textarea
                  className="field"
                  required
                  rows={5}
                  value={editing.body}
                  onChange={(e) => setEditing({ ...editing, body: e.target.value })}
                />
              </label>
              <div className="uv-form-row">
                <label>
                  Category
                  <select
                    className="field"
                    value={editing.category}
                    onChange={(e) =>
                      setEditing({
                        ...editing,
                        category: e.target.value as PortalNotice["category"],
                      })
                    }
                  >
                    {["Guidance", "Updates", "Maintenance"].map((c) => (
                      <option key={c}>{c}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Publication date
                  <input
                    className="field"
                    type="date"
                    required
                    value={editing.publishedOn}
                    onChange={(e) => setEditing({ ...editing, publishedOn: e.target.value })}
                  />
                </label>
              </div>
              <label>
                Optional link
                <input
                  className="field"
                  placeholder="/resources or https://…"
                  value={editing.link ?? ""}
                  onChange={(e) => setEditing({ ...editing, link: e.target.value })}
                />
              </label>
              <div className="uv-form-row">
                <label className="uv-checkbox">
                  <input
                    type="checkbox"
                    checked={editing.pinned}
                    onChange={(e) => setEditing({ ...editing, pinned: e.target.checked })}
                  />
                  Pin to top
                </label>
                <label className="uv-checkbox">
                  <input
                    type="checkbox"
                    checked={editing.published}
                    onChange={(e) => setEditing({ ...editing, published: e.target.checked })}
                  />
                  Publish notice
                </label>
              </div>
              {error && (
                <p role="alert" className="text-destructive">
                  {error}
                </p>
              )}
              <button className="uv-button uv-coral" type="submit">
                Save notice
              </button>
            </form>
          )}
        </DialogContent>
      </Dialog>
      <Dialog
        open={!!deleting}
        onOpenChange={(open) => {
          if (!open) setDeleting(null);
        }}
      >
        <DialogContent className="uv-dialog">
          <DialogTitle>Delete this notice?</DialogTitle>
          <DialogDescription>
            “{deleting?.title}” will be removed from this browser’s prototype data.
          </DialogDescription>
          <div className="uv-form-row">
            <button className="uv-button" onClick={() => setDeleting(null)}>
              Keep notice
            </button>
            <button
              className="uv-button uv-coral"
              onClick={() => {
                if (deleting) perform(() => actions.deleteNotice(deleting.id), "Notice deleted.");
                setDeleting(null);
              }}
            >
              Delete notice
            </button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
