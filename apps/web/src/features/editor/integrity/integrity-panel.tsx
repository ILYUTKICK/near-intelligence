"use client";

import { useEffect, useState, type KeyboardEvent } from "react";
import type { Editor } from "@tiptap/core";

import { Button } from "@/components/ui/button";
import { shortId } from "../blocks/display";
import { useChartEditorContext } from "../blocks/chart-context";
import { topLevelNodePosition } from "../commands";
import { fetchIntegrityReport, type IntegrityFinding, type IntegrityReport } from "./api";

/**
 * Advisory integrity findings panel (NI-065, ADR-021). The deterministic,
 * owner-checked report over the SAVED revision, shown next to the evidence
 * panel in the editor's tools pane: stale chart contexts (newer approved
 * data exists — refreshing stays the author's explicit action on the chart
 * block), drifted registry/target availability, corruption signals (missing
 * or invalid frozen contexts) and uncited pinned data.
 *
 * The panel is strictly read-only: no finding can rewrite the paper, a pin,
 * a coefficient or an insight context, and there is no truth score — every
 * entry carries its exact block/entity/dataset/definition references in
 * visible text, a jump-to-source action when the block is in the paper, and
 * an honest unavailable note when it is not.
 */

const CHECK_LABELS: Record<IntegrityFinding["check_id"], string> = {
  invalid_revision_content: "Revision content corrupted",
  missing_chart_context: "Missing frozen chart context",
  invalid_chart_context: "Invalid frozen chart context",
  stale_chart_context: "Newer approved data exists",
  chart_definition_unavailable: "Chart definition unavailable",
  dataset_pin_unavailable: "Dataset pin unavailable",
  evidence_target_unavailable: "Evidence target unavailable",
  insight_context_unavailable: "Insight context unavailable",
  uncited_pinned_chart: "Uncited pinned chart",
  uncited_pinned_dataset_table: "Uncited pinned dataset table",
};

const TARGET_KIND_LABELS: Record<NonNullable<IntegrityFinding["target_kind"]>, string> = {
  insight: "Insight in this research",
  chart_block: "Chart in this research",
  model_run: "Public model run",
  citation: "Public citation",
};

const SEVERITY_LABELS: Record<IntegrityFinding["severity"], string> = {
  advisory: "Advisory",
  warning: "Warning — inspect before editing",
};

function findingReferences(finding: IntegrityFinding): string {
  const parts: string[] = [];
  if (finding.block_id) parts.push(`Block ${shortId(finding.block_id)}`);
  if (finding.entity_id) parts.push(`Entity ${shortId(finding.entity_id)}`);
  if (finding.chart_definition_version_id) {
    parts.push(`Definition ${shortId(finding.chart_definition_version_id)}`);
  }
  if (finding.dataset_version_id) parts.push(`Dataset ${shortId(finding.dataset_version_id)}`);
  if (finding.latest_dataset_version_id) {
    parts.push(`Newest approved dataset ${shortId(finding.latest_dataset_version_id)}`);
  }
  if (finding.context_hash) parts.push(`Context hash ${shortId(finding.context_hash)}`);
  if (finding.target_kind) parts.push(TARGET_KIND_LABELS[finding.target_kind]);
  return parts.join(" · ");
}

function blockIndexByBlockId(editor: Editor, blockId: string): number | null {
  let index = 0;
  let found: number | null = null;
  editor.state.doc.forEach((block) => {
    if (block.attrs.block_id === blockId && found === null) {
      found = index;
    }
    index += 1;
  });
  return found;
}

export function IntegrityFindingsPanel({ editor, onAnnounce }: {
  editor: Editor;
  onAnnounce?: (message: string) => void;
}) {
  const account = useChartEditorContext();
  const [report, setReport] = useState<IntegrityReport | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  const ready = Boolean(account?.ready && account.signal && !account.signal.aborted);
  const revision = account?.revision;

  // The report describes the acknowledged revision and reruns when that
  // revision changes (after a save) or on the explicit Retry. State changes
  // happen only in async callbacks and the Retry handler. Unsaved edits are
  // not checked — stated honestly in the status line below.
  useEffect(() => {
    const signal = account?.signal;
    if (!account?.ready || !signal || signal.aborted || revision === undefined) {
      return;
    }
    const controller = new AbortController();
    const requestSignal = AbortSignal.any([signal, controller.signal]);
    fetchIntegrityReport(account.documentId, requestSignal).then((data) => {
      if (requestSignal.aborted) return;
      setReport(data);
      setError(null);
      setPending(false);
    }).catch(() => {
      if (requestSignal.aborted) return;
      setError("Integrity findings could not be loaded. Nothing was changed — try again.");
      setPending(false);
    });
    return () => controller.abort();
  }, [account?.ready, account?.documentId, account?.signal, revision, attempt]);

  function rerun() {
    setError(null);
    setPending(true);
    setAttempt((value) => value + 1);
  }

  function jumpToSource(finding: IntegrityFinding) {
    if (!finding.block_id || finding.jump !== "block") return;
    const index = blockIndexByBlockId(editor, finding.block_id);
    if (index === null) {
      onAnnounce?.("This block is not part of the current paper. The finding stays recorded above.");
      return;
    }
    const position = topLevelNodePosition(editor, index);
    // Direct commands (the evidence-panel pattern): the Tiptap `focus`
    // command defers via requestAnimationFrame, which would steal focus back
    // from the panel after the user moves on.
    editor.commands.setNodeSelection(position);
    editor.view.focus();
    try {
      const dom = editor.view.nodeDOM(position);
      if (dom instanceof HTMLElement && typeof dom.scrollIntoView === "function") {
        dom.scrollIntoView({ block: "nearest" });
      }
    } catch {
      // Geometry is unavailable in some environments; selection still moved.
    }
    onAnnounce?.(`Showing the block with the “${CHECK_LABELS[finding.check_id]}” finding in the paper.`);
  }

  function onPanelKeyDown(event: KeyboardEvent<HTMLElement>) {
    if (event.key === "Escape") {
      onAnnounce?.("Integrity findings stay advisory; the paper was not changed.");
    }
  }

  const findings = report?.findings ?? [];

  return (
    <section
      data-testid="integrity-panel"
      aria-label="Integrity findings"
      onKeyDown={onPanelKeyDown}
      className="mt-4 border-t border-border pt-3"
    >
      <p className="font-ui text-ui leading-ui font-medium text-text">Integrity findings</p>
      <p role="status" aria-live="polite" className="mt-1 text-metadata leading-metadata text-text-secondary">
        {ready ? (pending ? "Checking this revision…" : null) : "Findings are listed once the document session is verified."}
      </p>
      {error ? (
        <div className="mt-1">
          <p role="alert" className="text-metadata leading-metadata text-danger">{error}</p>
          <Button variant="quiet" onClick={rerun}>Retry integrity check</Button>
        </div>
      ) : null}
      {ready && !pending && !error && revision !== undefined ? (
        <p className="mt-1 text-metadata leading-metadata text-text-secondary" data-testid="integrity-revision">
          Checked saved revision {revision}
          {account?.saved ? "." : " — the paper has unsaved edits, so findings appear after the next save."}
        </p>
      ) : null}

      {ready && !pending && !error && findings.length === 0 ? (
        <p className="mt-2 text-metadata leading-metadata text-text-secondary" data-testid="integrity-empty">
          No integrity findings on this revision.
        </p>
      ) : null}

      {findings.length > 0 ? (
        <ul className="mt-2 flex flex-col gap-2" data-testid="integrity-findings">
          {findings.map((finding, index) => (
            <li key={`${finding.check_id}-${finding.block_id ?? "doc"}-${index}`}
              className={finding.severity === "warning"
                ? "rounded-control border border-danger/40 p-2" : "rounded-control border border-border p-2"}>
              <p className="text-metadata leading-metadata font-medium text-text">
                {SEVERITY_LABELS[finding.severity]} · {CHECK_LABELS[finding.check_id]}
              </p>
              <p className="mt-1 text-metadata leading-metadata text-text">{finding.message}</p>
              <p className="mt-1 break-all text-metadata leading-metadata text-text-secondary">
                {findingReferences(finding) || "Document-level finding"}
              </p>
              {finding.jump === "block" && finding.block_id ? (
                <Button variant="quiet" className="mt-1" onClick={() => jumpToSource(finding)}>
                  Show block {shortId(finding.block_id)} in the paper
                </Button>
              ) : null}
              {finding.check_id === "stale_chart_context" ? (
                <p className="mt-1 text-metadata leading-metadata text-text-secondary">
                  Refreshing is an explicit action on the chart block itself — this panel never changes the pin.
                </p>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
