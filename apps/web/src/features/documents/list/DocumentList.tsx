"use client";

import Link from "next/link";
import { useRef, useState, type MouseEventHandler } from "react";

import { Skeleton } from "@/components/data-state/Skeleton";
import { PageIntro } from "@/components/layout/PageIntro";
import { ProductIcon } from "@/components/layout/ProductIcon";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import {
  CreateDocumentDialog,
  DeleteDocumentDialog,
  RenameDocumentDialog,
} from "./DocumentDialogs";
import type { DocumentSummary } from "./documents-schema";
import { formatUpdated } from "./format";
import { useDocumentList } from "./useDocumentList";

/**
 * My Research list (NI-023): the usable entry point to persisted documents.
 *
 * Every row comes from GET /api/documents through the verified session — the
 * component never sends a user identifier, never fabricates or filters rows
 * client-side, and shows honest empty, loading, error and pending states.
 * The first page (updated_at DESC) is the recent-documents view; the workspace
 * Home (NI-024) will reuse the NI-022 home aggregation instead of this list.
 *
 * Mutation results: create navigates to the persisted document route
 * /workspace/research/[documentId]; rename/delete refresh the list because a
 * revision bumps updated_at and the server owns the order. A stale revision
 * (409) keeps the item visible with an error and refreshes the current
 * revision — nothing is silently retried or overwritten.
 */

const REVISION_CONFLICT_MESSAGE =
  "This document changed elsewhere while you were working. The list has been refreshed with the current revisions — try again.";

export function DocumentList() {
  const returnFocus = useRef<HTMLElement | null>(null);
  const newButton = useRef<HTMLButtonElement | null>(null);
  function restoreDialogFocus(event: Event) {
    event.preventDefault();
    const target = returnFocus.current;
    if (target?.isConnected) target.focus();
    else newButton.current?.focus();
  }

  const openCreate: MouseEventHandler<HTMLButtonElement> = (event) => {
    returnFocus.current = event.currentTarget;
    setCreateOpen(true);
  };
  const list = useDocumentList();
  const [searchInput, setSearchInput] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [renameTarget, setRenameTarget] = useState<DocumentSummary | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<DocumentSummary | null>(null);
  const [itemError, setItemError] = useState<{ id: string; message: string } | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  function handleCreated() {
    // The dialog navigates to the persisted document route after the API
    // confirms creation; the list only drops any stale action notice.
    setNotice(null);
    setItemError(null);
  }

  function handleRenamed(updated: DocumentSummary) {
    setNotice(`Title updated for “${updated.title}”. The list was refreshed.`);
    setItemError(null);
    list.refresh();
  }

  function handleDeleted() {
    setNotice("Document deleted.");
    setItemError(null);
    list.refresh();
  }

  function handleRevisionConflict(documentId: string) {
    setNotice(null);
    setItemError({ id: documentId, message: REVISION_CONFLICT_MESSAGE });
    list.refresh();
  }

  function handleSearchSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setNotice(null);
    setItemError(null);
    list.submitSearch(searchInput);
  }

  function handleClearSearch() {
    setSearchInput("");
    setNotice(null);
    setItemError(null);
    list.clearSearch();
  }

  const hasQuery = list.activeQuery.length > 0;

  return (
    <div>
      <PageIntro
        compact
        eyebrow="My Research"
        title="Your research, connected."
        description="A place for questions, evidence and the conclusions you are still testing."
        action={<Button ref={newButton} onClick={openCreate}>New document <ProductIcon name="arrow" /></Button>}
      />

      <div className="mt-6 flex flex-wrap items-end justify-between gap-3">
        <form onSubmit={handleSearchSubmit} className="flex flex-wrap items-end gap-2" noValidate>
          <div className="flex min-w-48 flex-col gap-1.5">
            <Label htmlFor="document-search">Search by title</Label>
            <Input
              id="document-search"
              type="search"
              value={searchInput}
              maxLength={200}
              placeholder="Title contains…"
              className="rounded-full text-ui"
              autoComplete="off"
              onChange={(event) => setSearchInput(event.target.value)}
            />
          </div>
          <div className="flex flex-wrap gap-2">
            <Button type="submit" variant="secondary">
              Search
            </Button>
            {hasQuery || searchInput ? (
              <Button type="button" variant="quiet" onClick={handleClearSearch}>
                Clear
              </Button>
            ) : null}
          </div>
        </form>
        <p className="text-metadata text-text-secondary" aria-label="Sort order">Sorted by last update, newest first</p>
      </div>

      {list.status === "loading" ? (
        <div className="mt-6 flex flex-col gap-3" role="status" aria-label="Loading documents">
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-20 w-full" />
        </div>
      ) : null}

      {list.status === "error" ? (
        <div className="mt-6">
          <p role="alert" className="text-ui leading-ui text-danger font-medium">
            {list.loadError}
          </p>
          {list.loadError?.includes("session has expired") ? (
            <p className="text-body leading-body text-text-secondary mt-2">
              <Link
                href="/login"
                className="underline underline-offset-2 hover:text-text focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
              >
                Sign in again
              </Link>
            </p>
          ) : (
            <Button type="button" variant="secondary" className="mt-3" onClick={list.refresh}>
              Try again
            </Button>
          )}
        </div>
      ) : null}

      {list.status === "ready" ? (
        <>
          {notice ? (
            <p role="status" className="text-ui leading-ui text-accent font-medium mt-4">
              {notice}
            </p>
          ) : null}

          {list.items.length === 0 && !hasQuery ? (
            <FirstUseExplanation onCreate={openCreate} />
          ) : null}

          {list.items.length === 0 && hasQuery ? (
            <div className="paper-panel mt-6 p-8 text-center">
              <ProductIcon name="search" className="mx-auto mb-4 size-7 text-accent" />
              <p role="status" className="font-serif text-heading font-medium text-text">
                No documents match your search.
              </p>
              <p className="text-body leading-body text-text-secondary mt-2">
                Nothing titled “{list.activeQuery}” is in your workspace. Titles are matched as
                case-insensitive substrings.
              </p>
              <Button type="button" variant="secondary" className="mt-3" onClick={handleClearSearch}>
                Clear search
              </Button>
            </div>
          ) : null}

          {list.items.length > 0 ? (
            <ul className="paper-panel mt-6 divide-y divide-border" aria-busy={list.refreshing || undefined}>
              {list.items.map((item) => (
                <DocumentListItem
                  key={item.id}
                  item={item}
                  error={itemError?.id === item.id ? itemError.message : null}
                  onRename={(event) => {
                    returnFocus.current = event.currentTarget;
                    setRenameTarget(item);
                  }}
                  onDelete={(event) => {
                    returnFocus.current = event.currentTarget;
                    setDeleteTarget(item);
                  }}
                />
              ))}
            </ul>
          ) : null}

          {list.nextCursor !== null && list.items.length > 0 ? (
            <div className="mt-6">
              <Button
                type="button"
                variant="secondary"
                pending={list.loadingMore}
                onClick={list.loadMore}
              >
                Show more documents
              </Button>
            </div>
          ) : null}
        </>
      ) : null}

      {createOpen ? (
        <CreateDocumentDialog onOpenChange={setCreateOpen} onCreated={handleCreated} onCloseAutoFocus={restoreDialogFocus} />
      ) : null}
      {renameTarget ? (
        <RenameDocumentDialog
          key={renameTarget.id}
          target={renameTarget}
          onOpenChange={(open) => {
            if (!open) {
              setRenameTarget(null);
            }
          }}
          onRenamed={handleRenamed}
          onRevisionConflict={handleRevisionConflict}
          onCloseAutoFocus={restoreDialogFocus}
        />
      ) : null}
      {deleteTarget ? (
        <DeleteDocumentDialog
          key={deleteTarget.id}
          target={deleteTarget}
          onOpenChange={(open) => {
            if (!open) {
              setDeleteTarget(null);
            }
          }}
          onDeleted={handleDeleted}
          onRevisionConflict={handleRevisionConflict}
          onCloseAutoFocus={restoreDialogFocus}
        />
      ) : null}
    </div>
  );
}

function DocumentListItem({
  item,
  error,
  onRename,
  onDelete,
}: {
  item: DocumentSummary;
  error: string | null;
  onRename: MouseEventHandler<HTMLButtonElement>;
  onDelete: MouseEventHandler<HTMLButtonElement>;
}) {
  return (
    <li className="px-5 py-3.5">
      <div className="flex flex-wrap items-center gap-3">
        <span className="grid size-10 shrink-0 place-items-center rounded-control bg-sage text-accent">
          <ProductIcon name="document" className="size-5" />
        </span>
        <div className="min-w-0 flex-1 basis-48">
          <Link
            href={`/workspace/research/${item.id}`}
            className="text-ui font-semibold text-text underline-offset-2 hover:underline [overflow-wrap:anywhere]"
          >
            {item.title}
          </Link>
          <p className="text-metadata leading-metadata text-text-secondary mt-1">
            Updated{" "}
            <time dateTime={item.updated_at}>{formatUpdated(item.updated_at)}</time>
            {" · "}Revision {item.revision}
            {" · "}
            {item.progress.headings} headings, {item.progress.charts} charts,{" "}
            {item.progress.insights} insights
          </p>
        </div>
        <div className="flex flex-wrap gap-2 shrink-0">
          <Button type="button" variant="secondary" onClick={onRename}>
            Rename
          </Button>
          <Button type="button" variant="secondary" onClick={onDelete}>
            Delete
          </Button>
        </div>
      </div>
      {error ? (
        <p role="alert" className="text-ui leading-ui text-danger font-medium mt-3">
          {error}
        </p>
      ) : null}
    </li>
  );
}

/**
 * First-use explanation (UI_SCREEN_SPECIFICATIONS: "First-use explanation and
 * create action instead of fake docs"). Shown only for a genuinely empty
 * owner-scoped list; no sample documents are ever injected.
 */
export function FirstUseExplanation({ onCreate }: { onCreate: MouseEventHandler<HTMLButtonElement> }) {
  return (
    <div
      role="note"
      aria-label="About research documents"
      className="paper-panel mt-6 p-9 text-center"
    >
      <ProductIcon name="document" className="mx-auto mb-3 size-7 text-accent" />
      <p className="font-serif text-heading font-medium text-text">Starting your research</p>
      <div className="mx-auto mt-2 flex max-w-[55ch] flex-col gap-2 text-ui text-text-secondary">
        <p>
          A research document is your private analysis notebook: you write the question, collect
          charts, insights and evidence for one hypothesis, and every save creates an immutable,
          server-side revision you can look back at.
        </p>
      </div>
      <Button type="button" className="mt-4" onClick={onCreate}>
        Create your first document
      </Button>
    </div>
  );
}
