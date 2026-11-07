import StarterKit from "@tiptap/starter-kit";
import { Extension } from "@tiptap/core";

import { Divider } from "./blocks/divider";
import { DataTable } from "./blocks/data-table";
import {
  Evidence,
  Hypothesis,
  Insight,
  Risk,
} from "./blocks/annotation-nodes";
import { LiveChart } from "./blocks/live-chart";
import { blockIdAttr } from "./attributes";
import { BlockOperationShortcuts } from "./commands";
import { EditorUiBridge } from "./ui-bridge";
import { StableBlockIds } from "./block-id";

/**
 * Declares the canonical `block_id` attribute on the four rich-text block
 * families that StarterKit provides (paragraph/heading/bullet_list/
 * ordered_list). Without a declared attribute, ProseMirror drops the key
 * when parsing canonical JSON and the stable identity would be lost. The
 * atomic canonical nodes declare their attrs themselves; nested nodes
 * (listItem/text) must NOT carry block ids per the canonical grammar.
 */
const CANONICAL_TOP_LEVEL_RICH_NODES = ["paragraph", "heading", "bulletList", "orderedList"];

const BlockIdNodeAttrs = Extension.create({
  name: "blockIdNodeAttrs",

  addGlobalAttributes() {
    return [
      {
        types: CANONICAL_TOP_LEVEL_RICH_NODES,
        attributes: {
          block_id: blockIdAttr(),
        },
      },
    ];
  },
});

/**
 * The assembled research editor extension set (NI-039).
 *
 * StarterKit is configured to the canonical P0 grammar (EDITOR_SPECIFICATION
 * / NI-036 validator): headings 1-3, bold/italic/link marks only, lists via
 * the standard Tiptap names (mapped to canonical at the serialize boundary),
 * no horizontalRule/blockquote/codeBlock/code/strike/underline/hardBreak —
 * content outside the whitelist cannot be created, and pasted content is
 * dropped to the grammar by the schema itself. `trailingNode` is disabled so
 * the editor never appends blocks the author did not write.
 */
export const EDITOR_EXTENSIONS = [
  StarterKit.configure({
    heading: { levels: [1, 2, 3] },
    horizontalRule: false,
    blockquote: false,
    codeBlock: false,
    code: false,
    strike: false,
    underline: false,
    hardBreak: false,
    trailingNode: false,
    link: {
      openOnClick: false,
      autolink: true,
      defaultProtocol: "https",
      // Serializer enforces the canonical http(s) + no-credentials rules; the
      // editor-level allowlist keeps the paste path close to it.
      protocols: ["http", "https"],
      isAllowedUri: (uri) => {
        try {
          const parsed = new URL(uri);
          return (
            (parsed.protocol === "http:" || parsed.protocol === "https:") &&
            !parsed.username &&
            !parsed.password
          );
        } catch {
          return false;
        }
      },
    },
  }),
  // Canonical identity on the rich-text families, then the P0 atomic blocks.
  BlockIdNodeAttrs,
  Divider,
  LiveChart,
  DataTable,
  Insight,
  Hypothesis,
  Evidence,
  Risk,
  // Stable top-level identities and the structural operations.
  StableBlockIds,
  BlockOperationShortcuts,
  EditorUiBridge,
];
