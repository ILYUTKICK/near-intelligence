import { Node, mergeAttributes } from "@tiptap/core";
import {
  NodeViewWrapper,
  ReactNodeViewRenderer,
  type NodeViewProps,
} from "@tiptap/react";
import { useCallback, useContext, useEffect, useState } from "react";

import { blockIdAttr, jsonAttr, stringAttr } from "../attributes";
import { emitOpenBlockProperties } from "../ui-bridge";
import { HistoricalRevisionContext, useChartEditorContext } from "./chart-context";
import { loadPinnedRun } from "./model-run-api";
import { fieldPair, shortId } from "./display";
import { RichFragmentView } from "./rich-fragment";
import {
  MAX_BODY_PLAIN_CHARS,
  type CanonicalModelResultBlock,
  type RichFragment,
} from "../canonical";
import { recordedFloat, recordedJson } from "@/features/models/recorded";
import type { ModelRunDetail } from "@/features/models/models-schema";

/**
 * Canonical `modelResult` block (P1, NI-055): a pinned published model run
 * with an editable interpretation. The block stores ONLY ids and the
 * authored narrative — coefficients/diagnostics never live in the document
 * JSON. The node view re-projects the recorded summary from the immutable
 * `app.model_runs` row through the identity-checked run reader
 * (`loadPinnedRun` accepts only the exact pinned run id), so editing the
 * prose can never change the recorded result and a source revision never
 * refits it. The card is atomic: selected, moved, duplicated and deleted as
 * one unit; its pins travel with it.
 */
export const ModelResult = Node.create({
  name: "modelResult",
  group: "block",
  atom: true,
  selectable: true,
  draggable: true,

  addAttributes() {
    return {
      block_id: blockIdAttr(),
      model_run_id: stringAttr("model_run_id"),
      dataset_version_id: stringAttr("dataset_version_id"),
      interpretation: jsonAttr("interpretation"),
    };
  },

  parseHTML() {
    return [{ tag: "div[data-model-result]" }];
  },

  renderHTML({ HTMLAttributes }) {
    return ["div", mergeAttributes({ "data-model-result": "" }, HTMLAttributes)];
  },

  addNodeView() {
    return ReactNodeViewRenderer(ModelResultBlockView);
  },
});

export type ModelResultAttrs = CanonicalModelResultBlock["attrs"];

const cardWrapperClass =
  "my-4 rounded-surface border border-control-border bg-surface p-4";

const CONTROL_CLASS = "min-h-11 max-w-full rounded-control border border-control-border bg-surface px-3 py-2 font-ui text-base sm:text-ui touch-manipulation leading-ui text-text hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus disabled:opacity-60 aria-disabled:opacity-60";

/**
 * The authored interpretation as canonical rich text: each non-empty line
 * becomes one plain-text paragraph (the NI-046 dialog precedent — `insightBody`).
 * Editing the prose can never touch the pinned run or dataset ids, which
 * are separate attrs.
 */
export function interpretationBody(text: string): RichFragment {
  return text.split(/\r?\n/).map((line) => ({
    type: "paragraph",
    content: line ? [{ type: "text", text: line }] : [],
  }));
}

/** Flatten a stored interpretation for editing (paragraph text, list markers kept). */
export function interpretationText(fragment: RichFragment | null): string {
  if (!fragment) {
    return "";
  }
  const lines: string[] = [];
  const stack = [...fragment];
  while (stack.length > 0) {
    const node = stack.shift();
    if (!node) {
      continue;
    }
    if (node.type === "paragraph") {
      lines.push(node.content.map((run) => run.text).join(""));
    } else {
      for (const item of node.content) {
        for (const child of item.content) {
          if (child.type === "paragraph") {
            lines.push(child.content.map((run) => run.text).join(""));
          } else {
            stack.push(child);
          }
        }
      }
    }
  }
  return lines.join("\n");
}

function RunSummary({ run }: { run: ModelRunDetail }) {
  return (
    <div className="min-w-0">
      {/* LIMITS FIRST (the NI-054 ordering contract): the prohibited labels
          and gate limit codes render before any coefficient. */}
      <div className="mt-2 rounded-control border border-danger/40 bg-surface-muted p-3">
        <p className="font-ui text-ui leading-ui font-medium text-text">
          Prohibited labels — this result must never be presented as:
        </p>
        <ul className="mt-1 list-disc pl-5 text-metadata leading-metadata text-text">
          {run.limitations.prohibited_labels.map((label) => (
            <li key={label}>{label}</li>
          ))}
        </ul>
        {run.limitations.gate_limit_codes.length > 0 ? (
          <p className="mt-2 text-metadata leading-metadata text-text-secondary">
            Gate limit codes: {run.limitations.gate_limit_codes.join(", ")}
          </p>
        ) : null}
        <p className="mt-2 text-metadata leading-metadata text-text-secondary">
          Associations recorded by the publication gate — never causal effects.
        </p>
      </div>
      <table className="mt-3 w-full border-collapse text-metadata leading-metadata">
        <caption className="sr-only">Recorded coefficients of the pinned run</caption>
        <thead>
          <tr className="text-left text-text-secondary">
            <th scope="col" className="border border-border p-1">Term</th>
            <th scope="col" className="border border-border p-1">Estimate</th>
            <th scope="col" className="border border-border p-1">Std. error</th>
            <th scope="col" className="border border-border p-1">t</th>
            <th scope="col" className="border border-border p-1">p</th>
            <th scope="col" className="border border-border p-1">95% CI</th>
          </tr>
        </thead>
        <tbody>
          {run.coefficients.map((coefficient) => (
            <tr key={coefficient.name}>
              <td className="border border-border p-1">{coefficient.name}</td>
              <td className="border border-border p-1 font-mono">{recordedFloat(coefficient.estimate)}</td>
              <td className="border border-border p-1 font-mono">{recordedFloat(coefficient.std_error)}</td>
              <td className="border border-border p-1 font-mono">{recordedFloat(coefficient.t_stat)}</td>
              <td className="border border-border p-1 font-mono">{recordedFloat(coefficient.p_value)}</td>
              <td className="border border-border p-1 font-mono">
                [{recordedFloat(coefficient.ci95_low)}, {recordedFloat(coefficient.ci95_high)}]
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-2 text-metadata leading-metadata text-text-secondary">
        Gate verdict {run.gate_verdict} · sample {run.sample.start} to {run.sample.end_exclusive} (end
        exclusive) · {run.sample.nobs} observations · recorded tolerances rtol{" "}
        {run.tolerances.coefficient_rtol} / atol {run.tolerances.coefficient_atol}.
      </p>
      <details className="mt-2 rounded-control border border-border p-2">
        <summary className="min-h-11 cursor-pointer text-ui leading-ui">Recorded diagnostics (verbatim)</summary>
        <pre className="mt-2 overflow-x-auto rounded-control bg-surface-muted p-2 font-mono text-metadata leading-metadata">
          <code>{recordedJson(run.diagnostics)}</code>
        </pre>
      </details>
    </div>
  );
}

function ModelResultBlockView({ node, editor, getPos, updateAttributes }: NodeViewProps) {
  const attrs = node.attrs as {
    block_id: string | null;
    model_run_id: string | null;
    dataset_version_id: string | null;
    interpretation: RichFragment | null;
  };
  const historical = useContext(HistoricalRevisionContext);
  const account = useChartEditorContext();
  const [run, setRun] = useState<ModelRunDetail | null>(null);
  const [loading, setLoading] = useState(() => Boolean(attrs.model_run_id));
  const [error, setError] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);

  const reload = useCallback((signal: AbortSignal) => {
    loadPinnedRun(attrs.model_run_id ?? "", signal)
      .then((value) => {
        if (!signal.aborted) {
          setRun(value);
          setError(null);
          setLoading(false);
        }
      })
      .catch((cause: unknown) => {
        if (!signal.aborted) {
          setRun(null);
          setError(cause instanceof Error ? cause.message : "The pinned model run could not be loaded.");
          setLoading(false);
        }
      });
  }, [attrs.model_run_id]);

  useEffect(() => {
    if (!attrs.model_run_id) {
      return;
    }
    const controller = new AbortController();
    reload(controller.signal);
    return () => controller.abort();
  }, [reload, attrs.model_run_id, retry]);

  const editable = editor.isEditable && !historical;

  return (
    <NodeViewWrapper
      data-model-result-block-view
      className={cardWrapperClass}
      aria-label="Model result block"
    >
      <div
        contentEditable={false}
        className="not-prose min-w-0"
        onKeyDown={(event) => {
          if (event.key === "Escape" && !event.defaultPrevented
            && !(event.target as HTMLElement).closest('[role="dialog"]')
            && !(event.target as HTMLElement).closest("textarea, input")) {
            event.preventDefault();
            event.stopPropagation();
            const pos = getPos();
            if (typeof pos === "number") {
              editor.commands.setNodeSelection(pos);
              editor.view.focus();
            }
          }
        }}
      >
        <div className="flex flex-wrap items-center gap-2">
          <p className="font-ui text-ui leading-ui font-medium text-text">Model result</p>
          {run ? (
            <span className="rounded-control border border-control-border px-1.5 py-0.5 text-metadata leading-metadata text-text-secondary">
              {run.model_id} · v{run.model_version}
            </span>
          ) : null}
          <span className="rounded-control border border-control-border px-1.5 py-0.5 text-metadata leading-metadata text-text-secondary">
            Published run · immutable result
          </span>
        </div>
        <p className="mt-1 text-metadata leading-metadata text-text-secondary">
          The recorded result below is re-projected from the pinned published run — never stored in
          this document. Editing your interpretation never changes it.
        </p>
        <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-metadata leading-metadata text-text-secondary">
          {fieldPair("Pinned run", shortId(attrs.model_run_id), "mmr")}
          {fieldPair("Pinned dataset version", shortId(attrs.dataset_version_id), "mds")}
          {run ? fieldPair("Specification version", `${run.model_id}@${run.model_version}`, "msv") : null}
        </dl>
        {loading ? <p role="status" className="mt-2 text-metadata leading-metadata text-text-secondary">
          Loading the pinned published run…
        </p> : null}
        {!attrs.model_run_id ? <div role="alert" className="mt-2 text-metadata leading-metadata text-danger">
          <p>This saved block has no pinned run identity.</p>
        </div> : null}
        {error ? <div role="alert" className="mt-2 text-metadata leading-metadata text-danger">
          <p>{error}</p>
          {attrs.model_run_id && editable ? (
            <button type="button" className={CONTROL_CLASS} onClick={() => setRetry((value) => value + 1)}>
              Retry loading the pinned run
            </button>
          ) : null}
        </div> : null}
        {run ? <RunSummary run={run} /> : null}
        {run ? (
          <p className="mt-2 text-metadata leading-metadata text-text-secondary">
            Source:{" "}
            <a href={`/models/${run.run_id}`} className="underline underline-offset-2">
              published run page
            </a>{" "}
            (the recorded manifest bundle travels with the publication).
          </p>
        ) : null}
        <div className="mt-2 text-body leading-body text-text">
          <p className="font-ui text-ui leading-ui font-medium text-text">Interpretation</p>
          {editable ? (
            <>
              <label className="sr-only" htmlFor={`interpretation-${attrs.block_id ?? "new"}`}>
                Interpretation of the pinned model result
              </label>
              <textarea
                id={`interpretation-${attrs.block_id ?? "new"}`}
                aria-label="Interpretation of the pinned model result"
                rows={4}
                maxLength={MAX_BODY_PLAIN_CHARS}
                value={interpretationText(attrs.interpretation)}
                onChange={(event) =>
                  updateAttributes({ interpretation: interpretationBody(event.target.value) })
                }
                className="mt-1 w-full rounded-control border border-control-border bg-surface px-2 py-1 font-ui text-ui leading-ui text-text focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
              />
              <p className="mt-1 text-metadata leading-metadata text-text-secondary">
                Each line becomes one paragraph. Your prose is stored in the document; the recorded
                result stays on the pinned run.
              </p>
            </>
          ) : attrs.interpretation ? (
            <RichFragmentView fragment={attrs.interpretation} />
          ) : null}
        </div>
        {historical && historical.versionId ? (
          <p className="mt-2 text-metadata leading-metadata text-text-secondary">
            Historical revision {shortId(historical.versionId)}: the pinned context is shown exactly
            as saved.
          </p>
        ) : null}
        {editable ? (
          <button
            type="button"
            className={CONTROL_CLASS}
            onClick={() => {
              const pos = typeof getPos === "function" ? getPos() : undefined;
              if (typeof pos === "number") {
                editor.commands.setNodeSelection(pos);
              }
              emitOpenBlockProperties(editor, attrs.block_id);
            }}
          >
            Edit properties
          </button>
        ) : null}
        {!account?.ready && !historical ? (
          <p role="status" className="mt-2 text-metadata leading-metadata text-text-secondary">
            Suspended while your document account is checked. The pinned result is unchanged.
          </p>
        ) : null}
      </div>
    </NodeViewWrapper>
  );
}
