import { useState } from "react";
import { ArrowRight, Pin, Search } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogTitle, DialogTrigger } from "./ui/dialog";
import { Link } from "./link";
import { useCurrentUser } from "@/lib/backend-session";
import { usePortalContent, isSafeNoticeLink } from "@/lib/portal-content";
import type { PortalNotice } from "@/lib/data";

import { noticeDate } from "@/lib/notice-format";
export function NoticeLink({ link }: { link?: string }) {
  if (!link || !isSafeNoticeLink(link)) return null;
  return link.startsWith("/") ? (
    <Link to={link} className="uv-button uv-coral">
      Continue to resource <ArrowRight size={16} />
    </Link>
  ) : (
    <a href={link} target="_blank" rel="noreferrer" className="uv-button uv-coral">
      Open linked resource ↗
    </a>
  );
}
export function NoticeCard({ notice }: { notice: PortalNotice }) {
  return (
    <Dialog>
      <DialogTrigger asChild>
        <button className="uv-notice" aria-label={`Read notice: ${notice.title}`}>
          <span className="uv-notice-meta">
            <time dateTime={notice.publishedOn}>{noticeDate(notice.publishedOn)}</time>
            <span className={`uv-tag uv-tag-${notice.category.toLowerCase()}`}>
              {notice.category}
            </span>
            {notice.pinned && (
              <span className="uv-pinned">
                <Pin size={12} /> Pinned
              </span>
            )}
          </span>
          <span className="uv-notice-copy">
            <strong>{notice.title}</strong>
            <span>{notice.summary}</span>
          </span>
          <span className="uv-notice-arrow" aria-hidden="true">
            <ArrowRight size={22} />
          </span>
        </button>
      </DialogTrigger>
      <DialogContent className="uv-dialog">
        <span className={`uv-tag uv-tag-${notice.category.toLowerCase()}`}>{notice.category}</span>
        <DialogTitle>{notice.title}</DialogTitle>
        <DialogDescription>
          Published {noticeDate(notice.publishedOn)} · Prototype portal notice
        </DialogDescription>
        <div className="uv-notice-body">
          {notice.body.split(/\n\s*\n/).map((p, i) => (
            <p key={i}>{p}</p>
          ))}
        </div>
        <NoticeLink link={notice.link} />
      </DialogContent>
    </Dialog>
  );
}
export function NoticesSection({ full = false }: { full?: boolean }) {
  const content = usePortalContent();
  const notices = (content.data?.data.notices ?? []).map((n) => ({ ...n, published: true }));
  const user = useCurrentUser();
  const [filter, setFilter] = useState("All");
  const [query, setQuery] = useState("");
  const list = notices.filter(
    (n) =>
      (filter === "All" || n.category === filter) &&
      `${n.title} ${n.summary} ${n.body}`.toLowerCase().includes(query.toLowerCase()),
  );
  const shown = full ? list : list.slice(0, 3);
  const Heading = full ? "h1" : "h2";
  return (
    <section id="notices" className="uv-section uv-notices" aria-labelledby="notices-title">
      <div className="uv-section-top">
        <div>
          <span className="uv-eyebrow">KEEP IN THE KNOW</span>
          <Heading id="notices-title">The latest from the portal.</Heading>
        </div>
        <p>
          Guidance, updates, and useful information.
          <br />
          All in one place, whenever you need it.
        </p>
      </div>
      <div className="uv-notice-toolbar">
        <div className="uv-filters" role="group" aria-label="Filter notices">
          {["All", "Guidance", "Updates", "Maintenance"].map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              aria-pressed={filter === f}
              className={filter === f ? "selected" : ""}
            >
              {f}
            </button>
          ))}
        </div>
        {full && (
          <label className="uv-search">
            <Search size={17} />
            <span className="sr-only">Search notices</span>
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search notices"
            />
          </label>
        )}
      </div>
      {content.isPending && <p role="status">Loading portal notices…</p>}
      {content.error && (
        <p role="alert">
          Notices could not be loaded.{" "}
          <button onClick={() => void content.refetch()}>Try again</button>
        </p>
      )}
      <div className="uv-notice-list">
        {shown.length ? (
          shown.map((n) => <NoticeCard key={n.id} notice={n} />)
        ) : (
          <p className="uv-empty">
            No published notices match this selection. Try another category or search.
          </p>
        )}
      </div>
      <div className="uv-notice-bottom">
        <span role="status">
          {full
            ? `${list.length} published notice${list.length === 1 ? "" : "s"}`
            : `Showing ${shown.length} of ${list.length} notices`}
        </span>
        <div>
          {user?.role === "admin" && (
            <Link to="/admin/notices">
              Manage notices <ArrowRight size={15} />
            </Link>
          )}
          {!full && (
            <Link to="/notices">
              View all notices <ArrowRight size={17} />
            </Link>
          )}
        </div>
      </div>
    </section>
  );
}
