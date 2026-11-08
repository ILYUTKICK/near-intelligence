"use client";

import type { Editor } from "@tiptap/core";
import { EditorContent, useEditor } from "@tiptap/react";
import { useCallback, useEffect, useRef, useState } from "react";

import { useRouter } from "next/navigation";

import { Drawer, DrawerContent } from "@/components/ui/drawer";
import { Skeleton } from "@/components/data-state/Skeleton";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import { canonicalToTiptapDoc } from "./serialize";
import { EDITOR_EXTENSIONS } from "./extensions";
import { deriveOutline, type OutlineEntry } from "./outline";
import {
  blockLabel,
  canonicalSnapshot,
  currentTopLevelBlock,
  duplicateTopLevelBlock,
  findDependentBlocks,
  insertBlock,
  moveTopLevelBlock,
  removeTopLevelBlocks,
  topLevelNodePosition,
  type CurrentBlock,
  type DependentBlock,
} from "./commands";
import {
  CANONICAL_SCHEMA_VERSION,
  validateCanonicalDocument,
  type CanonicalDocument,
  type CanonicalCell,
  type CanonicalTableColumn,
} from "./canonical";
import { InsertMenuButton, SlashMenu, type InsertItemChoice } from "./insert-menu";
import { BlockToolbar } from "./block-toolbar";
import { OutlinePane } from "./outline-pane";
import { ContextPane } from "./context-pane";
import { DeleteConfirmationDialog } from "./delete-confirmation";
import {
  EDITOR_OPEN_BLOCK_PROPERTIES,
  EDITOR_REQUEST_BLOCK_DELETE,
  EDITOR_SLASH_TRIGGER,
  detailOf,
} from "./ui-bridge";
import { ConflictRecoveryDialog } from "./persistence/conflict-dialog";
import { SaveStatusBar, formatSavedAt } from "./persistence/save-status";
import { useDocumentSave } from "./persistence/use-document-save";
import { downloadJson } from "./persistence/download";
import { newIdempotencyKey, saveRevision, type SaveRequestBody } from "./persistence/save-transport";
import {
  createDocument,
  DocumentApiError,
  getDocument,
} from "@/features/documents/list/documents-api";
import { DOCUMENT_TITLE_MAX_LENGTH } from "@/features/documents/list/documents-schema";

/**
 * The three-pane research editor workbench (NI-039):
 *
 * - left: heading outline anchored to stable block ids;
 * - center: the paper (Tiptap) with the P0 block taxonomy and the structural
 *   operations (insert via menu/slash, remove with explicit dependent-link
 *   confirmation, reorder, duplicate, table and risk title editing);
 * - right: context tools showing the selected block's properties.
 *
 * Responsive contract (INFORMATION_ARCHITECTURE): >=1280px shows the three
 * panes (collapsible); 768-1279px adds a collapsible inline outline and the
 * tools drawer; below 768px the paper is the only pane and outline/tools
 * open as drawers — one at a time, focus handled by the drawer primitive.
 *
 * Persistence (NI-040): autosave after 1s idle with a hard 5s ceiling, an
 * immediate manual save (button or Mod+S), one request in flight with later
 * content coalesced, If-Match compare-and-set with a per-attempt
 * Idempotency-Key, a truthful status line, honest offline queueing, session
 * draft recovery, and an explicit 409 conflict dialog (reload / overwrite /
 * download / new copy — never a silent overwrite).
 */

export interface EditorShellProps {
  documentId: string;
  title: string;
  revision: number;
  updatedAt: string;
  /** Already validated canonical content (the persisted revision). */
  content: CanonicalDocument;
}

interface SlashMenuState {
  position: number;
  coordinates: { left: number; top: number } | null;
}

interface DeleteRequest {
  targetIndex: number;
  targetLabel: string;
  dependents: readonly DependentBlock[];
}

export function EditorShell({ documentId, title, revision, updatedAt, content }: EditorShellProps) {
  const router = useRouter();
  // The conflict dialog opens declaratively whenever a 409 state exists and
  // has not been dismissed for THIS conflict (each conflict carries a fresh
  // timestamp, so a later conflict re-opens it). No effect/setState cascade.
  const [conflictDismissedAt, setConflictDismissedAt] = useState<string | null>(null);
  const [conflictBusy, setConflictBusy] = useState(false);
  const [conflictActionError, setConflictActionError] = useState<string | null>(null);
  const editorRef = useRef<Editor | null>(null);
  const paperRef = useRef<HTMLDivElement>(null);

  /** Captures the editor state as a save request body (canonical, validated). */
  const capture = useCallback((): SaveRequestBody => {
    const current = editorRef.current;
    if (!current) {
      throw new Error("The editor is not ready");
    }
    const snapshot = canonicalSnapshot(current);
    return {
      schema_version: CANONICAL_SCHEMA_VERSION,
      content: snapshot as unknown as Record<string, unknown>,
      observed_contexts: [],
    };
  }, []);

  const controller = useDocumentSave({ documentId, initialRevision: revision, capture });
  // The controller's members are stable callbacks (they close over the
  // coordinator); depending on THEM — not the per-status object — keeps the
  // effects below from re-running on every save-status transition. This is
  // also what keeps the baseline adoption a one-time event: re-running it on
  // edits would swallow unsaved content into the "acknowledged" baseline.
  const { adoptBaseline, markChanged } = controller;

  const editor = useEditor({
    extensions: EDITOR_EXTENSIONS,
    content: canonicalToTiptapDoc(content),
    immediatelyRender: false,
    editorProps: {
      attributes: {
        class: "editor-paper",
        role: "textbox",
        "aria-multiline": "true",
        "aria-label": "Research paper editor",
      },
    },
  });
  // Refs sync in effects (never during render); event-time readers always
  // see the current values.
  useEffect(() => {
    editorRef.current = editor;
  }, [editor]);

  const [outline, setOutline] = useState<OutlineEntry[]>([]);
  const [blockCount, setBlockCount] = useState(content.content.length);
  const [currentBlock, setCurrentBlock] = useState<CurrentBlock | null>(null);
  const [announcement, setAnnouncement] = useState("");
  const [deleteRequest, setDeleteRequest] = useState<DeleteRequest | null>(null);
  const [slashMenu, setSlashMenu] = useState<SlashMenuState | null>(null);
  const [drawerPane, setDrawerPane] = useState<"outline" | "tools" | null>(null);
  const [outlineCollapsed, setOutlineCollapsed] = useState(false);
  const [toolsCollapsed, setToolsCollapsed] = useState(false);
  const [tabletOutlineOpen, setTabletOutlineOpen] = useState(false);

  const announce = useCallback((message: string) => {
    setAnnouncement(message);
  }, []);

  // -- persistence (NI-040) -------------------------------------------------- //

  // The loaded (already validated) content is the acknowledged baseline: the
  // editor may normalize it (e.g. an empty document to one paragraph), so the
  // baseline is captured from the editor itself — never a phantom revision.
  useEffect(() => {
    if (!editor) {
      return;
    }
    adoptBaseline(revision);
  }, [editor, adoptBaseline, revision]);

  // Every editor update marks the coordinator; content is captured only when
  // a save actually fires (cheap per-keystroke path).
  const onEditorChanged = useCallback(() => {
    markChanged();
  }, [markChanged]);

  const conflictAt = controller.status.kind === "conflict" ? controller.status.at : null;
  const conflictDialogOpen = conflictAt !== null && conflictDismissedAt !== conflictAt;

  // Manual save (button and Mod+S): during a conflict the button reopens the
  // explicit resolution dialog instead of racing another 409.
  const handleSaveNow = useCallback(() => {
    if (controller.status.kind === "conflict") {
      setConflictDismissedAt(null);
      return;
    }
    controller.saveNow();
  }, [controller]);

  // Mod+S inside the research editor claims the browser save shortcut for
  // the document save (standard editor behavior; the listener lives on the
  // window so the handler identity always matches the current controller).
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && !event.altKey && event.key.toLowerCase() === "s") {
        event.preventDefault();
        handleSaveNow();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [handleSaveNow]);

  const handleStatusRetry = useCallback(() => {
    controller.retry();
  }, [controller]);

  const handleConflictOpen = useCallback(() => {
    setConflictDismissedAt(null);
    setConflictActionError(null);
  }, []);

  const handleConflictDismiss = useCallback(() => {
    setConflictDismissedAt(conflictAt);
    setConflictActionError(null);
  }, [conflictAt]);

  const handleConflictOverwrite = useCallback(() => {
    const status = controller.status;
    if (status.kind !== "conflict") {
      return;
    }
    if (status.serverRevision === null) {
      setConflictActionError(
        "The server did not report its current revision — load the server version or download a local copy instead.",
      );
      return;
    }
    try {
      // The explicit dialog confirmation is the only path here: CAS against
      // the revision the 409 reported, with the LATEST local content.
      controller.overwriteConflict(status.serverRevision);
      setConflictActionError(null);
    } catch {
      setConflictActionError(
        "The current content could not be serialized for saving — nothing was sent.",
      );
    }
  }, [controller]);

  const handleConflictReload = useCallback(async () => {
    setConflictBusy(true);
    setConflictActionError(null);
    try {
      const document = await getDocument(documentId);
      const rawContent = document.content;
      if (rawContent.schema_version !== CANONICAL_SCHEMA_VERSION) {
        throw new Error("the server content uses an unsupported schema version");
      }
      const validated = validateCanonicalDocument(rawContent);
      if (!editorRef.current) {
        throw new Error("the editor is not ready");
      }
      editorRef.current.commands.setContent(canonicalToTiptapDoc(validated));
      controller.adoptServerState(document.revision);
      announce("Loaded the server version. Your local edits were discarded as you confirmed.");
    } catch (error) {
      setConflictActionError(describeRecoveryActionError(error, "The server version could not be loaded."));
    } finally {
      setConflictBusy(false);
    }
  }, [controller, documentId, announce]);

  const handleDownloadLocalCopy = useCallback(() => {
    try {
      const body = controller.captureLocal();
      downloadJson(body.content, `document-local-copy-${documentId}.json`);
      announce("Downloaded a local copy of the current content.");
    } catch {
      setConflictActionError("The current content could not be serialized for download.");
    }
  }, [controller, documentId, announce]);

  const handleConflictNewCopy = useCallback(async () => {
    setConflictBusy(true);
    setConflictActionError(null);
    try {
      const body = controller.captureLocal();
      // POST /documents (owner-checked, client Idempotency-Key) then the
      // first content save against the created revision 1 — the copy holds
      // exactly the local content, the original stays untouched.
      const created = await createDocument({
        title: recoveredCopyTitle(title),
        idempotencyKey: newIdempotencyKey(),
      });
      await saveRevision({
        documentId: created.id,
        revision: created.revision,
        idempotencyKey: newIdempotencyKey(),
        body,
      });
      router.push(`/workspace/research/${created.id}`);
    } catch (error) {
      setConflictActionError(
        describeRecoveryActionError(error, "The copy could not be saved as a new document."),
      );
      setConflictBusy(false);
      return;
    }
    setConflictBusy(false);
  }, [controller, title, router]);

  const handleDraftRestore = useCallback(() => {
    const offer = controller.draft;
    if (!offer || offer.invalidReason !== null || !editorRef.current) {
      return;
    }
    try {
      const validated = validateCanonicalDocument(offer.body.content);
      editorRef.current.commands.setContent(canonicalToTiptapDoc(validated));
      controller.restoreDraft();
      announce("Restored the draft with unsaved changes. Autosave will save it shortly.");
    } catch {
      controller.discardDraft();
    }
  }, [controller, announce]);

  const handleDraftDiscard = useCallback(() => {
    controller.discardDraft();
    announce("Discarded the recovered draft.");
  }, [controller, announce]);


  // -- editor state derivation (doc + selection driven) --------------------- //

  useEffect(() => {
    if (!editor) {
      return;
    }
    const refreshDoc = (contentChanged: boolean) => {
      setOutline(deriveOutline(editor.getJSON()));
      setBlockCount(editor.state.doc.childCount);
      setCurrentBlock(currentTopLevelBlock(editor));
      if (contentChanged) {
        onEditorChanged();
      }
    };
    const refreshSelection = () => {
      setCurrentBlock(currentTopLevelBlock(editor));
      // Typing away from the trigger closes the slash menu (a new keystroke
      // is a clearer intent than a stale menu).
      setSlashMenu(null);
    };
    // The initial derivation is NOT a content change: the editor holds the
    // loaded baseline (adoptBaseline adopts it), and marking it dirty would
    // schedule a phantom save.
    refreshDoc(false);
    const onUpdate = () => refreshDoc(true);
    editor.on("update", onUpdate);
    editor.on("selectionUpdate", refreshSelection);
    return () => {
      editor.off("update", onUpdate);
      editor.off("selectionUpdate", refreshSelection);
    };
  }, [editor, onEditorChanged]);

  // -- bridges (node views / keyboard -> shell, via bubbling DOM events) ---- //

  useEffect(() => {
    const container = paperRef.current;
    if (!editor || !container) {
      return;
    }
    const onOpenProperties = () => {
      setToolsCollapsed(false);
      setDrawerPane("tools");
    };
    const onRequestDelete = (event: Event) => {
      const { index } = detailOf<{ index: number }>(event, { index: -1 });
      setDeleteRequest(buildDeleteRequest(editor, index));
    };
    const onSlashTrigger = (event: Event) => {
      const { position } = detailOf<{ position: number }>(event, { position: -1 });
      setSlashMenu({
        position,
        coordinates: computeSlashCoordinates(editor, position, container),
      });
    };
    container.addEventListener(EDITOR_OPEN_BLOCK_PROPERTIES, onOpenProperties);
    container.addEventListener(EDITOR_REQUEST_BLOCK_DELETE, onRequestDelete);
    container.addEventListener(EDITOR_SLASH_TRIGGER, onSlashTrigger);
    return () => {
      container.removeEventListener(EDITOR_OPEN_BLOCK_PROPERTIES, onOpenProperties);
      container.removeEventListener(EDITOR_REQUEST_BLOCK_DELETE, onRequestDelete);
      container.removeEventListener(EDITOR_SLASH_TRIGGER, onSlashTrigger);
    };
  }, [editor]);

  // -- operations ------------------------------------------------------------ //

  const handleInsert = useCallback(
    (choice: InsertItemChoice) => {
      if (!editor) {
        return;
      }
      setSlashMenu(null);
      const ok = insertBlock(editor, choice.type, { headingLevel: choice.headingLevel });
      announce(ok ? "Block inserted. Focus is in the new block." : "The block could not be inserted at this position.");
    },
    [editor, announce],
  );

  const handleMove = useCallback(
    (delta: -1 | 1) => {
      if (!editor || !currentBlock) {
        return;
      }
      const label = blockLabel(currentBlock.canonicalType);
      const ok = moveTopLevelBlock(editor, currentBlock.index, delta);
      announce(
        ok
          ? `${label} moved ${delta === -1 ? "up" : "down"}. Its id and links are unchanged.`
          : `The ${label.toLowerCase()} is already at this end of the document.`,
      );
    },
    [editor, currentBlock, announce],
  );

  const handleDuplicate = useCallback(() => {
    if (!editor || !currentBlock) {
      return;
    }
    const ok = duplicateTopLevelBlock(editor, currentBlock.index);
    announce(
      ok
        ? "Block duplicated. The copy has new ids; references to other blocks are unchanged."
        : "The block could not be duplicated.",
    );
  }, [editor, currentBlock, announce]);

  const handleDeleteFromToolbar = useCallback(() => {
    if (!editor || !currentBlock) {
      return;
    }
    const snapshot = canonicalSnapshot(editor);
    const block = snapshot.content[currentBlock.index];
    if (!block) {
      return;
    }
    const dependents = findDependentBlocks(snapshot.content, block.attrs.block_id);
    if (dependents.length > 0) {
      // Explicit preview of the affected links before anything is removed.
      setDeleteRequest({
        targetIndex: currentBlock.index,
        targetLabel: blockLabel(block.type),
        dependents,
      });
      return;
    }
    const ok = removeTopLevelBlocks(editor, [currentBlock.index]);
    announce(ok ? "Block deleted. You can undo this." : "The block could not be deleted.");
  }, [editor, currentBlock, announce]);

  const confirmDelete = useCallback(() => {
    if (!editor || !deleteRequest) {
      return;
    }
    const snapshot = canonicalSnapshot(editor);
    const target = snapshot.content[deleteRequest.targetIndex];
    const idToIndex = new Map(snapshot.content.map((block, index) => [block.attrs.block_id, index]));
    const indices = new Set<number>();
    if (target) {
      indices.add(deleteRequest.targetIndex);
    }
    for (const dependent of deleteRequest.dependents) {
      const index = idToIndex.get(dependent.blockId);
      if (index !== undefined) {
        indices.add(index);
      }
    }
    const ok = removeTopLevelBlocks(editor, [...indices]);
    setDeleteRequest(null);
    announce(
      ok
        ? deleteRequest.dependents.length > 0
          ? `Deleted ${indices.size} blocks including ${deleteRequest.dependents.length} dependent link${deleteRequest.dependents.length === 1 ? "" : "s"} — no dangling references remain.`
          : "Block deleted. You can undo this."
        : "The blocks could not be deleted.",
    );
  }, [editor, deleteRequest, announce]);

  const handleTableChange = useCallback(
    (patch: { columns: CanonicalTableColumn[]; rows: CanonicalCell[][] }) => {
      if (!editor || !currentBlock) {
        return;
      }
      const position = topLevelNodePosition(editor, currentBlock.index);
      editor.commands.command(({ tr, dispatch }) => {
        if (dispatch) {
          tr.setNodeMarkup(position, undefined, { columns: patch.columns, rows: patch.rows });
          dispatch(tr);
        }
        return true;
      });
    },
    [editor, currentBlock],
  );

  const handleOutlineNavigate = useCallback(
    (blockId: string) => {
      if (!editor) {
        return;
      }
      let position: number | null = null;
      editor.state.doc.forEach((node, offset) => {
        if (node.attrs.block_id === blockId) {
          position = offset;
        }
      });
      if (position !== null) {
        editor.chain().focus().setTextSelection(position + 1).run();
        announce("Selected the heading in the paper.");
      }
      setDrawerPane(null);
    },
    [editor, announce],
  );

  const savedAt = controller.status.kind === "clean" ? controller.status.savedAt : null;
  const displayedUpdatedAt = savedAt ?? updatedAt;

  return (
    <div className="flex flex-col gap-4" data-testid="editor-workbench">
      <p aria-live="polite" role="status" data-testid="editor-announcement" className="sr-only">
        {announcement}
      </p>

      <header>
        <h1 className="font-serif text-title leading-title">{title}</h1>
        <p className="text-metadata leading-metadata text-text-secondary mt-1">
          Updated <time dateTime={displayedUpdatedAt}>{displayedUpdatedAt}</time> · Revision{" "}
          {controller.revision} · Schema version 1
        </p>
        <div className="mt-2">
          <SaveStatusBar
            status={controller.status}
            onSave={handleSaveNow}
            onRetry={handleStatusRetry}
            onOpenConflict={handleConflictOpen}
            onDownloadCopy={handleDownloadLocalCopy}
          />
        </div>
      </header>

      {controller.draft ? (
        <div
          role="alert"
          data-testid="draft-recovery"
          className="rounded-surface border border-border bg-surface p-4"
        >
          <p className="text-ui leading-ui font-medium text-text">
            A draft with unsaved changes from this session was found (saved at{" "}
            {formatSavedAt(controller.draft.capturedAt)}, based on revision{" "}
            {controller.draft.baseRevision}).
          </p>
          {controller.draft.invalidReason ? (
            <p className="text-ui leading-ui text-warning mt-1">
              The draft cannot be restored: {controller.draft.invalidReason}. Discard it or keep
              editing without it.
            </p>
          ) : (
            <p className="text-body leading-body text-text-secondary mt-1">
              Restoring replaces the paper with the draft&apos;s content; it is saved to the
              server by the next autosave. The server version stays in the document history.
            </p>
          )}
          <div className="mt-3 flex flex-wrap gap-2">
            {controller.draft.invalidReason === null ? (
              <Button variant="secondary" onClick={handleDraftRestore} data-testid="draft-restore">
                Restore draft
              </Button>
            ) : null}
            <Button variant="quiet" onClick={handleDraftDiscard} data-testid="draft-discard">
              Discard draft
            </Button>
          </div>
        </div>
      ) : null}

      <div className="flex flex-wrap items-start gap-2">
        <InsertMenuButton onInsert={handleInsert} disabled={!editor} />
        <BlockToolbar
          currentBlock={currentBlock}
          blockCount={blockCount}
          onMoveUp={() => handleMove(-1)}
          onMoveDown={() => handleMove(1)}
          onDuplicate={handleDuplicate}
          onDelete={handleDeleteFromToolbar}
        />
        <div className="ml-auto flex items-center gap-2">
          <button
            type="button"
            className="inline-flex min-h-11 items-center rounded-control border border-control-border bg-surface px-3 text-ui leading-ui text-text hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus md:hidden"
            aria-label="Open outline drawer"
            onClick={() => setDrawerPane("outline")}
          >
            Outline
          </button>
          <button
            type="button"
            className="inline-flex min-h-11 items-center rounded-control border border-control-border bg-surface px-3 text-ui leading-ui text-text hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus hidden md:inline-flex xl:hidden"
            aria-expanded={tabletOutlineOpen}
            onClick={() => setTabletOutlineOpen((open) => !open)}
          >
            {tabletOutlineOpen ? "Hide outline" : "Show outline"}
          </button>
          <button
            type="button"
            className="inline-flex min-h-11 items-center rounded-control border border-control-border bg-surface px-3 text-ui leading-ui text-text hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus xl:hidden"
            aria-label="Open tools drawer"
            onClick={() => setDrawerPane("tools")}
          >
            Tools
          </button>
          <button
            type="button"
            className="hidden xl:inline-flex min-h-11 items-center rounded-control border border-control-border bg-surface px-3 text-ui leading-ui text-text hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
            aria-pressed={!outlineCollapsed}
            onClick={() => setOutlineCollapsed((collapsed) => !collapsed)}
          >
            {outlineCollapsed ? "Show outline pane" : "Collapse outline"}
          </button>
          <button
            type="button"
            className="hidden xl:inline-flex min-h-11 items-center rounded-control border border-control-border bg-surface px-3 text-ui leading-ui text-text hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
            aria-pressed={!toolsCollapsed}
            onClick={() => setToolsCollapsed((collapsed) => !collapsed)}
          >
            {toolsCollapsed ? "Show tools pane" : "Collapse tools"}
          </button>
        </div>
      </div>

      {tabletOutlineOpen ? (
        <section
          data-pane="outline-tablet"
          aria-label="Document outline"
          className="rounded-surface border border-border bg-surface p-3 hidden md:block xl:hidden"
        >
          <OutlinePane
            entries={outline}
            activeBlockId={currentBlock?.blockId ?? null}
            onNavigate={handleOutlineNavigate}
          />
        </section>
      ) : null}

      <div
        className="grid gap-4 xl:grid-cols-[16rem_minmax(0,1fr)_18rem]"
        data-testid="editor-grid"
      >
        <aside
          data-pane="outline"
          aria-label="Document outline"
          className={cn("hidden xl:block min-w-0", outlineCollapsed && "xl:hidden")}
        >
          <div className="rounded-surface border border-border bg-surface p-3">
            <p className="font-ui text-ui leading-ui font-medium text-text mb-2">Outline</p>
            <OutlinePane
              entries={outline}
              activeBlockId={currentBlock?.blockId ?? null}
              onNavigate={handleOutlineNavigate}
            />
          </div>
        </aside>

        <section data-pane="paper" className="min-w-0">
          <div ref={paperRef} className="relative rounded-surface border border-border bg-surface p-6">
            {editor ? (
              <EditorContent editor={editor} />
            ) : (
              <div className="flex flex-col gap-3" role="status" aria-label="Loading editor">
                <Skeleton className="h-8 w-2/3" />
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-24 w-full" />
              </div>
            )}
            {editor && slashMenu ? (
              <SlashMenu
                coordinates={slashMenu.coordinates}
                boundaryWidth={null}
                onInsert={handleInsert}
                onClose={() => {
                  setSlashMenu(null);
                  editor.commands.focus();
                }}
              />
            ) : null}
          </div>
        </section>

        <aside
          data-pane="tools"
          aria-label="Block properties"
          className={cn("hidden xl:block min-w-0", toolsCollapsed && "xl:hidden")}
        >
          <div className="rounded-surface border border-border bg-surface p-3">
            <p className="font-ui text-ui leading-ui font-medium text-text mb-2">Properties</p>
            {editor ? (
              <ContextPane editor={editor} currentBlock={currentBlock} onTableChange={handleTableChange} />
            ) : null}
          </div>
        </aside>
      </div>

      <Drawer
        open={drawerPane === "outline"}
        onOpenChange={(open) => setDrawerPane(open ? "outline" : null)}
      >
        <DrawerContent>
          <div className="max-h-[70dvh] overflow-y-auto pb-2">
            <p className="font-ui text-ui leading-ui font-medium text-text">Outline</p>
            <OutlinePane
              entries={outline}
              activeBlockId={currentBlock?.blockId ?? null}
              onNavigate={handleOutlineNavigate}
              className="mt-2"
            />
          </div>
        </DrawerContent>
      </Drawer>

      <Drawer
        open={drawerPane === "tools"}
        onOpenChange={(open) => setDrawerPane(open ? "tools" : null)}
      >
        <DrawerContent>
          <div className="max-h-[70dvh] overflow-y-auto pb-2">
            <p className="font-ui text-ui leading-ui font-medium text-text">Properties</p>
            {editor ? (
              <ContextPane
                editor={editor}
                currentBlock={currentBlock}
                onTableChange={handleTableChange}
              />
            ) : null}
          </div>
        </DrawerContent>
      </Drawer>

      <DeleteConfirmationDialog
        open={deleteRequest !== null}
        targetLabel={deleteRequest?.targetLabel ?? "block"}
        targetIndex={deleteRequest?.targetIndex ?? -1}
        dependents={deleteRequest?.dependents ?? []}
        onConfirm={confirmDelete}
        onOpenChange={(open) => {
          if (!open) {
            setDeleteRequest(null);
          }
        }}
      />

      <ConflictRecoveryDialog
        open={conflictDialogOpen}
        onOpenChange={(open) => {
          if (!open) {
            handleConflictDismiss();
          }
        }}
        localRevision={controller.status.kind === "conflict" ? controller.status.revision : controller.revision}
        serverRevision={controller.status.kind === "conflict" ? controller.status.serverRevision : null}
        busy={conflictBusy}
        actionError={conflictActionError}
        onOverwrite={handleConflictOverwrite}
        onReloadServerVersion={() => void handleConflictReload()}
        onDownloadLocalCopy={handleDownloadLocalCopy}
        onSaveAsNewCopy={() => void handleConflictNewCopy()}
      />
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Helpers
// --------------------------------------------------------------------------- */

/** Title of the "save as new document" conflict-recovery copy. */
function recoveredCopyTitle(original: string): string {
  const suffix = " (recovered copy)";
  const room = DOCUMENT_TITLE_MAX_LENGTH - suffix.length;
  const base = original.length > room ? `${original.slice(0, room - 1)}…` : original;
  return `${base}${suffix}`;
}

function describeRecoveryActionError(error: unknown, fallback: string): string {
  if (error instanceof DocumentApiError) {
    if (error.status === 401) {
      return "Your session has expired. Sign in again and retry — your local content is kept.";
    }
    if (error.status === 404) {
      return "The document no longer exists on the server. Download a local copy to preserve your edits.";
    }
    return error.message || fallback;
  }
  return fallback;
}

function buildDeleteRequest(editor: Editor, index: number): DeleteRequest | null {
  const snapshot = canonicalSnapshot(editor);
  const block = snapshot.content[index];
  if (!block) {
    return null;
  }
  return {
    targetIndex: index,
    targetLabel: blockLabel(block.type),
    dependents: findDependentBlocks(snapshot.content, block.attrs.block_id),
  };
}

function computeSlashCoordinates(
  editor: NonNullable<ReturnType<typeof useEditor>>,
  position: number,
  container: HTMLElement | null,
): { left: number; top: number } | null {
  if (!container) {
    return null;
  }
  try {
    const coords = editor.view.coordsAtPos(position);
    const rect = container.getBoundingClientRect();
    return { left: coords.left - rect.left, top: coords.bottom - rect.top + 4 };
  } catch {
    return null;
  }
}
