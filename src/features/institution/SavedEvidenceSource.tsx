import { useSearchParams } from "@/features/navigation";
import { useQuery } from "@tanstack/react-query";
import { api, type Evidence } from "../api";
import { Card } from "../components/ui/card";
import { ProcessingSlot } from "./ProcessingSlot";
import type { Workflow, Item } from "./types";

export function SavedEvidenceSource({ s }: { s: Workflow }) {
  const [params] = useSearchParams();
  const version = params.get("sourceVersion");
  const q = useQuery({
    queryKey: ["source-versions", s.application_id],
    enabled: !!version,
    queryFn: () => api<Evidence[]>(`/applications/${s.application_id}/documents`),
  });
  if (!version) return null;
  const v = q.data?.data.find((v) => v.id === version);
  if (!v)
    return (
      <p role="status">
        {q.error?.message ??
          (q.isPending ? "Loading saved source…" : "Source unavailable in this application.")}
      </p>
    );
  const item: Item = {
    ...s.checklist.items[0],
    code: "saved-source",
    evidence: {
      id: v.id,
      document_id: v.document_id,
      number: v.number,
      name: v.original_name,
      status: v.status,
      sha256: v.sha256,
      is_mock: v.is_mock,
      document_type: "",
    },
  };
  return (
    <Card>
      <h2>
        Saved source · {v.original_name} · original version {v.number}
      </h2>
      <p className="hash">SHA-256 {v.sha256}</p>
      <ProcessingSlot s={{ ...s, editable: false }} item={item} documentType="" />
    </Card>
  );
}
