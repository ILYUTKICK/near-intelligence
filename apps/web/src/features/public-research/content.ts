/**
 * Reviewed editorial copy for the public routes (NI-011).
 *
 * Every string here is deliberately free of metrics: quantitative claims are
 * bound to versioned datasets and definitions by later tasks (NI-012,
 * NI-014) and must never be typed by hand. No promises, no live claims, no
 * unfinished feature announcements.
 */

export const landing = {
  title: "NEAR Intelligence",
  standfirst:
    "Evidence-first investment research on the NEAR ecosystem. Every published number carries its source, definition version and limitations — and a missing value is never shown as zero.",
  whatYouCanDo:
    "Read the full thesis, follow each economic mechanism, and check the methodology before trusting any conclusion.",
  links: [
    { label: "Read the research", href: "/research" },
    { label: "How the numbers are made", href: "/methodology" },
  ],
} as const;

export const mechanism = {
  heading: "The economic mechanism",
  intro:
    "The investment question is a chain of distinct steps, each of which can hold or break on its own evidence. Treating them as one number is the mistake this project exists to avoid.",
  stages: [
    {
      id: "activity",
      title: "Activity",
      body: "People use applications on NEAR. Usage is observable on-chain, but raw transaction counts say nothing about economic value by themselves.",
    },
    {
      id: "fees",
      title: "Fees",
      body: "Usage produces fees. Fee amounts are exact on-chain facts and are the first quantity worth measuring precisely.",
    },
    {
      id: "revenue",
      title: "Revenue",
      body: "Fees accrue somewhere — to validators, to a protocol treasury, to application contracts. Which part is economically attributable revenue is a definition question, answered per source with explicit boundaries.",
    },
    {
      id: "conversion",
      title: "Conversion",
      body: "A treasury may convert holdings or purchase NEAR on the market. Purchases are observable events with their own provenance.",
    },
    {
      id: "supply",
      title: "Retention & supply",
      body: "Purchases can support demand; burns permanently remove supply. These are different effects and are never presented as one movement.",
    },
  ],
  cautions: [
    "Treasury purchases do not reduce total supply — burns do.",
    "Gross fees, attributable revenue and treasury payouts are different metrics; this project never relabels one as another.",
  ],
} as const;

export const research = {
  title: "Research",
  standfirst:
    "The published thesis with its supporting and contrary evidence. Quantitative sections are bound to versioned datasets; this page is the reading structure they will live in.",
  outline: [
    {
      id: "executive-summary",
      title: "Executive summary",
      body: "The complete argument in one place, with explicit status for every claim.",
    },
    {
      id: "question",
      title: "The question",
      body: "Does cross-chain adoption translate into sustainable revenue and measurable NEAR token value capture?",
    },
    {
      id: "ecosystem",
      title: "Ecosystem and activity",
      body: "What is observable on-chain, and what those observations can and cannot support.",
    },
    {
      id: "h1",
      title: "H1 — Revenue generation",
      body: "Status: to be published with the reviewed findings. This anchor exists so citations can already reference the section.",
    },
    {
      id: "h2",
      title: "H2 — Value capture",
      body: "Status: to be published with the reviewed findings.",
    },
    {
      id: "h3",
      title: "H3 — Retention effects",
      body: "Status: to be published with the reviewed findings.",
    },
    {
      id: "h4",
      title: "H4 — Supply dynamics",
      body: "Status: to be published with the reviewed findings.",
    },
    {
      id: "limits",
      title: "Limits and contrary evidence",
      body: "Evidence against the thesis is published with the same care as evidence for it.",
    },
  ],
} as const;

export const methodology = {
  title: "Methodology",
  standfirst:
    "How the numbers are made: providers, definitions, collection, cleaning and the reproduction path. Published so a reader can assess the evidence before trusting a conclusion.",
  sections: [
    {
      id: "sources",
      title: "Sources and rights",
      body: "Every provider is recorded with its endpoints, verification date, license and access status. Raw historical inputs remain in the operator's archive and are shared only through verified, hash-checked handoffs — a fresh clone of this repository intentionally does not contain them.",
    },
    {
      id: "definitions",
      title: "Definitions",
      body: "Metrics are defined once, in a versioned registry, and every chart references that definition. Gross fees, attributable revenue, treasury payouts and supply movements stay distinct quantities.",
    },
    {
      id: "collection",
      title: "Collection and cleaning",
      body: "Collection runs with explicit caps and allowlists; stopped collectors stay stopped. Cleaning steps are documented next to the datasets they produced.",
    },
    {
      id: "reproduce",
      title: "Reproduction",
      body: "Published analyses ship their inputs' provenance, code and locks so a reader can rerun them offline. The exact reproduction recipe is published together with the first quantitative release.",
    },
  ],
} as const;
