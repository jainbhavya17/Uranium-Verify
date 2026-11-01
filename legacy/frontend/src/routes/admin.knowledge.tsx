import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { InnerPage, Filters } from "@/components/portal";
import { articles } from "@/lib/data";
import { seo } from "@/lib/seo";

export const Route = createFileRoute("/admin/knowledge")({
  head: seo(
    "Knowledge Base",
    "Acts, regulations, procedures and officer manuals for the approval process.",
  ),
  component: Page,
});

function Page() {
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("");
  const list = articles.filter(
    (a) =>
      (!cat || a.category === cat) &&
      `${a.title} ${a.body}`.toLowerCase().includes(q.toLowerCase()),
  );
  return (
    <InnerPage crumbs={[{ label: "Knowledge Base" }]} title="Knowledge Base">
      <Filters>
        <div className="flex-1 min-w-[12rem]">
          <label className="label" htmlFor="q">
            Search
          </label>
          <input id="q" className="field" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <div>
          <label className="label" htmlFor="c">
            Category
          </label>
          <select id="c" className="field" value={cat} onChange={(e) => setCat(e.target.value)}>
            <option value="">All</option>
            {[...new Set(articles.map((a) => a.category))].map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </div>
      </Filters>
      {list.length === 0 ? (
        <div className="panel p-6 text-center text-sm text-muted-foreground">No records found</div>
      ) : (
        <div className="space-y-2">
          {list.map((a) => (
            <details key={a.id} className="panel">
              <summary className="cursor-pointer px-4 py-3 font-semibold text-navy flex justify-between gap-3">
                <span>{a.title}</span>
                <span className="text-xs font-normal text-muted-foreground">
                  {a.category} · Updated {a.updated}
                </span>
              </summary>
              <p className="px-4 pb-4 text-sm leading-relaxed">{a.body}</p>
            </details>
          ))}
        </div>
      )}
    </InnerPage>
  );
}
