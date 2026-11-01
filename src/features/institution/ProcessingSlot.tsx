import { useState, useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Preview } from "../api";
import type { components } from "../../../packages/contracts/openapi";
import type { Item, Workflow } from "./types";
import { label } from "../presentation";
import { Button } from "../components/ui/button";
type Job = components["schemas"]["ProcessingView"];
type Policy = {
  pdf_bytes: number;
  image_bytes: number;
  max_files: number;
  max_pages: number;
  scanner_mode: string;
};
const terminal = new Set([
  "PROCESSED",
  "NEEDS_REUPLOAD",
  "MANUAL_REVIEW",
  "PROCESSING_FAILED",
  "SAFETY_UNAVAILABLE",
  "QUARANTINED_PENDING_SAFETY",
]);

function sendFile(path: string, file: File | FormData, progress: (n: number) => void) {
  return new Promise<{ application_version: number }>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `/api/v1${path}`);
    xhr.timeout = 120_000;
    if (file instanceof File) xhr.setRequestHeader("Content-Type", file.type);
    xhr.setRequestHeader("Idempotency-Key", crypto.randomUUID());
    xhr.setRequestHeader(
      "X-CSRF-Token",
      document.cookie
        .split("; ")
        .find((x) => x.startsWith("uv_csrf="))
        ?.slice(8) ?? "",
    );
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) progress(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onerror = () => reject(new Error("Upload failed. Refresh saved versions before retrying."));
    xhr.ontimeout = () =>
      reject(new Error("Upload timed out. Refresh saved versions before retrying."));
    xhr.onload = () => {
      try {
        const body = JSON.parse(xhr.responseText);
        if (xhr.status < 200 || xhr.status >= 300)
          reject(new Error(body.error?.message ?? "Upload failed"));
        else resolve(Array.isArray(body.data) ? body.data.at(-1) : body.data);
      } catch {
        reject(new Error("Upload service unavailable."));
      }
    };
    xhr.send(file);
  });
}

export function ProcessingSlot({
  s,
  item,
  documentType,
}: {
  s: Workflow;
  item: Item;
  documentType: string;
}) {
  const qc = useQueryClient();
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [page, setPage] = useState(1);
  const [region, setRegion] = useState("");
  const policy = useQuery({
    queryKey: ["processing-policy"],
    queryFn: () => api<Policy>("/processing/policy"),
  });
  const evidence = item.evidence;
  const q = useQuery({
    queryKey: ["processing", s.application_id, evidence?.id],
    queryFn: () =>
      api<Job>(`/applications/${s.application_id}/documents/${evidence!.id}/processing`),
    enabled: !!evidence && evidence.status !== "SYNTHETIC_FIXTURE",
    refetchInterval: (query) => (terminal.has(query.state.data?.data.state ?? "") ? false : 1500),
  });
  const observedState = q.data?.data.state;
  useEffect(() => {
    if (observedState && terminal.has(observedState)) {
      void qc.invalidateQueries({
        queryKey: ["institution", "state", s.application_id],
      });
      void qc.invalidateQueries({
        queryKey: ["institution", "versions", s.application_id],
      });
    }
  }, [observedState, qc, s.application_id]);
  async function refresh() {
    await qc.invalidateQueries({ queryKey: ["institution"] });
    await qc.invalidateQueries({ queryKey: ["processing"] });
  }
  async function upload() {
    if (!policy.data || !files.length) return;
    const p = policy.data.data;
    setError("");
    setNotice("");
    if (files.length > p.max_files) {
      setError(`Choose at most ${p.max_files} files per batch.`);
      return;
    }
    for (const file of files) {
      const expected: Record<string, string> = {
        pdf: "application/pdf",
        png: "image/png",
        jpg: "image/jpeg",
        jpeg: "image/jpeg",
      };
      if (expected[file.name.split(".").pop()?.toLowerCase() ?? ""] !== file.type) {
        setError("Choose PDF, PNG or JPEG with a matching extension and MIME type.");
        return;
      }
      if (
        !file.size ||
        file.size > (file.type === "application/pdf" ? p.pdf_bytes : p.image_bytes)
      ) {
        setError("File exceeds the engineering byte budget or is empty.");
        return;
      }
    }
    setBusy(true);
    try {
      if (files.length > 1) {
        const body = new FormData();
        for (const file of files) body.append("files", file);
        setProgress(0);
        setNotice(`Uploading ${files.length} files in one bounded request`);
        const params = new URLSearchParams({
          requirement_id: item.id,
          document_type: documentType,
          expected_version: String(s.version),
        });
        await sendFile(
          `/applications/${s.application_id}/documents/batch?${params}`,
          body,
          setProgress,
        );
      } else {
        for (const [index, file] of files.entries()) {
          setProgress(0);
          setNotice(`Uploading ${index + 1} of ${files.length}: ${file.name}`);
          const params = new URLSearchParams({
            requirement_id: item.id,
            document_type: documentType,
            expected_version: String(s.version),
            filename: file.name,
          });
          await sendFile(
            `/applications/${s.application_id}/documents/upload?${params}`,
            file,
            setProgress,
          );
        }
      }
      setFiles([]);
      setNotice(
        "Upload saved in private quarantine. Processing progress reflects the local worker.",
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
      await refresh();
    }
  }
  async function action(kind: "retry" | "manual-review") {
    setError("");
    setBusy(true);
    try {
      const result = await api<{ message?: string }>(
        `/applications/${s.application_id}/documents/${evidence!.id}/${kind}`,
        {
          method: "POST",
          headers: { "Idempotency-Key": crypto.randomUUID() },
          body: JSON.stringify({ expected_version: s.version }),
        },
      );
      setNotice(result.data.message ?? "Reprocessing queued. Old results remain retained.");
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function open(targetPage = 1, box = "") {
    if (!evidence) return;
    try {
      const result = await api<Preview>(
        `/documents/${evidence.document_id}/versions/${evidence.number}/preview`,
        { method: "POST" },
      );
      setPreview(result.data);
      setPage(targetPage);
      setRegion(box);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  const job = q.data?.data;
  return (
    <section className="processing-slot" aria-label={`File processing ${item.code}`}>
      {s.editable && !["NOT_APPLICABLE", "NOT_DUE"].includes(item.applicability) && (
        <>
          <label className="field">
            Upload {item.label}
            <input
              type="file"
              multiple
              accept="application/pdf,image/png,image/jpeg,.pdf,.png,.jpg,.jpeg"
              disabled={busy}
              onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
            />
          </label>
          <p className="notice">
            PDF: {policy.data ? Math.round(policy.data.data.pdf_bytes / 1024 ** 2) : 20} MiB /{" "}
            {policy.data?.data.max_pages ?? 50} pages. Images:{" "}
            {policy.data ? Math.round(policy.data.data.image_bytes / 1024 ** 2) : 10} MiB. Up to{" "}
            {policy.data?.data.max_files ?? 10} files per request; the last file becomes the
            selected version. Use a clear, complete scan.
          </p>
          <Button
            variant="outline"
            disabled={busy || !files.length || !policy.data}
            onClick={() => void upload()}
          >
            Upload and process original{files.length > 1 ? "s" : ""}
          </Button>
        </>
      )}
      {busy && (
        <label>
          Transferred bytes{" "}
          <progress max={100} value={progress}>
            {progress}%
          </progress>
        </label>
      )}
      {notice && <p role="status">{notice}</p>}
      {error && <p role="alert">{error}</p>}
      {policy.error && <p role="alert">{policy.error.message}</p>}
      {q.error && <p role="alert">{q.error.message}</p>}
      {job && (
        <div className="processing-result">
          <p role="status">
            <strong>{label(job.state)}</strong>
          </p>
          <details>
            <summary>Processing details</summary>
            <p>
              Attempt {job.attempt} · Safety scanner: {label(job.scanner_mode)} ·{" "}
              {label(job.scan_status)}
            </p>
          </details>
          {job.scanner_mode === "MOCK_TEST" && (
            <p className="notice">
              MOCK scanner: synthetic demonstration only. No real malware protection.
            </p>
          )}
          {job.message && <p>{job.message}</p>}
          {["UPLOADED", "REPROCESSING"].includes(job.state) && (
            <p>Your document is waiting to be processed. This page updates automatically.</p>
          )}
          {s.editable && terminal.has(job.state) && (job.attempt ?? 0) < 3 && (
            <Button variant="outline" disabled={busy} onClick={() => void action("retry")}>
              Retry / reprocess original
            </Button>
          )}
          {s.editable && job.state === "MANUAL_REVIEW" && (
            <Button variant="outline" disabled={busy} onClick={() => void action("manual-review")}>
              Request manual review
            </Button>
          )}
          {(job.accepted || job.result_id) && (
            <Button variant="outline" onClick={() => void open()}>
              Preview processed original
            </Button>
          )}
          {!!job.fields.length && (
            <details>
              <summary>Extracted fields and source regions ({job.fields.length})</summary>
              <p>{job.processor_version} · machine observations requiring review.</p>
              <dl className="extracted-fields">
                {job.fields.map((f) => (
                  <div key={f.id}>
                    <dt>{f.key.replaceAll("_", " ")}</dt>
                    <dd>
                      {f.normalized ?? "Unknown"}
                      <small>
                        Raw: {f.raw} · {f.method} · {f.uncertainty} · confidence{" "}
                        {Math.round((f.confidence ?? 0) * 100)}%
                      </small>
                      <button
                        className="source-link"
                        onClick={() => void open(f.page, f.bbox.join(", "))}
                      >
                        Original v{evidence?.number} · page {f.page} · region{" "}
                        {f.bbox.map((v) => v.toFixed(1)).join(", ")}
                      </button>
                    </dd>
                  </div>
                ))}
              </dl>
              <p>
                Unknown / absent: {job.unknown_fields?.join(", ") || "none"}. Missing values were
                not inferred.
              </p>
            </details>
          )}
          <details>
            <summary>Observed lifecycle</summary>
            <ol>
              {job.events.map((e, i) => (
                <li key={i}>
                  {String(e.state).replaceAll("_", " ")} ·{" "}
                  {new Date(Number(e.at) * 1000).toLocaleTimeString()}
                </li>
              ))}
            </ol>
          </details>
        </div>
      )}
      {preview && (
        <div className="phase2-preview">
          <h3>
            Original version {evidence?.number} · page {page}
          </h3>
          {region && (
            <p>
              Source region [x0, y0, x1, y1]: {region}. PDF points; image coordinates in pixels.
            </p>
          )}
          <iframe title="Private processed original" src={`${preview.url}#page=${page}`} />
          <Button variant="ghost" onClick={() => setPreview(null)}>
            Close original preview
          </Button>
        </div>
      )}
    </section>
  );
}
