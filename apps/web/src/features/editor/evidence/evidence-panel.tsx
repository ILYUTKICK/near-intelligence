"use client";

import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import type { Editor } from "@tiptap/core";
import { useEditorState } from "@tiptap/react";

import { Button } from "@/components/ui/button";
import { shortId } from "../blocks/display";
import { useChartEditorContext } from "../blocks/chart-context";
import { topLevelNodePosition } from "../commands";
import { assessmentLabel } from "../hypotheses/assessment";
import { classificationLabels, targetKindLabels } from "./options";
import { listDocumentEvidence, type EvidenceLink } from "./api";

/**
 * Evidence navigation and research context panel (NI-050). The read-only
 * "connected argument" view for the editor's tools pane: per-hypothesis
 * evidence lists with counts by classification (from the owner-checked
 * GET /api/documents/{document_id}/evidence surface, NI-049), contradicting
 * evidence and related risk blocks surfaced alongside the hypothesis, and
 * click-through navigation evidence entry → target block in the paper →
 * (for charts) the block's own pinned-context/source controls → back, with
 * keyboard focus restored to the originating evidence entry.
 *
 * Navigation is strictly read-only: it moves the ProseMirror selection and
 * never rewrites block attributes, insight contexts or saved pins — the
 * paper's document is unchanged by every interaction in this panel.
 * Classification is the author's editorial interpretation (NI-046/NI-049),
 * never a statistical confidence claim; missing evidence shows explicit
 * empty states and is never fabricated.
 */

interface PanelHypothesis {
  hypothesisId: string;
  blockId: string;
  statement: string;
  assessment: string | null;
}

interface PanelRisk {
  blockId: string;
  title: string;
  relatedHypothesisId: string | null;
}

/** Editor-derived, selection-independent argument structure (deep-compared). */
function selectArgumentState(editor: Editor) {
  const hypotheses: PanelHypothesis[] = [];
  const risks: PanelRisk[] = [];
  editor.state.doc.forEach((block) => {
    if (block.type.name === "hypothesis") {
      hypotheses.push({
        hypothesisId: String(block.attrs.hypothesis_id ?? ""),
        blockId: String(block.attrs.block_id ?? ""),
        statement: String(block.attrs.statement ?? ""),
        assessment: (block.attrs.assessment as string | null) ?? null,
      });
    } else if (block.type.name === "risk") {
      risks.push({
        blockId: String(block.attrs.block_id ?? ""),
        title: String(block.attrs.title ?? ""),
        relatedHypothesisId: (block.attrs.related_hypothesis_id as string | null) ?? null,
      });
    }
  });
  return { hypotheses, risks };
}

/**
 * The top-level block an evidence target points at: `chart_block` targets
 * reference the chart's block_id, `insight` targets the insight entity id.
 * Public model/citation artifacts are not blocks of this paper.
 */
function evidenceTargetIndex(editor: Editor, entry: EvidenceLink): number | null {
  let index = 0;
  let found: number | null = null;
  editor.state.doc.forEach((block) => {
    const matches =
      (entry.target_kind === "chart_block" && block.type.name === "liveChart" && block.attrs.block_id === entry.target_id) ||
      (entry.target_kind === "insight" && block.type.name === "insight" && block.attrs.insight_id === entry.target_id);
    if (matches && found === null) {
      found = index;
    }
    index += 1;
  });
  return found;
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

type Origin = { kind: "evidence"; id: string } | { kind: "risk"; id: string };

const EMPTY_COUNTS = { supporting: 0, contradicting: 0, uncertain: 0 } as const;

export function EvidenceNavigationPanel({ editor, onAnnounce }: {
  editor: Editor;
  onAnnounce?: (message: string) => void;
}) {
  const account = useChartEditorContext();
  const { hypotheses, risks } = useEditorState({ editor, selector: ({ editor: current }) => selectArgumentState(current) });
  const [links, setLinks] = useState<EvidenceLink[] | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [origin, setOrigin] = useState<Origin | null>(null);
  const entryRefs = useRef(new Map<string, HTMLButtonElement | null>());

  const ready = Boolean(account?.ready && account.signal && !account.signal.aborted);
  const revision = account?.revision;

  // The list is the owner-checked server view of the current revision; it
  // refetches when the acknowledged revision changes (after a save or an
  // adopted annotation mutation) or after the explicit Retry. State changes
  // happen only in async callbacks and the Retry handler — never synchronously
  // in the effect body (no cascading renders). While local edits are unsaved
  // the paper may hold links the server has not acknowledged yet — stated
  // honestly in the status line below.
  useEffect(() => {
    const signal = account?.signal;
    if (!account?.ready || !signal || signal.aborted || revision === undefined) {
      return;
    }
    const controller = new AbortController();
    const requestSignal = AbortSignal.any([signal, controller.signal]);
    listDocumentEvidence(account.documentId, requestSignal).then((data) => {
      if (requestSignal.aborted) return;
      setLinks(data);
      setError(null);
      setPending(false);
    }).catch(() => {
      if (requestSignal.aborted) return;
      setError("Linked evidence could not be loaded. Nothing was changed — try again.");
      setPending(false);
    });
    return () => controller.abort();
  }, [account?.ready, account?.documentId, account?.signal, revision, attempt]);

  function retryEvidence() {
    setError(null);
    setPending(true);
    setAttempt((value) => value + 1);
  }

  function navigateToBlock(index: number, label: string) {
    const position = topLevelNodePosition(editor, index);
    // Direct commands (the live-chart Escape pattern): the Tiptap `focus`
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
    onAnnounce?.(`Showing the ${label} in the paper. Use “Back to the evidence list” to return.`);
  }

  function showEvidence(entry: EvidenceLink) {
    if (entry.target_kind !== "insight" && entry.target_kind !== "chart_block") {
      onAnnounce?.(`This evidence targets a public ${targetKindLabels[entry.target_kind].toLowerCase()} outside the paper.`);
      return;
    }
    const index = evidenceTargetIndex(editor, entry);
    if (index === null) {
      onAnnounce?.("The linked target is not part of the current paper.");
      return;
    }
    setOrigin({ kind: "evidence", id: entry.id });
    navigateToBlock(index, entry.target_kind === "insight" ? "insight" : "chart");
  }

  function showRisk(risk: PanelRisk) {
    const index = blockIndexByBlockId(editor, risk.blockId);
    if (index === null) return;
    setOrigin({ kind: "risk", id: risk.blockId });
    navigateToBlock(index, "risk");
  }

  function returnToOrigin() {
    if (!origin) return;
    const ref = origin.kind === "evidence"
      ? entryRefs.current.get(origin.id)
      : entryRefs.current.get(`risk:${origin.id}`);
    if (ref && ref.isConnected) {
      ref.focus();
    }
    setOrigin(null);
    onAnnounce?.("Returned to the evidence list.");
  }

  function onPanelKeyDown(event: KeyboardEvent<HTMLElement>) {
    if (event.key === "Escape" && origin) {
      event.preventDefault();
      event.stopPropagation();
      returnToOrigin();
    }
  }

  const knownHypotheses = new Set(hypotheses.map((hypothesis) => hypothesis.hypothesisId));
  const orphanLinks = (links ?? []).filter((link) => !knownHypotheses.has(link.hypothesis_id));

  return (
    <section
      data-testid="evidence-navigation-panel"
      aria-label="Evidence and arguments"
      onKeyDown={onPanelKeyDown}
      className="mt-4 border-t border-border pt-3"
    >
      <p className="font-ui text-ui leading-ui font-medium text-text">Evidence and arguments</p>
      {!ready && hypotheses.length > 0 ? (
        <p role="status" className="mt-1 text-metadata leading-metadata text-text-secondary">
          Linked evidence is listed once the document session is verified.
        </p>
      ) : null}
      {ready && pending ? <p role="status" className="mt-1 text-metadata leading-metadata text-text-secondary">Loading linked evidence…</p> : null}
      {error ? (
        <div className="mt-1">
          <p role="alert" className="text-metadata leading-metadata text-danger">{error}</p>
          <Button variant="quiet" onClick={retryEvidence}>Retry evidence list</Button>
        </div>
      ) : null}
      {ready && !pending && !error && revision !== undefined ? (
        <p className="mt-1 text-metadata leading-metadata text-text-secondary">
          Linked evidence from saved revision {revision}
          {account?.saved ? "." : " — the paper has unsaved edits, so newly linked evidence appears after the next save."}
        </p>
      ) : null}

      {hypotheses.length === 0 ? (
        <p className="mt-2 text-metadata leading-metadata text-text-secondary">
          No hypotheses in this research yet. Add a hypothesis to connect supporting and
          contradicting evidence, insights and risks in one view.
        </p>
      ) : null}
      {hypotheses.length === 0 && ready && (links === null || links.length === 0) && !pending && !error ? (
        <p className="text-metadata leading-metadata text-text-secondary">
          No evidence links are recorded for this research.
        </p>
      ) : null}

      {hypotheses.map((hypothesis) => {
        const entries = (links ?? []).filter((link) => link.hypothesis_id === hypothesis.hypothesisId);
        const counts = { ...EMPTY_COUNTS };
        for (const entry of entries) {
          if (Object.hasOwn(counts, entry.classification)) {
            counts[entry.classification] += 1;
          }
        }
        const total = entries.length;
        const relatedRisks = risks.filter((risk) => risk.relatedHypothesisId === hypothesis.hypothesisId);
        return (
          <article key={hypothesis.hypothesisId || hypothesis.blockId} aria-label={`Evidence for hypothesis: ${hypothesis.statement}`}
            className="mt-3 rounded-control border border-border p-2">
            <p className="text-ui leading-ui text-text">{hypothesis.statement}</p>
            <p className="mt-1 text-metadata leading-metadata text-text-secondary">
              Author assessment · {assessmentLabel(hypothesis.assessment)}
            </p>
            <p className="mt-1 text-metadata leading-metadata text-text-secondary" data-testid="evidence-counts">
              {total === 0 ? "No linked evidence yet — " : ""}
              Supporting {counts.supporting} · Contradicting {counts.contradicting} · Uncertain {counts.uncertain}
            </p>
            {total === 0 ? (
              <p className="text-metadata leading-metadata text-text-secondary">
                Use “Add evidence” on the hypothesis card to link the first target.
              </p>
            ) : (
              <ul className="mt-2 flex flex-col gap-2">
                {entries.map((entry) => {
                  const targetLabel = targetKindLabels[entry.target_kind];
                  const targetIndex = entry.target_kind === "insight" || entry.target_kind === "chart_block"
                    ? evidenceTargetIndex(editor, entry)
                    : null;
                  return (
                    <li key={entry.id}
                      className={entry.classification === "contradicting" ? "rounded-control border border-danger/40 p-2" : ""}>
                      <button
                        type="button"
                        ref={(node) => { entryRefs.current.set(entry.id, node); }}
                        data-testid="evidence-entry"
                        className="w-full rounded-control text-left text-metadata leading-metadata text-text hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
                        aria-label={`Show ${classificationLabels[entry.classification].toLowerCase()} evidence in the paper (${targetLabel})`}
                        onClick={() => showEvidence(entry)}
                      >
                        <span className="font-medium">
                          {classificationLabels[entry.classification]} · {targetLabel} · {shortId(entry.target_id)}
                        </span>
                        <span className="block">{entry.explanation}</span>
                      </button>
                      {targetIndex === null
                        ? <p className="text-metadata leading-metadata text-text-secondary">
                            {entry.target_kind === "insight" || entry.target_kind === "chart_block"
                              ? "The linked target is not part of the current paper."
                              : "Public artifact — inspected outside this paper; its id stays pinned on the link."}
                          </p>
                        : null}
                    </li>
                  );
                })}
              </ul>
            )}
            <p className="mt-2 text-metadata leading-metadata font-medium text-text">Counterarguments</p>
            {counts.contradicting === 0 ? (
              <p className="text-metadata leading-metadata text-text-secondary">
                No contradicting evidence is linked to this hypothesis.
              </p>
            ) : (
              <p className="text-metadata leading-metadata text-text-secondary">
                {counts.contradicting} contradicting {counts.contradicting === 1 ? "entry above records" : "entries above record"} the
                authors&apos; counterargument; the classification is editorial, not a statistical confidence claim.
              </p>
            )}
            <p className="mt-2 text-metadata leading-metadata font-medium text-text">Related risks</p>
            {relatedRisks.length === 0 ? (
              <p className="text-metadata leading-metadata text-text-secondary">No risk blocks reference this hypothesis.</p>
            ) : (
              <ul className="mt-1 flex flex-col gap-1">
                {relatedRisks.map((risk) => (
                  <li key={risk.blockId}>
                    <button
                      type="button"
                      ref={(node) => { entryRefs.current.set(`risk:${risk.blockId}`, node); }}
                      className="w-full rounded-control text-left text-metadata leading-metadata text-text hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
                      aria-label={`Show risk ${risk.title} in the paper`}
                      onClick={() => showRisk(risk)}
                    >
                      Risk · {risk.title}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </article>
        );
      })}

      {orphanLinks.length > 0 ? (
        <div className="mt-3" role="note">
          <p className="text-metadata leading-metadata text-text-secondary">
            {orphanLinks.length} evidence {orphanLinks.length === 1 ? "link" : "links"} reference a hypothesis that is
            not in the current paper. Nothing was changed.
          </p>
          <ul className="mt-1 flex flex-col gap-1">
            {orphanLinks.map((entry) => (
              <li key={entry.id} className="text-metadata leading-metadata text-text-secondary">
                {classificationLabels[entry.classification]} · {targetKindLabels[entry.target_kind]} · {shortId(entry.target_id)} — {entry.explanation}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {origin ? (
        <Button variant="secondary" className="mt-3" onClick={returnToOrigin}
          data-testid="evidence-return">
          Back to the evidence list
        </Button>
      ) : null}
    </section>
  );
}
