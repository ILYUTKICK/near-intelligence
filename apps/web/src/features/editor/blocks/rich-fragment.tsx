import type { ReactNode } from "react";

import type { RichFragment } from "../canonical";

/**
 * Read-only renderer for canonical rich text fragments (the `body` of risk
 * and insight blocks). Bodies are canonical JSON (NI-036), so this renders
 * exactly the validated grammar — paragraphs, bullet/ordered lists with
 * depth <= 3, bold/italic/link marks — without a second rich-text engine.
 */

function renderRuns(runs: Array<{ type: string; text: string; marks?: Array<{ type: string; attrs?: { href?: string } }> }>): ReactNode[] {
  return runs.map((run, index) => {
    let node: ReactNode = run.text;
    for (const mark of [...(run.marks ?? [])].reverse()) {
      if (mark.type === "bold") {
        node = <strong key={index}>{node}</strong>;
      } else if (mark.type === "italic") {
        node = <em key={index}>{node}</em>;
      } else if (mark.type === "link") {
        node = (
          <a key={index} href={mark.attrs?.href} className="underline underline-offset-2">
            {node}
          </a>
        );
      }
    }
    return <span key={index}>{node}</span>;
  });
}

function renderFragmentNodes(fragment: RichFragment): ReactNode[] {
  return fragment.map((node, index) => {
    if (node.type === "paragraph") {
      return <p key={index}>{renderRuns(node.content)}</p>;
    }
    const items = node.content.map((item, itemIndex) => (
      <li key={itemIndex}>{renderFragmentNodes(item.content)}</li>
    ));
    return node.type === "ordered_list" ? <ol key={index}>{items}</ol> : <ul key={index}>{items}</ul>;
  });
}

export function RichFragmentView({ fragment }: { fragment: RichFragment }) {
  if (fragment.length === 0) {
    return <p className="text-text-secondary italic">(empty body)</p>;
  }
  return <div className="flex flex-col gap-2">{renderFragmentNodes(fragment)}</div>;
}
