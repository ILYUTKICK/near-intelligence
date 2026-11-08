import { Component, useCallback, useContext, useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { ChartView, type ChartSelection, type ChartViewResponse } from "@/features/charts/renderer/ChartView";
import { filterEnumOptions, filterLabel } from "@/features/charts/library/filter-controls";
import { isIsoCalendarDate, windowDays } from "@/features/charts/library/selection-url";
import { HistoricalRevisionContext, useChartEditorContext } from "./chart-context";
import { loadDocumentChart, type DocumentChartView } from "./chart-api";
import { HistoricalChart } from "./historical-chart";
import { Node, mergeAttributes } from "@tiptap/core";
import {
  NodeViewWrapper,
  ReactNodeViewRenderer,
  type NodeViewProps,
} from "@tiptap/react";

import { blockIdAttr, jsonAttr, stringAttr } from "../attributes";
import { emitOpenBlockProperties } from "../ui-bridge";


/**
 * Canonical `liveChart` block (P0, EDITOR_SPECIFICATION): chart reference +
 * mode + selection + observed dataset pin. The block is atomic — it is
 * selected, moved, duplicated and deleted as one unit, and its context pins
 * travel with it. NI-042 reuses ChartView and commits inspected selection
 * changes only after successful canonical resolution.
 */
export const LiveChart = Node.create({
  name: "liveChart",
  group: "block",
  atom: true,
  selectable: true,
  draggable: true,

  addAttributes() {
    return {
      block_id: blockIdAttr(),
      chart_definition_version_id: stringAttr("chart_definition_version_id"),
      mode: stringAttr("mode"),
      selection: jsonAttr("selection"),
      observed_dataset_version_id: stringAttr("observed_dataset_version_id"),
      snapshot_id: stringAttr("snapshot_id"),
    };
  },

  parseHTML() {
    return [{ tag: "div[data-live-chart]" }];
  },

  renderHTML({ HTMLAttributes }) {
    return ["div", mergeAttributes({ "data-live-chart": "" }, HTMLAttributes)];
  },

  addNodeView() {
    return ReactNodeViewRenderer(LiveChartBlockView);
  },
});

function LiveChartBlockView({ node, editor, getPos, updateAttributes }: NodeViewProps) {
  const attrs = node.attrs as ChartBlockAttrs;
  const context = useChartEditorContext();
  const historical = useContext(HistoricalRevisionContext);
  if (historical) return <NodeViewWrapper className="not-prose my-4 min-w-0" aria-label="Saved chart block">
    {attrs.block_id ? <HistoricalChart {...historical} blockId={attrs.block_id} />
      : <p role="alert">Chart reconstruction failed. This saved block has no identity.</p>}
  </NodeViewWrapper>;
  return <NodeViewWrapper data-live-chart-block className="my-4 min-w-0 max-w-full" aria-label="Live chart block">
    <div contentEditable={false} className="not-prose min-w-0" onKeyDown={(event) => {
      if (event.key === "Escape" && !event.defaultPrevented && !(event.target as HTMLElement).closest('[role="dialog"]')) {
        event.preventDefault(); event.stopPropagation();
        const pos = getPos();
        if (typeof pos === "number") { editor.commands.setNodeSelection(pos); editor.view.focus(); }
      }
    }}>
      {context ? <InteractiveChart attrs={attrs} context={context} onApply={updateAttributes} /> : <p>Chart controls require an owned research document.</p>}
      <button type="button" className={CONTROL_CLASS} onClick={() => {
        const pos = getPos();
        if (typeof pos === "number") editor.commands.setNodeSelection(pos);
        emitOpenBlockProperties(editor, attrs.block_id);
      }}>Edit properties</button>
    </div>
  </NodeViewWrapper>;
}

export interface ChartBlockAttrs {
  block_id: string | null;
  chart_definition_version_id: string;
  mode: string;
  selection: ChartSelection;
  observed_dataset_version_id: string;
}
const CONTROL_CLASS = "min-h-11 max-w-full rounded-control border border-control-border bg-surface px-3 py-2 font-ui text-base sm:text-ui touch-manipulation leading-ui text-text hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus disabled:opacity-60 aria-disabled:opacity-60";
export function inspectionKey(definitionId: string, selection: ChartSelection | ChartViewResponse["selection"], datasetId: string) {
  return JSON.stringify([definitionId, selection.start, selection.end, Object.entries(selection.filters ?? {}).sort(), datasetId]);
}
type Context = NonNullable<ReturnType<typeof useChartEditorContext>>;

/** The renderer may fail independently of the enclosing text editor. */
class ChartBoundary extends Component<{ children: ReactNode; resetKey: string }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidUpdate(previous: { resetKey: string }) {
    if (previous.resetKey !== this.props.resetKey && this.state.failed) this.setState({ failed: false });
  }
  render() { return this.state.failed ? <p role="alert">This chart could not render. Prose editing remains available. Retry loading the chart.</p> : this.props.children; }
}

export function InteractiveChart({ attrs, context, onApply }: {
  attrs: ChartBlockAttrs; context: Context; onApply: (attrs: Record<string, unknown>) => void;
}) {
  const [loaded, setLoaded] = useState<{ key: string; view: DocumentChartView; order: number } | null>(null);
  const [candidate, setCandidate] = useState<{ key: string; view: DocumentChartView; attempt: number; order: number; signal: AbortSignal; subject: string | null; documentId: string } | null>(null);
  const applied = useRef<{ candidate: object; revision: number | undefined } | null>(null);
  const checkedAfterSave = useRef<object | null>(null);
  const [openedDataset] = useState(attrs.observed_dataset_version_id);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState<ChartSelection | null>(null);
  const [retry, setRetry] = useState(0);
  const request = useRef<AbortController | null>(null);
  const generation = useRef(0);
  const readOrder = useRef(0);
  const acceptView = useCallback((key: string, view: DocumentChartView, order: number) => {
    setLoaded(current => current && current.order > order ? current : { key, view, order });
  }, []);
  const attrsKey = inspectionKey(attrs.chart_definition_version_id, attrs.selection, attrs.observed_dataset_version_id);
  const currentKey = useRef(attrsKey);
  const readyRef = useRef(context.ready);
  // Updated at effect time before any later browser event can commit a response.
  useLayoutEffect(() => { currentKey.current = attrsKey; readyRef.current = context.ready; }, [attrsKey, context.ready]);
  // Async responses propose an edit; commit only after React reconciles current
  // props/identity. A batched auth change or Undo wins over a late response.
  useLayoutEffect(() => {
    if (!candidate || applied.current?.candidate === candidate || !context.ready || candidate.signal.aborted
      || candidate.key !== attrsKey || candidate.attempt !== generation.current
      || candidate.subject !== context.subject || candidate.documentId !== context.documentId) return;
    const { definition, dataset, selection, context_hash, resolved_at } = candidate.view;
    const nextKey = inspectionKey(definition.id, selection, dataset.id);
    applied.current = { candidate, revision: context.revision };
    if (nextKey === attrsKey) return;
    if (attrs.block_id) context.onObserve?.(attrs.block_id, {
      chart_definition_version_id: definition.id, dataset_version_id: dataset.id,
      selection, context_hash, resolved_at, renderer_version: definition.renderer_version,
      metric_definition_versions: definition.metric_definition_ids,
    });
    onApply({ selection, observed_dataset_version_id: dataset.id });
  }, [candidate, attrsKey, attrs.block_id, context, onApply]);
  const candidateMatchesNode = candidate && candidate.subject === context.subject && candidate.documentId === context.documentId
    && inspectionKey(candidate.view.definition.id, candidate.view.selection, candidate.view.dataset.id) === attrsKey;
  const view = loaded?.key === attrsKey && (!candidateMatchesNode || loaded.order > candidate.order)
    ? loaded.view : candidateMatchesNode ? candidate.view : null;

  const resolve = useCallback(async (selection: ChartSelection, dataset: string, commit: boolean) => {
    request.current?.abort();
    const controller = new AbortController(); request.current = controller;
    const attempt = ++generation.current;
    const order = ++readOrder.current;
    const inspectedKey = attrsKey;
    setLoading(true); setError(null);
    try {
      const next = await loadDocumentChart(context.documentId, attrs.chart_definition_version_id, selection, dataset, controller.signal);
      if (controller.signal.aborted || attempt !== generation.current || currentKey.current !== inspectedKey || !readyRef.current) return;
      const nextKey = inspectionKey(next.definition.id, next.selection, next.dataset.id);
      // A prospective edit stays separate until attrs reconcile, so the old
      // matching renderer/controls stay mounted and keyboard focus is retained.
      if (!commit) acceptView(nextKey, next, order);
      setLoading(false);
      if (commit) {
        // Only a successful canonical resolution becomes a single undoable document edit.
        setDraft(null);
        setCandidate({ key: inspectedKey, view: next, attempt, order, signal: controller.signal, subject: context.subject, documentId: context.documentId });
      }
    } catch (cause) {
      if (!controller.signal.aborted && attempt === generation.current) {
        setLoading(false); setError(cause instanceof Error ? cause.message : "Chart unavailable. Prose editing remains available.");
      }
    }
  }, [acceptView, attrsKey, attrs.chart_definition_version_id, context.documentId, context.subject]);

  useEffect(() => {
    if (!context.ready || attrs.mode !== "live") { request.current?.abort(); return; }
    const timer = setTimeout(() => void resolve(attrs.selection, attrs.observed_dataset_version_id, false), 0);
    return () => { clearTimeout(timer); request.current?.abort(); };
  }, [resolve, attrs.selection, attrs.observed_dataset_version_id, context.ready, context.subject, retry, attrs.mode]);

  // Recheck once after an inspected edit is acknowledged. A publication
  // between inspection and save only changes the working-view notice.
  useEffect(() => {
    if (!candidateMatchesNode || checkedAfterSave.current === candidate || !context.ready || !context.saved
      || applied.current?.candidate !== candidate || applied.current?.revision === context.revision) return;
    const controller = new AbortController();
    const order = ++readOrder.current;
    void loadDocumentChart(context.documentId, attrs.chart_definition_version_id, attrs.selection,
      attrs.observed_dataset_version_id, controller.signal).then(next => {
      if (!controller.signal.aborted) {
        checkedAfterSave.current = candidate;
        acceptView(attrsKey, next, order);
      }
    }).catch(() => { /* The inspected pin remains visible if the status check fails. */ });
    return () => controller.abort();
  }, [acceptView, candidate, candidateMatchesNode, context.documentId, context.ready, context.saved, context.revision,
    attrsKey, attrs.chart_definition_version_id, attrs.selection, attrs.observed_dataset_version_id]);
  const selection = draft ?? attrs.selection;
  const definition = view?.definition;
  const properties = definition?.filter_schema["properties"];
  const filterKeys = properties && typeof properties === "object" && !Array.isArray(properties) ? Object.keys(properties).sort() : [];
  const enabled = context.ready && attrs.mode === "live";
  const draftRangeError = definition && (!isIsoCalendarDate(selection.start) || !isIsoCalendarDate(selection.end)
    || windowDays(selection.start, selection.end) < 1 || windowDays(selection.start, selection.end) > definition.available_ranges.max_days);

  return <section className="min-w-0 space-y-3" aria-label="Embedded chart controls">
    <div className="flex flex-wrap gap-2 text-metadata leading-metadata">
      <span>{attrs.mode === "live" ? "Live chart · saved observation" : "Snapshot chart · reconstruction unavailable"}</span>
      <span role="status">{context.saved ? "Saved in document revision" : "Changed — document has unsaved edits"}</span>
      {openedDataset !== attrs.observed_dataset_version_id ? <span>Changed dataset — explicit observation edit</span> : null}
      {context.ready && view?.latest_approved_dataset_version_id && view.latest_approved_dataset_version_id !== view.dataset.id
        ? <span role="status">Newer approved data available</span> : null}
    </div>
    <p className="break-all text-metadata leading-metadata text-text-secondary">Observed dataset: {attrs.observed_dataset_version_id}. Opening or typing never refreshes this pin.</p>
    {!context.ready ? <p role="status">Chart controls are suspended while your document account is checked. Reopen the document after an account change.</p> : null}
    {attrs.mode !== "live" ? <p role="alert">Snapshot reconstruction requires snapshot storage; this block is retained without resolving latest.</p> : null}
    {loading && context.ready ? <p role="status">Loading chart context… {view ? "Showing the last loaded values." : ""}</p> : null}
    {error ? <p role="alert">{error} {view ? "Showing the last successfully loaded context." : ""}</p> : null}
    <div className="flex flex-wrap gap-2">
      <button type="button" className={CONTROL_CLASS} disabled={!context.ready || attrs.mode !== "live"} onClick={() => setRetry(value => value + 1)}>Retry chart</button>
      <button type="button" className={CONTROL_CLASS} disabled={!enabled} onClick={() => void resolve(attrs.selection, "latest", true)}>Refresh to latest and save observation</button>
      <button type="button" className={CONTROL_CLASS} disabled aria-describedby={`insight-gate-${attrs.block_id}`}>Add Insight</button>
    </div>
    <p id={`insight-gate-${attrs.block_id}`} className="text-metadata text-text-secondary">Add Insight is unavailable until insight authoring can preserve the chart context.</p>
    {view && context.ready ? <>
      <ChartBoundary resetKey={`${attrsKey}:${retry}`}>
        <ChartView definition={view.definition} view={view} mode="historical" selection={attrs.selection}
          className="min-w-0 p-3 sm:p-6" onSelectionChange={enabled ? (next) => void resolve({ ...next, filters: attrs.selection.filters }, attrs.observed_dataset_version_id, true) : undefined} />
      </ChartBoundary>
      <details className="rounded-control border border-border p-3"><summary className="min-h-11 cursor-pointer text-ui">Chart definition and pinned context</summary>
        <p>{definition?.title} · version {definition?.version}</p><p>{definition?.description}</p>
        <p className="break-all">Definition: {definition?.id}</p><p className="break-all">Renderer: {definition?.renderer_version}</p>
        <p className="break-all">Displayed dataset: {view.dataset.id}</p><p className="break-all">Context hash: {view.context_hash}</p>
      </details>
      <fieldset disabled={!enabled} className="min-w-0 space-y-3"><legend className="text-ui">Edit chart range and filters</legend>
        <p className="text-metadata text-text-secondary">UTC [start, end); maximum {definition?.available_ranges.max_days} days. Apply explicitly changes the document. Filters and range use the current observed dataset.</p>
        <div className="flex flex-wrap gap-3">
          <label className="flex min-w-0 flex-col gap-1 text-ui">Start date<input className={CONTROL_CLASS} type="date" value={selection.start} onChange={event => setDraft({ ...selection, start: event.target.value })} /></label>
          <label className="flex min-w-0 flex-col gap-1 text-ui">End date (exclusive)<input className={CONTROL_CLASS} type="date" value={selection.end} onChange={event => setDraft({ ...selection, end: event.target.value })} /></label>
          {filterKeys.map(key => <label key={key} className="flex min-w-0 flex-col gap-1 text-ui">{filterLabel(key)}<select className={CONTROL_CLASS} value={selection.filters?.[key] ?? ""} onChange={event => {
            const filters = { ...selection.filters }; if (event.target.value) filters[key] = event.target.value; else delete filters[key];
            setDraft({ ...selection, filters });
          }}><option value="">All — no filter</option>{filterEnumOptions(properties, key).map(option => <option key={option} value={option}>{option}</option>)}</select></label>)}
        </div>
        {!filterKeys.length ? <p className="text-metadata text-text-secondary">No filters are registered for this chart version.</p> : null}
        {draftRangeError ? <p role="alert">Enter a non-empty calendar range within the chart limit. Nothing has been applied.</p> : null}
        <button type="button" className={CONTROL_CLASS} aria-disabled={!draft || Boolean(draftRangeError)} onClick={() => { if (draft && !draftRangeError) void resolve(selection, attrs.observed_dataset_version_id, true); }}>Apply range and filters</button>
      </fieldset>
    </> : null}
    <p className="text-metadata text-text-secondary">Escape returns focus to the selected chart block in the editor.</p>
  </section>;
}
