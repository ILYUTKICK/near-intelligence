/**
 * Interim typed mirror of the canonical DataSource contract from
 * docs/API_SPECIFICATION.md (NI-010 interim state).
 *
 * The API projection is already sanitized upstream ("no auth header/base URL
 * with token"); this UI layer additionally refuses to render non-http(s)
 * URLs as links (see sanitizeSourceUrl in SourceDrawer). When NI-004 lands
 * the generated shared types, this module must be replaced by them.
 */
export interface DataSource {
  id: string;
  name: string;
  docs_url: string;
  verified_at: string;
  license_status: string;
  access_status: string;
  lineage: string[];
  expected_update_frequency: string;
  last_success_at: string | null;
}

/** A row of the frame's equivalent accessible data table. */
export interface FrameTableRow {
  /** Period label, e.g. "2026-11-02" — displayed as text. */
  period: string;
  /** Formatted value already including bounds labels, e.g. "≥ 1 234". */
  value: string;
  /** Optional per-point quality note, e.g. "partial coverage". */
  note?: string;
}

/** Chart display mode; historical frames pin the inspected dataset. */
export type ChartMode = "live" | "historical";
