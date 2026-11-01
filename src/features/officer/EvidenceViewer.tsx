import { useState, useEffect } from "react";
import { useSearchParams } from "@/features/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { EvidenceTrail } from "./EvidenceTrail";
import { label } from "../presentation";
import { type Row, record, rows, value, mutate, Loading, Fields } from "./common";
import type { User } from "../api";

export function EvidenceViewer({ id, user }: { id: string; user: User }) {
  const qc = useQueryClient();
  const [params, setParams] = useSearchParams();
  const [chosen, setChosen] = useState(params.get("version") ?? "");
  const [page, setPage] = useState(Number(params.get("page")) || 1);
  const [field, setField] = useState(params.get("field") ?? "");
  const [corrected, setCorrected] = useState("");
  const [rationale, setRationale] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const queryString = params.toString();
  useEffect(() => {
    const query = new URLSearchParams(queryString);
    setChosen(query.get("version") ?? "");
    setPage(Number(query.get("page")) || 1);
    setField(query.get("field") ?? "");
  }, [queryString, id]);
  function navigateSource(version: string, number: number, fieldId = "") {
    setParams({
      version,
      page: String(number),
      ...(fieldId ? { field: fieldId } : {}),
    });
  }
  const q = useQuery({
    queryKey: ["scrutiny", "evidence", id],
    queryFn: () => api<Row>(`/officer/cases/${id}/evidence`),
  });
  const versions = rows(q.data?.data.versions);
  const version = chosen ? versions.find((v) => v.id === chosen) : versions[0];
  const versionId = value(version?.id);
  const image = useQuery({
    queryKey: ["scrutiny-page", id, versionId, page],
    queryFn: () => api<Row>(`/officer/cases/${id}/evidence/${versionId}/pages/${page}`),
    enabled: !!version?.previewable,
    staleTime: 20_000,
  });
  if (q.isPending || q.error) return <Loading error={q.error} retry={() => void q.refetch()} />;
  if (!versions.length)
    return (
      <Card>
        <p>No evidence versions have been saved for this case.</p>
      </Card>
    );
  if (!version)
    return (
      <Card>
        <p role="alert">Requested evidence version is unavailable in this case.</p>
        <Button onClick={() => setParams({})}>Show authorized versions</Button>
      </Card>
    );
  const fields = rows(q.data.data.fields).filter((f) => f.version_id === version?.id);
  const active = fields.find((f) => f.id === field);
  const source = record(image.data?.data);
  const requestedBox = (params.get("region") ?? "").split(",").map(Number);
  const candidateBox = Array.isArray(active?.bbox) ? (active.bbox as number[]) : requestedBox;
  const box =
    candidateBox.length === 4 &&
    candidateBox.every(Number.isFinite) &&
    candidateBox[0] >= 0 &&
    candidateBox[1] >= 0 &&
    candidateBox[2] > candidateBox[0] &&
    candidateBox[3] > candidateBox[1] &&
    candidateBox[2] <= Number(source.width) &&
    candidateBox[3] <= Number(source.height)
      ? candidateBox
      : null;
  async function saveCorrection() {
    if (!active) return;
    setBusy(true);
    setError("");
    try {
      await mutate(`/officer/cases/${id}/corrections`, {
        expected_version: record(q.data!.data.review).version,
        field_id: active.id,
        normalized: corrected || null,
        rationale,
      });
      setRationale("");
      await qc.invalidateQueries({ queryKey: ["scrutiny"] });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Card>
        <label className="field">
          Immutable file version
          <select
            value={value(version?.id)}
            onChange={(e) => {
              setChosen(e.target.value);
              setPage(1);
              setField("");
              navigateSource(e.target.value, 1);
            }}
          >
            {versions.map((v) => (
              <option key={value(v.id)} value={value(v.id)}>
                {value(v.name)} · v{value(v.number)} · {label(value(record(v.processing).state))}
              </option>
            ))}
          </select>
        </label>
        <p className="hash">SHA-256 {value(version?.sha256)}</p>
      </Card>
      <div className="evidence-split">
        <Card>
          <div className="form-actions">
            <Button
              variant="outline"
              disabled={page <= 1}
              onClick={() => navigateSource(versionId, page - 1, field)}
            >
              Previous page
            </Button>
            <label className="field">
              Page
              <input
                type="number"
                min={1}
                max={50}
                value={page}
                onChange={(e) =>
                  navigateSource(
                    versionId,
                    Math.max(1, Math.min(50, Number(e.target.value))),
                    field,
                  )
                }
              />
            </label>
            <Button
              variant="outline"
              disabled={page >= 50}
              onClick={() => navigateSource(versionId, page + 1, field)}
            >
              Next page
            </Button>
          </div>
          {!version?.previewable ? (
            <p role="status">File remains quarantined. Source rendering is unavailable.</p>
          ) : image.isPending ? (
            <p role="status">Rendering the authorized original…</p>
          ) : image.error ? (
            <p role="alert">{image.error.message}</p>
          ) : (
            <div className="page-region-view">
              <img
                alt={`Original version ${value(version?.number)}, page ${page}`}
                src={`data:image/png;base64,${value(source.png)}`}
              />
              {box && (!active || Number(active.page) === page) && (
                <svg
                  viewBox={`0 0 ${value(source.width)} ${value(source.height)}`}
                  aria-label="Selected extracted-field source region"
                >
                  <rect x={box[0]} y={box[1]} width={box[2] - box[0]} height={box[3] - box[1]} />
                </svg>
              )}
            </div>
          )}
          <p>
            Highlights reference original PDF points or oriented image pixels. Preview is audited.
          </p>
        </Card>
        <Card>
          <h2>Extracted and reviewed information</h2>
          {fields.length ? (
            fields.map((f) => (
              <div key={value(f.id)} className="observation-row">
                <Button
                  variant="outline"
                  onClick={() => {
                    setField(value(f.id));
                    setPage(Number(f.page));
                    setCorrected(value(record(f.machine).normalized));
                    navigateSource(versionId, Number(f.page), value(f.id));
                  }}
                >
                  {label(value(f.key))} · page {value(f.page)}
                </Button>
                <p>
                  Original: {value(record(f.machine).raw)} → {value(record(f.machine).normalized)}
                </p>
                <small>
                  {value(record(f.machine).method).includes("FIXTURE")
                    ? "Reviewed sample annotation · not automated extraction"
                    : `Method: ${value(record(f.machine).method)} · Confidence: ${value(f.confidence)}`}
                </small>
                {rows(q.data.data.corrections)
                  .filter((c) => c.field_id === f.id)
                  .map((c) => (
                    <p key={value(c.id)}>
                      Correction: {value(record(c.value).normalized)} · {value(c.rationale)} · actor{" "}
                      {value(c.actor_id)}
                    </p>
                  ))}
              </div>
            ))
          ) : (
            <p>
              No extracted information is available. A sample attachment is not treated as live OCR.
            </p>
          )}
          {active && user.roles.some((r) => ["officer", "supervisor"].includes(r)) && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void saveCorrection();
              }}
            >
              <h3>Append a correction</h3>
              <label className="field">
                Corrected normalized value (blank means unknown)
                <input value={corrected} onChange={(e) => setCorrected(e.target.value)} />
              </label>
              <label className="field">
                Correction rationale
                <textarea
                  minLength={10}
                  maxLength={2000}
                  required
                  value={rationale}
                  onChange={(e) => setRationale(e.target.value)}
                />
              </label>
              <Button disabled={busy}>Save audited correction</Button>
              {error && <p role="alert">{error}</p>}
            </form>
          )}
        </Card>
      </div>
      <Card>
        <h2>Compare information across documents</h2>
        {Array.from(new Set(rows(q.data.data.fields).map((f) => value(f.key)))).map((key) => (
          <article key={key} className="observation-row">
            <h3>{key.replaceAll("_", " ")}</h3>
            {rows(q.data.data.fields)
              .filter((f) => f.key === key)
              .map((f) => (
                <p key={value(f.id)}>
                  {value(versions.find((v) => v.id === f.version_id)?.name)} · page {value(f.page)}:{" "}
                  {value(record(f.machine).normalized)}
                  {rows(q.data.data.corrections)
                    .filter((c) => c.field_id === f.id)
                    .map((c) => (
                      <small key={value(c.id)}>
                        {" "}
                        → human correction {value(record(c.value).normalized)}
                      </small>
                    ))}
                </p>
              ))}
          </article>
        ))}
      </Card>
      <Card>
        <h2>Evidence graph</h2>
        <EvidenceTrail
          nodes={rows(q.data.data.nodes)}
          edges={rows(q.data.data.edges)}
          versions={versions}
          fields={rows(q.data.data.fields)}
          openSource={navigateSource}
        />
      </Card>
    </>
  );
}
