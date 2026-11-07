"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { DocumentApiError, listDocuments } from "./documents-api";
import type { DocumentSummary } from "./documents-schema";

/**
 * Owner-scoped document list state (NI-023). All data comes from
 * GET /api/documents through the verified session — the client never sends a
 * user identifier and never reorders, filters or fabricates rows locally:
 * search (`q`), the updated_at-DESC order and pagination cursors are the
 * API's. Failures keep the previously loaded rows and stay retryable.
 */

export type ListStatus = "loading" | "ready" | "error";

export interface DocumentListState {
  /** Current rows, exactly as the API returned them (updated_at DESC). */
  items: DocumentSummary[];
  status: ListStatus;
  /** Human-readable load failure, null while the last load succeeded. */
  loadError: string | null;
  /** True while a first-page reload (search change or refresh) is in flight. */
  refreshing: boolean;
  /** True while a next-page load is in flight. */
  loadingMore: boolean;
  /** Opaque next-page cursor from the API; null when there are no more rows. */
  nextCursor: string | null;
  /** The submitted search query currently applied to the loaded list. */
  activeQuery: string;
  submitSearch: (query: string) => void;
  clearSearch: () => void;
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
        const page = await listDocuments({ query: activeQuery || undefined });
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
  }, [activeQuery, refreshKey]);

  const submitSearch = useCallback((query: string) => {
    // The applied query is the trimmed input, bounded like the API's `q`.
    setRefreshing(true);
    setActiveQuery(query.trim().slice(0, 200));
  }, []);

  const clearSearch = useCallback(() => {
    setRefreshing(true);
    setActiveQuery("");
  }, []);

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
        const page = await listDocuments({ query: activeQuery || undefined, cursor: nextCursor });
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
  }, [activeQuery, loadingMore, nextCursor]);

  return {
    items,
    status,
    loadError,
    refreshing,
    loadingMore,
    nextCursor,
    activeQuery,
    submitSearch,
    clearSearch,
    loadMore,
    refresh,
  };
}
