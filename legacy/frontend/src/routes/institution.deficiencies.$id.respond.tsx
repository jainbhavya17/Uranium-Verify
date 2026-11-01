import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { InnerPage, Panel, Status } from "@/components/portal";
import { Link } from "@/components/link";
import { actions, useCurrentUser, useStore } from "@/lib/store";
import type { Deficiency } from "@/lib/data";
import { seo } from "@/lib/seo";

export const Route = createFileRoute("/institution/deficiencies/$id/respond")({
  head: seo("Respond to Deficiency", "Submit a response to a Deficiency Notice issued by AICTE."),
  component: Page,
});

function Page() {
  const { id } = Route.useParams();
  const user = useCurrentUser();
  const d = useStore((s) => s.deficiencies.find((x) => x.id === id));
  const a = useStore((s) => s.applications.find((x) => x.id === d?.appId));

  return (
    <InnerPage
      role="institution"
      crumbs={[{ label: "Deficiencies", to: "/institution/deficiencies" }, { label: id }]}
      title={`Respond to Deficiency ${id}`}
    >
      {!d || !a ? (
        <div className="notice">No Deficiency Notice found with number {id}.</div>
      ) : a.institutionId !== user?.institutionId ? (
        <div className="notice">This notice does not pertain to your institution.</div>
      ) : (
        <div className="space-y-5">
          <Panel title="Deficiency Notice">
            <dl className="dl">
              <dt>Notice No.</dt>
              <dd>{d.id}</dd>
              <dt>Application</dt>
              <dd>
                <Link to={`/institution/applications/${a.id}/status`} className="link">
                  {a.ref}
                </Link>
              </dd>
              <dt>Category</dt>
              <dd>{d.category}</dd>
              <dt>Description</dt>
              <dd>{d.description}</dd>
              <dt>Raised By</dt>
              <dd>
                {d.raisedBy} on {d.raisedOn}
              </dd>
              <dt>Respond By</dt>
              <dd>{d.dueOn}</dd>
              <dt>Status</dt>
              <dd>
                <Status s={d.status} />
              </dd>
              {d.response && (
                <>
                  <dt>Response</dt>
                  <dd>
                    {d.response}
                    <div className="text-xs text-muted-foreground">Submitted {d.respondedOn}</div>
                  </dd>
                </>
              )}
              {d.closedBy && (
                <>
                  <dt>Closure</dt>
                  <dd>
                    {d.closeRemark}
                    <div className="text-xs text-muted-foreground">
                      Closed by {d.closedBy} on {d.closedOn}
                    </div>
                  </dd>
                </>
              )}
            </dl>
          </Panel>
          {d.status === "Open" && <ResponseDraft key={d.id} notice={d} />}
          {d.status === "Responded" && (
            <div className="notice">
              Your response has been recorded and is pending re-verification by the scrutinising
              officer.
            </div>
          )}
        </div>
      )}
    </InnerPage>
  );
}

function ResponseDraft({ notice: d }: { notice: Deficiency }) {
  const [text, setText] = useState(d.draftResponse ?? "");
  const [file, setFile] = useState(d.draftAttachment ?? "");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  return (
    <Panel title="Your response">
      <p className="workspace-note mb-4">
        Respond to this specific query. Your original submitted application stays unchanged.
        Supporting files are recorded as metadata only.
      </p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          try {
            actions.respondDeficiency(d.id, text + (file ? ` [Attachment metadata: ${file}]` : ""));
          } catch (err) {
            setError((err as Error).message);
          }
        }}
        className="space-y-4"
      >
        <div>
          <label className="label" htmlFor="resp">
            Compliance response
          </label>
          <textarea
            id="resp"
            className="field"
            rows={6}
            required
            minLength={20}
            value={text}
            onChange={(e) => {
              setText(e.target.value);
              setMessage("");
            }}
          />
        </div>
        <div>
          <label className="label" htmlFor="att">
            Supporting PDF (metadata only)
          </label>
          <input
            id="att"
            type="file"
            accept="application/pdf"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f && (!f.name.toLowerCase().endsWith(".pdf") || f.size > 10 * 1024 * 1024)) {
                setError("Choose a PDF no larger than 10 MB.");
                return;
              }
              setFile(f?.name ?? "");
              setError("");
            }}
          />
          {file && (
            <p className="workspace-note mt-2">
              Saved selection: {file}. Re-selecting the original bytes is not required for this
              metadata demonstration.
            </p>
          )}
        </div>
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            className="btn btn-outline"
            onClick={() => {
              actions.saveResponseDraft(d.id, text, file);
              setMessage("Response draft saved in this browser.");
            }}
          >
            Save response draft
          </button>
          <button className="btn btn-primary">Submit response</button>
        </div>
        <p role="status" className="workflow-feedback">
          {message || (d.draftSavedOn ? `Draft saved · ${d.draftSavedOn}` : "")}
        </p>
        {error && (
          <p role="alert" className="text-destructive">
            {error}
          </p>
        )}
      </form>
    </Panel>
  );
}
