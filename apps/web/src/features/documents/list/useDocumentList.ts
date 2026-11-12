"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { DocumentApiError, listDocuments } from "./documents-api";
import type { DocumentSummary } from "./documents-schema";

/**
 * Owner-scoped document list state (NI-023). All data comes from
 * GET /api/documents through the verified session — the client never sends a
 * user identifier and never reorders, filters or fabricates rows locally:
 * search (`q`), the organization filters (`tag`, `favorite` — NI-072), the
 * updated_at-DESC order and pagination cursors are the API's. Failures keep
 * the previously loaded rows and stay retryable.
 */

export type ListStatus = "loading" | "ready" | "error";

export interface DocumentListState {
  /** Current rows, exactly as the API returned them (updated_at DESC). */
  items: DocumentSummary[];
  status: ListStatus;
  /** Human-readable load failure, null while the last load succeeded. */
  loadError: string | null;
  /** True while a first-page reload (search or filter change) is in flight. */
  refreshing: boolean;
  /** True while a next-page load is in flight. */
  loadingMore: boolean;
  /** Opaque next-page cursor from the API; null when there are no more rows. */
  nextCursor: string | null;
  /** The submitted search query currently applied to the loaded list. */
  activeQuery: string;
  /** The tag filter currently applied (normalized exact tag, or null). */
  activeTag: string | null;
  /** True while the list is filtered to favorites only. */
  favoriteOnly: boolean;
  submitSearch: (query: string) => void;
  clearSearch: () => void;
  applyTagFilter: (tag: string | null) => void;
  toggleFavoriteOnly: () => void;
  /** Merge server-confirmed organization metadata into one loaded row. */
  applyOrganization: (update: { documentId: string; tags?: string[]; favorite?: boolean }) => void;
  loadMore: () => void;
  refresh: () => void;
}

function describeLoadError(error: unknown): string {
  if (error instanceof DocumentApiError) {
    if (error.status === 401) {
      return "Your session has expired. Sign in again to see your documents.";
    }
    if (error.status === 403) {
      return "Your account cannot load documents right now. Contact the operator if this persists.";
    }
    return "Your documents could not be loaded. Nothing was changed.";
  }
  return "Your documents could not be loaded. Nothing was changed.";
}

export function useDocumentList(): DocumentListState {
  const [activeQuery, setActiveQuery] = useState("");
  const [activeTag, setActiveTag] = useState<string | null>(null);
  const [favoriteOnly, setFavoriteOnly] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [items, setItems] = useState<DocumentSummary[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [status, setStatus] = useState<ListStatus>("loading");
  const [loadError, setLoadError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  // Monotonic epoch of first-page requests: every effect run increments it,
  // so a slower "load more" response from a superseded page is discarded.
  const firstPageEpoch = useRef(0);

  useEffect(() => {
    const epoch = ++firstPageEpoch.current;
    let cancelled = false;
    void (async () => {
      try {
        const page = await listDocuments({
          query: activeQuery || undefined,
          tags: activeTag ? [activeTag] : undefined,
          favorite: favoriteOnly ? true : undefined,
        });
        if (cancelled || epoch !== firstPageEpoch.current) {
          return;
        }
        setItems(page.items);
        setNextCursor(page.nextCursor);
        setStatus("ready");
        setLoadError(null);
      } catch (error) {
        if (cancelled || epoch !== firstPageEpoch.current) {
          return;
        }
        setLoadError(describeLoadError(error));
        setStatus("error");
      } finally {
        if (!cancelled && epoch === firstPageEpoch.current) {
          setRefreshing(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [activeQuery, activeTag, favoriteOnly, refreshKey]);

  const submitSearch = useCallback((query: string) => {
    // The applied query is the trimmed input, bounded like the API's `q`.
    setRefreshing(true);
    setActiveQuery(query.trim().slice(0, 200));
  }, []);

  const clearSearch = useCallback(() => {
    setRefreshing(true);
    setActiveQuery("");
  }, []);

  const applyTagFilter = useCallback((tag: string | null) => {
    // The filter value is the normalized tag exactly as the list returned it;
    // the API matches the stored metadata, the client never pre-filters.
    setRefreshing(true);
    setActiveTag(tag);
  }, []);

  const toggleFavoriteOnly = useCallback(() => {
    setRefreshing(true);
    setFavoriteOnly((current) => !current);
  }, []);

  const applyOrganization = useCallback(
    (update: { documentId: string; tags?: string[]; favorite?: boolean }) => {
      // Only ever called with the server's own PATCH response (or an exact
      // revert of the previous server state) — a row is updated in place,
      // never reordered, refiltered or fabricated.
      setItems((previous) => previous.map((item) => item.id === update.documentId
        ? {
            ...item,
            ...(update.tags !== undefined ? { tags: update.tags } : {}),
            ...(update.favorite !== undefined ? { favorite: update.favorite } : {}),
          }
        : item));
    },
    [],
  );

  const refresh = useCallback(() => {
    setRefreshing(true);
    setRefreshKey((key) => key + 1);
  }, []);

  const loadMore = useCallback(() => {
    if (loadingMore || nextCursor === null) {
      return;
    }
    setLoadingMore(true);
    const epoch = firstPageEpoch.current;
    void (async () => {
      try {
        const page = await listDocuments({
          query: activeQuery || undefined,
          tags: activeTag ? [activeTag] : undefined,
          favorite: favoriteOnly ? true : undefined,
          cursor: nextCursor,
        });
        if (epoch !== firstPageEpoch.current) {
          return;
        }
        setItems((previous) => [...previous, ...page.items]);
        setNextCursor(page.nextCursor);
      } catch {
        // A failed page load keeps the already-loaded rows; the next attempt
        // can resume from the same cursor.
      } finally {
        if (epoch === firstPageEpoch.current) {
          setLoadingMore(false);
        }
      }
    })();
  }, [activeQuery, activeTag, favoriteOnly, loadingMore, nextCursor]);

  return {
    items,
    status,
    loadError,
    refreshing,
    loadingMore,
    nextCursor,
    activeQuery,
    activeTag,
    favoriteOnly,
    submitSearch,
    clearSearch,
    applyTagFilter,
    toggleFavoriteOnly,
    applyOrganization,
    loadMore,
    refresh,
  };
}
