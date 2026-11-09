import { Node, mergeAttributes } from "@tiptap/core";
import {
  NodeViewWrapper,
  ReactNodeViewRenderer,
  useEditorState,
  type NodeViewProps,
} from "@tiptap/react";

import { blockIdAttr, jsonAttr, stringAttr } from "../attributes";
import { emitOpenBlockProperties } from "../ui-bridge";
import type {
  CanonicalContext,
  CanonicalRiskBlock,
  Classification,
  EvidenceTargetKind,
  RichFragment,
} from "../canonical";
import { fieldPair, formatTimestamp, shortId } from "./display";
import { RichFragmentView } from "./rich-fragment";
import { Button } from "@/components/ui/button";
import { useChartEditorContext } from "./chart-context";
import { assessmentLabel } from "../hypotheses/assessment";
import { classificationLabels, targetKindLabels } from "../evidence/options";

/**
 * Canonical typed research annotation blocks (P0): `insight`, `hypothesis`,
 * `evidence` and `risk`. All four are atomic cards whose entity ids
 * (`insight_id`/`hypothesis_id`/`evidence_id`) are allocated once and persist
 * unchanged across text edits and reorders (NI-046), so outline anchors and
 * evidence links survive edits. Structured authoring/rest mutations of these
 * nodes arrive with NI-047/NI-048/NI-049 — the node views render the
 * persisted contract fields honestly and expose the shared structural
 * operations (select, move, duplicate, delete) through the block toolbar.
 */

const cardWrapperClass =
  "my-4 rounded-surface border border-control-border bg-surface p-4";

function EditPropertiesButton({ editor, getPos, blockId }: {
  editor: NodeViewProps["editor"];
  getPos: NodeViewProps["getPos"];
  blockId: string | null;
}) {
  if (!editor.isEditable) return null;
  return (
    <button
      type="button"
      className="mt-2 min-h-11 rounded-control border border-control-border bg-surface px-3 text-ui leading-ui text-text hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
      onClick={() => {
        const pos = typeof getPos === "function" ? getPos() : undefined;
        if (typeof pos === "number") {
          editor.commands.setNodeSelection(pos);
        }
        emitOpenBlockProperties(editor, blockId);
      }}
    >
      Edit properties
    </button>
  );
}

function selectionSummary(context: CanonicalContext | null): string {
  if (!context || !("selection" in context)) {
    return "—";
  }
  return `${context.selection.start} – ${context.selection.end} (UTC, half-open)`;
}

function ContextSummary({ context }: { context: CanonicalContext | null }) {
  if (!context) {
    return null;
  }
  return (
    <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-metadata leading-metadata text-text-secondary">
      {"chart_definition_version_id" in context ? (
        <>
          {fieldPair("Chart definition version", shortId(context.chart_definition_version_id), "ccd")}
          {fieldPair("Pinned dataset version", shortId(context.dataset_version_id), "cds")}
          {fieldPair("Selection window", selectionSummary(context), "csel")}
          {fieldPair("Renderer version", context.renderer_version, "crv")}
          {fieldPair("Resolved at", formatTimestamp(context.resolved_at), "cra")}
        </>
      ) : (
        <>
          {fieldPair("Model run", shortId(context.model_run_id), "cmr")}
          {fieldPair("Pinned dataset version", shortId(context.dataset_version_id), "cds")}
          {fieldPair("Specification version", context.specification_version, "csv")}
        </>
      )}
      {fieldPair("Context hash", shortId(context.context_hash), "chash")}
    </dl>
  );
}

// --------------------------------------------------------------------------- //
// insight
// --------------------------------------------------------------------------- //

export const Insight = Node.create({
  name: "insight",
  group: "block",
  atom: true,
  selectable: true,
  draggable: true,

  addAttributes() {
    return {
      block_id: blockIdAttr(),
      insight_id: stringAttr("insight_id"),
      type: stringAttr("type"),
      classification: stringAttr("classification"),
      body: jsonAttr("body"),
      context: jsonAttr("context"),
      authored_at: stringAttr("authored_at"),
      modified_at: stringAttr("modified_at"),
      hypothesis_id: stringAttr("hypothesis_id"),
    };
  },

  parseHTML() {
    return [{ tag: "div[data-insight-block]" }];
  },

  renderHTML({ HTMLAttributes }) {
    return ["div", mergeAttributes({ "data-insight-block": "" }, HTMLAttributes)];
  },

  addNodeView() {
    return ReactNodeViewRenderer(InsightBlockView);
  },
});

function InsightBlockView({ node, editor, getPos }: NodeViewProps) {
  const account = useChartEditorContext();
  const attrs = node.attrs as {
    block_id: string | null;
    insight_id: string | null;
    type: string | null;
    classification: string | null;
    body: RichFragment | null;
    context: CanonicalContext | null;
    authored_at: string | null;
    modified_at: string | null;
    hypothesis_id: string | null;
  };
  return (
    <NodeViewWrapper
      data-insight-block-view
      className={cardWrapperClass}
      aria-label="Insight block"
    >
      <div contentEditable={false} className="not-prose">
        <div className="flex flex-wrap items-center gap-2">
          <p className="font-ui text-ui leading-ui font-medium text-text">Insight</p>
          <span className="rounded-control border border-control-border px-1.5 py-0.5 text-metadata leading-metadata text-text-secondary">
            {attrs.type ?? "—"} · {attrs.classification ?? "—"}
          </span>
        </div>
        <div className="mt-2 text-body leading-body text-text">
          {attrs.body ? <RichFragmentView fragment={attrs.body} /> : null}
        </div>
        <p className="mt-2 font-ui text-ui leading-ui text-text-secondary">
          Pinned context: {selectionSummary(attrs.context)}
        </p>
        <ContextSummary context={attrs.context} />
        <p className="mt-2 text-metadata leading-metadata text-text-secondary">
          {attrs.hypothesis_id ? `Linked hypothesis: ${shortId(attrs.hypothesis_id)} · ` : ""}
          Authored {formatTimestamp(attrs.authored_at)} · Modified {formatTimestamp(attrs.modified_at)}
        </p>
        <div className="flex flex-wrap items-baseline gap-2">
          <EditPropertiesButton editor={editor} getPos={getPos} blockId={attrs.block_id} />
          {editor.isEditable && account?.onInsightAction && attrs.block_id ? <>
            <Button variant="quiet" disabled={!account.ready || !account.saved} onClick={() => {
              if (attrs.block_id) account.onInsightAction?.({ kind: "edit", blockId: attrs.block_id });
            }}>Edit insight</Button>
            <Button variant="quiet" disabled={!account.ready || !account.saved} onClick={() => {
              if (attrs.block_id) account.onInsightAction?.({ kind: "delete", blockId: attrs.block_id });
            }}>Delete insight</Button>
          </> : null}
        </div>
      </div>
    </NodeViewWrapper>
  );
}

// --------------------------------------------------------------------------- //
// hypothesis
// --------------------------------------------------------------------------- //

export const Hypothesis = Node.create({
  name: "hypothesis",
  group: "block",
  atom: true,
  selectable: true,
  draggable: true,

  addAttributes() {
    return {
      block_id: blockIdAttr(),
      hypothesis_id: stringAttr("hypothesis_id"),
      statement: stringAttr("statement"),
      assessment: stringAttr("assessment"),
      authored_at: stringAttr("authored_at"),
      modified_at: stringAttr("modified_at"),
    };
  },

  parseHTML() {
    return [{ tag: "div[data-hypothesis-block]" }];
  },

  renderHTML({ HTMLAttributes }) {
    return ["div", mergeAttributes({ "data-hypothesis-block": "" }, HTMLAttributes)];
  },

  addNodeView() {
    return ReactNodeViewRenderer(HypothesisBlockView);
  },
});

function HypothesisBlockView({ node, editor, getPos }: NodeViewProps) {
  const account = useChartEditorContext();
  const attrs = node.attrs as {
    block_id: string | null;
    hypothesis_id: string | null;
    statement: string | null;
    assessment: string | null;
    authored_at: string | null;
    modified_at: string | null;
  };
  const counts = useEditorState({ editor, selector: ({ editor }) => {
    const linked = { supporting: 0, contradicting: 0, uncertain: 0 };
    editor.state.doc.forEach(block => {
      const classification = block.attrs.classification as Classification;
      if (block.type.name === "evidence" && block.attrs.hypothesis_id === attrs.hypothesis_id && Object.hasOwn(linked, classification)) {
        linked[classification]++;
      }
    });
    return linked;
  } });
  const linkedEvidence = counts.supporting + counts.contradicting + counts.uncertain;
  const blockId = attrs.block_id;
  return (
    <NodeViewWrapper
      data-hypothesis-block-view
      className={cardWrapperClass}
      aria-label="Hypothesis block"
    >
      <div contentEditable={false} className="not-prose">
        <div className="flex flex-wrap items-center gap-2">
          <p className="font-ui text-ui leading-ui font-medium text-text">Hypothesis</p>
          <span className="rounded-control border border-control-border px-1.5 py-0.5 text-metadata leading-metadata text-text-secondary">
            Author assessment · {assessmentLabel(attrs.assessment)}
          </span>
        </div>
        <p className="mt-2 text-body leading-body text-text">{attrs.statement ?? ""}</p>
        <p className="mt-2 text-metadata leading-metadata text-text-secondary">
          Authored {formatTimestamp(attrs.authored_at)} · Modified {formatTimestamp(attrs.modified_at)}
        </p>
        <p className="mt-1 text-metadata leading-metadata text-text-secondary">
          {linkedEvidence} linked evidence {linkedEvidence === 1 ? "block" : "blocks"}
        </p>
        {linkedEvidence > 0 ? <p className="text-metadata leading-metadata text-text-secondary">
          Supporting {counts.supporting} · Contradicting {counts.contradicting} · Uncertain {counts.uncertain}
        </p> : null}
        <div className="flex flex-wrap items-baseline gap-2">
          <EditPropertiesButton editor={editor} getPos={getPos} blockId={blockId} />
          {editor.isEditable && account?.onHypothesisAction && blockId ? <>
            <Button variant="quiet" disabled={!account.ready || !account.saved}
              onClick={() => account.onHypothesisAction?.({ kind: "edit", blockId })}>Edit hypothesis</Button>
            <Button variant="quiet" disabled={!account.ready || !account.saved}
              onClick={() => account.onHypothesisAction?.({ kind: "delete", blockId })}>Delete hypothesis</Button>
          </> : null}
          {editor.isEditable && account?.onEvidenceAction && blockId ? <Button variant="quiet" disabled={!account.ready || !account.saved}
            onClick={() => account.onEvidenceAction?.({ kind: "create", blockId })}>Add evidence</Button> : null}
        </div>
      </div>
    </NodeViewWrapper>
  );
}

// --------------------------------------------------------------------------- //
// evidence
// --------------------------------------------------------------------------- //

export const Evidence = Node.create({
  name: "evidence",
  group: "block",
  atom: true,
  selectable: true,
  draggable: true,

  addAttributes() {
    return {
      block_id: blockIdAttr(),
      evidence_id: stringAttr("evidence_id"),
      hypothesis_id: stringAttr("hypothesis_id"),
      classification: stringAttr("classification"),
      target_kind: stringAttr("target_kind"),
      target_id: stringAttr("target_id"),
      explanation: stringAttr("explanation"),
    };
  },

  parseHTML() {
    return [{ tag: "div[data-evidence-block]" }];
  },

  renderHTML({ HTMLAttributes }) {
    return ["div", mergeAttributes({ "data-evidence-block": "" }, HTMLAttributes)];
  },

  addNodeView() {
    return ReactNodeViewRenderer(EvidenceBlockView);
  },
});

function EvidenceBlockView({ node, editor, getPos }: NodeViewProps) {
  const account = useChartEditorContext();
  const attrs = node.attrs as {
    block_id: string | null;
    evidence_id: string | null;
    hypothesis_id: string | null;
    classification: Classification | null;
    target_kind: EvidenceTargetKind | null;
    target_id: string | null;
    explanation: string | null;
  };
  const blockId = attrs.block_id;
  const targetLabel = attrs.target_kind ? targetKindLabels[attrs.target_kind] : "—";
  return (
    <NodeViewWrapper
      data-evidence-block-view
      className={cardWrapperClass}
      aria-label="Evidence block"
    >
      <div contentEditable={false} className="not-prose">
        <div className="flex flex-wrap items-center gap-2">
          <p className="font-ui text-ui leading-ui font-medium text-text">Evidence</p>
          <span className="rounded-control border border-control-border px-1.5 py-0.5 text-metadata leading-metadata text-text-secondary">
            {attrs.classification ? classificationLabels[attrs.classification] : "—"} · {targetLabel}
          </span>
        </div>
        <p className="mt-2 text-body leading-body text-text">{attrs.explanation ?? ""}</p>
        <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-metadata leading-metadata text-text-secondary">
          {fieldPair("Hypothesis", shortId(attrs.hypothesis_id), "eh")}
          {fieldPair("Target ID", shortId(attrs.target_id), "et")}
        </dl>
        <div className="flex flex-wrap items-baseline gap-2">
          <EditPropertiesButton editor={editor} getPos={getPos} blockId={blockId} />
          {editor.isEditable && account?.onEvidenceAction && blockId ? <>
            <Button variant="quiet" disabled={!account.ready || !account.saved}
              onClick={() => account.onEvidenceAction?.({ kind: "edit", blockId })}>Edit evidence link</Button>
            <Button variant="quiet" disabled={!account.ready || !account.saved}
              onClick={() => account.onEvidenceAction?.({ kind: "delete", blockId })}>Delete evidence link</Button>
          </> : null}
        </div>
      </div>
    </NodeViewWrapper>
  );
}

// --------------------------------------------------------------------------- //
// risk
// --------------------------------------------------------------------------- //

export const Risk = Node.create({
  name: "risk",
  group: "block",
  atom: true,
  selectable: true,
  draggable: true,

  addAttributes() {
    return {
      block_id: blockIdAttr(),
      title: stringAttr("title"),
      body: jsonAttr("body"),
      related_hypothesis_id: stringAttr("related_hypothesis_id"),
    };
  },

  parseHTML() {
    return [{ tag: "div[data-risk-block]" }];
  },

  renderHTML({ HTMLAttributes }) {
    return ["div", mergeAttributes({ "data-risk-block": "" }, HTMLAttributes)];
  },

  addNodeView() {
    return ReactNodeViewRenderer(RiskBlockView);
  },
});

function RiskBlockView({ node, updateAttributes, editor, getPos }: NodeViewProps) {
  const attrs = node.attrs as {
    block_id: string | null;
    title: string | null;
    body: RichFragment | null;
    related_hypothesis_id: string | null;
  };
  return (
    <NodeViewWrapper
      data-risk-block-view
      className={`${cardWrapperClass} border-danger/40`}
      aria-label="Risk block"
    >
      <div contentEditable={false} className="not-prose">
        <p className="font-ui text-ui leading-ui font-medium text-text">Risk</p>
        {/* Title editing follows the NI-038 nested-input pattern: an island
            inside the atomic node, controlled by updateAttributes so the
            canonical attr stays the single source. */}
        {editor.isEditable ? <input
          aria-label="Risk title"
          value={attrs.title ?? ""}
          onChange={(event) => updateAttributes({ title: event.target.value })}
          className="mt-2 w-full rounded-control border border-control-border bg-surface px-2 py-1 font-ui text-ui leading-ui text-text focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
        /> : <p>{attrs.title}</p>}
        <div className="mt-2 text-body leading-body text-text">
          {attrs.body ? <RichFragmentView fragment={attrs.body} /> : null}
        </div>
        <p className="mt-2 text-metadata leading-metadata text-text-secondary">
          {attrs.related_hypothesis_id ? `Related hypothesis: ${shortId(attrs.related_hypothesis_id)}` : "No related hypothesis"}
        </p>
        {editor.isEditable ? <p className="mt-1 text-metadata leading-metadata text-text-secondary italic">
          Risk body rich-text editing arrives with the annotation tasks; the title, block and its
          structural operations are active now.
        </p> : null}
        <EditPropertiesButton editor={editor} getPos={getPos} blockId={attrs.block_id} />
      </div>
    </NodeViewWrapper>
  );
}

/** Exported for the properties panel (type only; no behavior duplication). */
export type RiskBlockAttrs = CanonicalRiskBlock["attrs"];
