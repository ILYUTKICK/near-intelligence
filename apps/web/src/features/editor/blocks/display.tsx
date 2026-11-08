/**
 * Small display helpers shared by the canonical block node views (NI-039).
 */

/** Shorten a UUID for on-card display; full ids stay in the properties panel. */
export function shortId(id: string | null | undefined): string {
  if (!id) {
    return "—";
  }
  return id.length > 13 ? `${id.slice(0, 8)}…${id.slice(-4)}` : id;
}

export function formatTimestamp(value: string | null | undefined): string {
  return value ?? "—";
}

export function fieldPair(term: string, detail: React.ReactNode, key?: string) {
  return (
    <div key={key} className="contents">
      <dt className="text-text-secondary">{term}</dt>
      <dd className="text-text break-all">{detail}</dd>
    </div>
  );
}
