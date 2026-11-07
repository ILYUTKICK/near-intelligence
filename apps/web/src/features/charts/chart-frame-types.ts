/**
 * Chart frame shared types.
 *
 * `DataSource` is now the generated API contract (packages/shared-types,
 * NI-032/NI-004) — the NI-010 interim mirror was replaced by it as this
 * module always instructed. The API projection is sanitized upstream ("no
 * auth header/base URL with token"); this UI layer additionally refuses to
 * render non-http(s) URLs as links (see sanitizeSourceUrl in SourceDrawer).
 */
import type { components } from "@near-intelligence/shared-types";

export type DataSource = components["schemas"]["DataSourceResponse"];

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
