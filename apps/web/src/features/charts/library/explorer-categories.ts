/**
 * The five public data-explorer categories (NI-015).
 *
 * INFORMATION_ARCHITECTURE.md defines the public data routes as
 * "/data/[category] — Same analytical components as workspace": the
 * categories are the workspace Data Explorer grouping (workspaceNav labels),
 * not the chart registry's own five registry categories. Each explorer
 * category therefore maps to the registry categories (`CATALOG_CATEGORIES`,
 * the only values GET /api/charts?category=… accepts) whose registered
 * charts answer that category's question. The mapping is a UI grouping of
 * existing registry entries — it never relabels a chart, and /charts stays
 * the flat catalog by registry category.
 *
 * The reverse direction is a total function: every registry category belongs
 * to exactly one explorer category or to none (model-category charts stay in
 * the chart library and the model section — the data explorer has no Models
 * entry). An explorer category with no registry categories (Network
 * Activity, Ecosystem) has no registered chart and renders its honest
 * explanation instead of placeholder cards; the explanation is checked
 * against the live catalog, so a chart registered under a mapped category
 * appears without any code change.
 *
 * Copy rules (AGENTS.md): missing is not zero; every availability statement
 * is either derived from the live catalog or states the recorded gate;
 * English only (OQ-06).
 */

export interface ExplorerCategory {
  /** URL slug under /data (INFORMATION_ARCHITECTURE.md public data routes). */
  slug: string;
  /** workspaceNav / workspace sidebar label. */
  label: string;
  /**
   * Registry categories (the API's closed `category` values) whose charts
   * are listed here; empty means "no registered chart yet".
   */
  registryCategories: readonly string[];
  /** Chart definitions to feature above the catalog, when registered. */
  featuredChartIds?: readonly string[];
  /** The analytical question headline (UI_SCREEN_SPECIFICATIONS.md rows). */
  question: string;
  /** What this category covers, stated before any chart is shown. */
  scopeNote: string;
  /**
   * The honest explanation for a category with no registered charts —
   * recorded gate, never a placeholder ("empty until source validation"
   * mirrors the workspaceNav availabilityNote).
   */
  emptyExplanation: {
    heading: string;
    body: string;
  };
}

export const EXPLORER_CATEGORIES: readonly ExplorerCategory[] = [
  {
    slug: "network",
    label: "Network Activity",
    registryCategories: [],
    question: "What verified network-level activity can be measured?",
    scopeNote:
      "This category is reserved for network-level verified counts and fees with "
      + "signer/receiver/address semantics made explicit. No such chart definition is "
      + "registered yet, so nothing is measured here rather than guessed.",
    emptyExplanation: {
      heading: "No network-level chart is registered yet",
      body:
        "Verified network activity (signer and receiver counts, network-wide fees) has "
        + "no approved chart definition in the registry, so this category states the gap "
        + "instead of showing placeholder activity. This is not zero. Availability varies "
        + "by source: a chart appears here only after its metric definitions and sources "
        + "are validated and the chart is registered.",
    },
  },
  {
    slug: "intents",
    label: "Intents & Adoption",
    registryCategories: ["activity"],
    featuredChartIds: ["observed-conversions"],
    question:
      "Is observed Intents activity growing, and how much NEAR is the observed cohort acquiring?",
    scopeNote:
      "Charts from the registry activity category: provider-reported Intents gross "
      + "volume, observed cohort purchases and conversion events, and the purchase "
      + "quantity versus USD-estimate comparison. Provider turnover is not token value, "
      + "and an event count is never a user count.",
    emptyExplanation: {
      heading: "No chart is registered for this category yet",
      body:
        "Nothing is shown rather than placeholders; a chart appears once it is "
        + "registered with validated inputs.",
    },
  },
  {
    slug: "revenue",
    label: "Revenue & Fees",
    registryCategories: ["fees", "treasury"],
    featuredChartIds: ["gross-fees", "treasury-payouts"],
    question:
      "What gross fees are reported, and what cash payouts reached the selected wallets?",
    scopeNote:
      "Charts from the registry fees and treasury categories: provider-reported gross "
      + "fees, the fee/volume association, and treasury payouts — never summed across "
      + "qualified sources, and never presented as attributable protocol revenue.",
    emptyExplanation: {
      heading: "No chart is registered for this category yet",
      body:
        "Nothing is shown rather than placeholders; a chart appears once it is "
        + "registered with validated inputs.",
    },
  },
  {
    slug: "token-economics",
    label: "Token Economics",
    registryCategories: ["supply"],
    featuredChartIds: ["supply-context"],
    question: "How large are observed purchases relative to net supply growth?",
    scopeNote:
      "Charts from the registry supply category: purchases in the context of net "
      + "supply change, as matched-boundary scale comparisons. Purchases are never "
      + "subtracted from total supply — burns, not purchases, reduce supply.",
    emptyExplanation: {
      heading: "No chart is registered for this category yet",
      body:
        "Nothing is shown rather than placeholders; a chart appears once it is "
        + "registered with validated inputs.",
    },
  },
  {
    slug: "ecosystem",
    label: "Ecosystem",
    registryCategories: [],
    question: "Which applications and integrations are verifiable?",
    scopeNote:
      "This category is reserved for application, integration and concentration "
      + "measures. It stays empty until source validation, exactly as stated in the "
      + "navigation — no collector-to-customer inference is drawn.",
    emptyExplanation: {
      heading: "Empty until source validation",
      body:
        "Available application, integration and concentration measures require source "
        + "validation that has not happened yet, so this category is honestly empty "
        + "rather than filled with placeholder entries. This is not zero. The data "
        + "requirements are recorded in the methodology.",
    },
  },
] as const;

/** The explorer category for a URL slug, or null for an unknown slug. */
export function explorerCategoryBySlug(slug: string): ExplorerCategory | null {
  return EXPLORER_CATEGORIES.find((category) => category.slug === slug) ?? null;
}

/**
 * The explorer category a registry category's charts belong to, or null for
 * registry categories outside the explorer (model charts). Total over the
 * registry's closed category values: activity→intents, fees→revenue,
 * treasury→revenue, supply→token-economics, model→none.
 */
export function explorerForRegistryCategory(registryCategory: string): ExplorerCategory | null {
  return EXPLORER_CATEGORIES.find((category) =>
    category.registryCategories.includes(registryCategory)
  ) ?? null;
}
