"use client";

import { ChartView } from "@/features/charts/renderer/ChartView";
import { formatUpdated } from "@/features/documents/list/format";
import type { ShareBlockPayload, ShareProjectionPayload } from "@/features/shares/share-schema";

/**
 * Read-only rendering of one shared frozen revision (NI-060, ADR-021).
 *
 * The viewer renders EXACTLY the allowlisted projection the owner consented
 * to — a deliberate static renderer, NOT the Tiptap editor and NOT the
 * workspace chrome: no editing surface, no private-route links, no refresh
 * or latest-data action (the frozen `ChartViewResponse` is passed to the
 * chart renderer as a controlled view; without a loader or a range callback
 * the renderer draws only what was pinned and shows its exact-value table).
 * Every quantitative element keeps its provenance (sources, dataset
 * versions, quality statuses); the limitations line states the frozen scope.
 */

const textUi = "text-body leading-body text-text";

type RunList = Extract<ShareBlockPayload, { block_type: "paragraph" }>["runs"];
type BodyChildren = Extract<ShareBlockPayload, { block_type: "insight" }>["body"];
type ListItems = Extract<ShareBlockPayload, { block_type: "bullet_list" | "ordered_list" }>["items"];

function RichRuns({ runs }: { runs: RunList }) {
  return (
    <>
      {runs.map((run, index) => {
        let node: React.ReactNode = run.text;
        for (const mark of [...run.marks].reverse()) {
          if (mark.type === "bold") {
            node = <strong>{node}</strong>;
          } else if (mark.type === "italic") {
            node = <em>{node}</em>;
          } else {
            // Canonical link mark: scheme/credential rules were enforced by
            // the server's canonical rich-text parser; rel keeps the shared
            // page's context out of the target.
            node = (
              <a href={mark.attrs.href} rel="noreferrer noopener"
                className="text-accent underline underline-offset-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus">
                {node}
              </a>
            );
          }
        }
        return <span key={index}>{node}</span>;
      })}
    </>
  );
}

function BodyContent({ body }: { body: BodyChildren }) {
  return (
    <>
      {body.map((node, index) => node.type === "paragraph" ? (
        <p key={index} className={textUi}>
          <RichRuns runs={node.content} />
        </p>
      ) : (
        <ListContent key={index} ordered={node.type === "ordered_list"} items={node.content} />
      ))}
    </>
  );
}

function ListContent({ ordered, items }: { ordered: boolean; items: ListItems }) {
  const ListTag = ordered ? "ol" : "ul";
  return (
    <ListTag className={`mt-2 space-y-1 ps-6 ${ordered ? "list-decimal" : "list-disc"} ${textUi}`}>
      {items.map((item, index) => (
        <li key={index}>
          {item.content.map((child, childIndex) => child.type === "paragraph" ? (
            <span key={childIndex} className="block">
              <RichRuns runs={child.content} />
            </span>
          ) : (
            <ListContent key={childIndex} ordered={child.type === "ordered_list"} items={child.content} />
          ))}
        </li>
      ))}
    </ListTag>
  );
}

function ChartBlock({ block }: { block: Extract<ShareBlockPayload, { block_type: "liveChart" }> }) {
  const view = block.view;
  return (
    <figure className="mt-6 rounded-surface border border-border p-5" data-testid="share-chart">
      <ChartView definition={view.definition} selection={view.selection} view={view}
        mode="live" height={320} />
      <figcaption className="mt-2 text-metadata leading-metadata text-text-secondary">
        Frozen chart: pinned dataset {view.dataset.dataset_key} v{view.dataset.version} ·
        context hash {view.context_hash.slice(0, 12)}… · resolved {formatUpdated(view.resolved_at)} UTC.
        This figure never refreshes.
      </figcaption>
    </figure>
  );
}

function DataTableBlock({ block }: { block: Extract<ShareBlockPayload, { block_type: "dataTable" }> }) {
  const rows = block.rows ?? [];
  return (
    <figure className="mt-6 rounded-surface border border-border p-5" data-testid="share-table">
      <div role="region" aria-label="Shared data table" tabIndex={0}
        className="max-h-64 overflow-auto rounded-control border border-border">
        <table className="w-full border-collapse text-left tabular-nums">
          <thead>
            <tr className="bg-surface-muted">
              {block.columns.map((column) => (
                <th key={column.key} scope="col" className="font-ui text-ui leading-ui px-3 py-2 font-medium">
                  {column.label}{column.unit ? ` (${column.unit})` : ""}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr><td className="text-ui leading-ui text-text-secondary px-3 py-2">
                No authored rows — this is the table&apos;s honest empty state, not zero.
              </td></tr>
            ) : rows.map((row, rowIndex) => (
              <tr key={rowIndex} className="border-t border-border">
                {block.columns.map((column, columnIndex) => (
                  <td key={column.key} className="text-ui leading-ui px-3 py-2 font-medium">
                    {row[columnIndex] ?? "—"}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <figcaption className="mt-2 text-metadata leading-metadata text-text-secondary">
        {block.dataset
          ? `Projected from approved dataset ${block.dataset.dataset_key} v${block.dataset.version} (sha256 ${block.dataset.content_sha256.slice(0, 12)}…).`
          : "Authored table published verbatim (numbers as exact decimal strings)."}
      </figcaption>
    </figure>
  );
}

function InsightBlock({ block }: { block: Extract<ShareBlockPayload, { block_type: "insight" }> }) {
  const contextLine = "chart_definition_version_id" in block.context
    ? `Chart evidence: definition ${block.context.chart_definition_version_id}, dataset ${block.context.dataset_version_id}, inspected ${formatUpdated(block.context.resolved_at)} UTC.`
    : `Model evidence: published run ${block.context.model_run_id} (specification ${block.context.specification_version}).`;
  return (
    <section className="mt-6 rounded-surface border border-border p-5" data-testid="share-insight">
      <p className="eyebrow">{block.insight_type} · {block.classification}</p>
      <div className="mt-2"><BodyContent body={block.body} /></div>
      <p className="mt-2 text-metadata leading-metadata text-text-secondary">{contextLine}</p>
    </section>
  );
}

function EvidenceBlock({ block }: { block: Extract<ShareBlockPayload, { block_type: "evidence" }> }) {
  const kind = block.target_kind === "insight" || block.target_kind === "chart_block"
    ? "in this revision"
    : block.target_kind === "model_run" ? "a published model run"
      : "a public citation artifact";
  return (
    <p className="mt-6 flex flex-wrap items-baseline gap-2 text-ui leading-ui text-text" data-testid="share-evidence">
      <span className={`rounded-full px-2 py-0.5 font-medium ${block.classification === "supporting" ? "bg-sage text-accent" : "bg-surface-muted text-text-secondary"}`}>
        {block.classification}
      </span>
      <span>
        Evidence referencing {kind}
        {block.target_ref ? <>: <code className="text-metadata">{block.target_ref.slice(0, 8)}…</code></> : null}
      </span>
    </p>
  );
}

function RiskBlock({ block }: { block: Extract<ShareBlockPayload, { block_type: "risk" }> }) {
  return (
    <section className="mt-6 rounded-surface border border-border border-s p-5" data-testid="share-risk">
      <p className="eyebrow">Counterargument</p>
      <h3 className="font-serif text-heading leading-heading mt-1">{block.title}</h3>
      <div className="mt-2"><BodyContent body={block.body} /></div>
    </section>
  );
}

function Block({ block }: { block: ShareBlockPayload }) {
  switch (block.block_type) {
    case "paragraph":
      return <p className={`${textUi} mt-4`}><RichRuns runs={block.runs} /></p>;
    case "heading": {
      const HeadingTag = block.level === 1 ? "h2" : block.level === 2 ? "h3" : "h4";
      return (
        <HeadingTag className="font-serif text-heading leading-heading mt-8">
          <RichRuns runs={block.runs} />
        </HeadingTag>
      );
    }
    case "bullet_list":
    case "ordered_list":
      return <div className="mt-4"><ListContent ordered={block.block_type === "ordered_list"} items={block.items} /></div>;
    case "liveChart":
      return <ChartBlock block={block} />;
    case "dataTable":
      return <DataTableBlock block={block} />;
    case "insight":
      return <InsightBlock block={block} />;
    case "hypothesis":
      return (
        <section className="mt-6 rounded-surface border border-border p-5" data-testid="share-hypothesis">
          <p className="eyebrow">Hypothesis · {block.assessment}</p>
          <p className={`${textUi} mt-2 font-medium`}>{block.statement}</p>
        </section>
      );
    case "evidence":
      return <EvidenceBlock block={block} />;
    case "risk":
      return <RiskBlock block={block} />;
    case "divider":
      return <hr className="mt-8 border-border" />;
  }
}

export function ShareViewer({ projection }: { projection: ShareProjectionPayload }) {
  const { document: meta } = projection;
  return (
    <article className="paper-panel p-8" data-testid="share-viewer">
      <p className="eyebrow">Shared research · read-only frozen revision</p>
      <h1 className="font-serif text-page leading-page mt-1 [overflow-wrap:anywhere]">{meta.title}</h1>
      <p className="mt-2 text-metadata leading-metadata text-text-secondary">
        Revision {meta.revision} · Content frozen on {formatUpdated(meta.created_at)} UTC ·
        Content hash {meta.content_sha256.slice(0, 12)}…
      </p>
      <div className="mt-6">
        {projection.blocks.map((block) => <Block key={block.block_id} block={block} />)}
      </div>
      {projection.sources.length > 0 || projection.model_runs.length > 0 || projection.citations.length > 0 ? (
        <section className="mt-10 border-t border-border pt-6" aria-label="Referenced registries"
          data-testid="share-registries">
          <h2 className="font-serif text-heading leading-heading">Referenced registries</h2>
          {projection.sources.length > 0 ? (
            <>
              <h3 className="font-ui text-ui font-medium mt-4">Data sources</h3>
              <ul className="mt-2 space-y-1">
                {projection.sources.map((source) => (
                  <li key={source.source_id} className={textUi}>
                    <code className="text-metadata">{source.source_id}</code> — {source.name}
                  </li>
                ))}
              </ul>
            </>
          ) : null}
          {projection.model_runs.length > 0 ? (
            <>
              <h3 className="font-ui text-ui font-medium mt-4">Published model runs</h3>
              <ul className="mt-2 space-y-1">
                {projection.model_runs.map((run) => (
                  <li key={run.run_id} className={textUi}>
                    Specification {run.spec_id} v{run.spec_version} — run{" "}
                    <code className="text-metadata">{run.run_id.slice(0, 8)}…</code>
                  </li>
                ))}
              </ul>
            </>
          ) : null}
          {projection.citations.length > 0 ? (
            <>
              <h3 className="font-ui text-ui font-medium mt-4">Cited artifacts</h3>
              <ul className="mt-2 space-y-1">
                {projection.citations.map((citation) => (
                  <li key={citation.artifact_id} className={textUi}>
                    Public artifact <code className="text-metadata">{citation.artifact_id.slice(0, 8)}…</code>
                  </li>
                ))}
              </ul>
            </>
          ) : null}
        </section>
      ) : null}
      <p className="mt-10 border-t border-border pt-4 text-metadata leading-metadata text-text-secondary">
        {meta.limitations}
      </p>
    </article>
  );
}
