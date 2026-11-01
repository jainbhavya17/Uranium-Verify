import { FileSearch, ArrowRight } from "lucide-react";
import { Button } from "../components/ui/button";
import { label } from "../presentation";
import { Fields, record, value, type Row } from "./common";

/** Render saved evidence relationships as readable source cards, with direct source navigation. */
export function EvidenceTrail({
  nodes,
  edges,
  versions,
  fields,
  openSource,
}: {
  nodes: Row[];
  edges: Row[];
  versions: Row[];
  fields: Row[];
  openSource: (version: string, page: number, field?: string) => void;
}) {
  function describe(node?: Row) {
    if (!node) return "Unavailable evidence";
    const ref = record(node.reference),
      field = fields.find((f) => f.id === ref.field_id);
    const version = versions.find((v) => v.id === ref.version_id);
    if (field) return `${label(value(field.key))} · page ${value(field.page)}`;
    if (version) return `${value(version.name)} · version ${value(version.number)}`;
    return (
      (
        {
          DECLARATION: "Institution’s declared information",
          APPROVED_SNAPSHOT: "Previous approved record",
          RULE_EVALUATION: "Application check",
          FINDING_INPUT: "Evidence behind a finding",
          CHECKED_VERSION: "Checked document",
          DOCUMENT_VERSION: "Original document",
          REGULATORY_SOURCE: "Applicable regulation",
        } as Record<string, string>
      )[value(node.kind)] ?? label(value(node.kind))
    );
  }
  if (!nodes.length)
    return <p>Evidence links appear after document processing or application checks.</p>;
  return (
    <>
      <p>Follow how the original documents, declared details and rules support each finding.</p>
      <div className="evidence-trail">
        {nodes.map((node) => {
          const ref = record(node.reference),
            field = fields.find((f) => f.id === ref.field_id);
          const version = versions.find((v) => v.id === ref.version_id);
          return (
            <article key={value(node.id)} className="evidence-trail-node">
              <FileSearch size={19} aria-hidden="true" />
              <div>
                <h3>{describe(node)}</h3>
                {version && (
                  <Button
                    variant="outline"
                    onClick={() =>
                      openSource(
                        value(version.id),
                        Number(field?.page ?? ref.page ?? 1),
                        field ? value(field.id) : "",
                      )
                    }
                  >
                    Open original source
                  </Button>
                )}
                <details>
                  <summary>View supporting details</summary>
                  <Fields data={ref} />
                </details>
              </div>
            </article>
          );
        })}
      </div>
      {!!edges.length && (
        <details>
          <summary>How the evidence connects ({edges.length})</summary>
          <ul className="evidence-connections">
            {edges.map((edge) => (
              <li key={value(edge.id)}>
                <span>{describe(nodes.find((n) => n.id === edge.from))}</span>
                <span className="evidence-relationship">
                  <ArrowRight size={14} aria-hidden="true" />
                  {label(value(edge.relationship))}
                </span>
                <span>{describe(nodes.find((n) => n.id === edge.to))}</span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </>
  );
}
