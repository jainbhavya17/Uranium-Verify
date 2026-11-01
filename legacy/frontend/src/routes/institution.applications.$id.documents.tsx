import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { InstitutionAppPage, WizardNav, DocTable } from "@/components/app-flow";
import { Panel } from "@/components/portal";
import { actions } from "@/lib/store";
import { EvidenceVersions } from "@/components/workflow-tools";
import { seo } from "@/lib/seo";

export const Route = createFileRoute("/institution/applications/$id/documents")({
  head: seo("Documents", "Upload supporting documents for the application."),
  component: Page,
});

function Page() {
  const { id } = Route.useParams();
  const [error, setError] = useState("");
  return (
    <InstitutionAppPage id={id} step="documents" title="Documents">
      {(a) => (
        <div className="space-y-5">
          <Panel title="Your supporting documents">
            <p className="workspace-note mb-4">
              Choose a PDF up to 10 MB. This prototype records filename and version metadata only;
              it does not upload or scan the original file.
            </p>
            <DocTable
              docs={a.status === "Draft" ? a.documents : (a.frozen?.documents ?? a.documents)}
              link={
                a.status !== "Draft"
                  ? undefined
                  : (code) => {
                      const d = a.documents.find((x) => x.code === code)!;
                      return d.fileName ? (
                        <button
                          className="link text-xs"
                          onClick={() => actions.removeDoc(a.id, code)}
                        >
                          Remove
                        </button>
                      ) : (
                        <label className="btn btn-outline text-xs cursor-pointer">
                          Upload
                          <input
                            type="file"
                            accept="application/pdf"
                            className="sr-only"
                            onChange={(e) => {
                              const f = e.target.files?.[0];
                              if (f) {
                                if (
                                  !f.name.toLowerCase().endsWith(".pdf") ||
                                  f.size > 10 * 1024 * 1024
                                ) {
                                  setError("Choose a PDF no larger than 10 MB.");
                                  return;
                                }
                                actions.uploadDoc(a.id, code, f.name);
                                setError("");
                              }
                            }}
                          />
                        </label>
                      );
                    }
              }
            />
            {error && (
              <p role="alert" className="text-destructive mt-3">
                {error}
              </p>
            )}
            {a.status === "Draft" && <WizardNav id={a.id} step="documents" />}
          </Panel>
          <EvidenceVersions docs={a.documents} />
        </div>
      )}
    </InstitutionAppPage>
  );
}
