import { api } from "../api";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { label } from "../presentation";
export type Row = Record<string, unknown>;
export const rows = (value: unknown): Row[] => (Array.isArray(value) ? (value as Row[]) : []);
export const record = (value: unknown): Row =>
  value && typeof value === "object" && !Array.isArray(value) ? (value as Row) : {};
export const value = (input: unknown): string => {
  if (input == null) return "Not available";
  if (Array.isArray(input)) return input.length ? input.map(value).join("; ") : "None recorded";
  if (typeof input === "object")
    return (
      Object.entries(input)
        .map(([key, item]) => `${label(key)}: ${value(item)}`)
        .join("; ") || "No details recorded"
    );
  return String(input);
};
export const options = (body: unknown) => ({
  method: "POST",
  headers: { "Idempotency-Key": crypto.randomUUID() },
  body: JSON.stringify(body),
});
export const mutate = (path: string, body: unknown) => api<Row>(path, options(body));
export function Fields({ data }: { data: Row }) {
  const entries = Object.entries(data).filter(([key]) => key !== "is_mock");
  const isReference = (key: string) => key === "id" || key.endsWith("_id") || key.endsWith("_ids");
  const references = entries.filter(([key, item]) => isReference(key) && item != null);
  return (
    <>
      <dl className="details">
        {entries
          .filter(([key]) => !isReference(key))
          .map(([key, item]) => (
            <div key={key}>
              <dt>{label(key)}</dt>
              <dd>
                <ReadableValue
                  item={
                    typeof item === "number" && key.endsWith("_at")
                      ? new Date(item * 1000).toLocaleString()
                      : item
                  }
                />
              </dd>
            </div>
          ))}
      </dl>
      {!!references.length && (
        <details className="record-references">
          <summary>Record references</summary>
          <dl className="details">
            {references.map(([key, item]) => (
              <div key={key}>
                <dt>{label(key)}</dt>
                <dd>
                  <ReadableValue item={item} />
                </dd>
              </div>
            ))}
          </dl>
        </details>
      )}
    </>
  );
}

function ReadableValue({ item }: { item: unknown }) {
  if (item == null) return <>Not available</>;
  if (typeof item === "boolean") return <>{item ? "Yes" : "No"}</>;
  if (Array.isArray(item))
    return item.length ? (
      <ul className="readable-list">
        {item.map((v, i) => (
          <li key={i}>
            <ReadableValue item={v} />
          </li>
        ))}
      </ul>
    ) : (
      <>None recorded</>
    );
  if (typeof item === "object") return <Fields data={item as Row} />;
  const text = String(item);
  if (/^https:\/\//.test(text))
    return (
      <a href={text} target="_blank" rel="noreferrer">
        View source ↗
      </a>
    );
  return <>{/^[A-Z][A-Z_]+$/.test(text) ? label(text) : text}</>;
}
export function Loading({ error, retry }: { error?: Error | null; retry?: () => void }) {
  return (
    <Card>
      {error ? (
        <>
          <p role="alert">{error.message}</p>
          <Button onClick={retry}>Retry</Button>
        </>
      ) : (
        <p role="status">Loading authorized records…</p>
      )}
    </Card>
  );
}
