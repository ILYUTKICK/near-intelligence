"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { formatUpdated } from "@/features/documents/list/format";
import { ShareViewer } from "@/features/shares/ShareViewer";
import { shareProjectionSchema, type ShareProjectionPayload } from "@/features/shares/share-schema";
import {
  createShare,
  listShares,
  previewShare,
  revokeShare,
  ShareApiError,
  type ShareConsent,
  type ShareCreatedResponse,
  type SharePreviewResponse,
  type ShareSummaryResponse,
} from "./share-api";

/**
 * Owner sharing dialog for one acknowledged revision (NI-060, ADR-021).
 *
 * The consent flow is explicit and previewed: the dialog fetches the EXACT
 * publication projection from the server (`GET .../shares/preview`), renders
 * what will be visible and what will not, and the create button stays
 * disabled until the owner ticks the consent checkbox that names the
 * revision and the visible scope. The share link (its token) is shown ONCE
 * after the create — the API stores only the token's hash, so the dialog can
 * never show it again and says so. Existing links are listed with their
 * honest computed lifecycle state (active/expired/revoked) and can be
 * revoked (the API clears the stored bytes; every holder is denied on their
 * next request).
 *
 * All mutations require a clean (acknowledged) editor state — the Share
 * button is disabled while the workbench is dirty, exactly like Export.
 */

type Phase = "loading" | "ready" | "creating" | "created" | "error";

const EXPIRY_OPTIONS = [
  { value: "never", label: "No expiry (revocable any time)" },
  { value: "1", label: "1 day" },
  { value: "7", label: "7 days" },
  { value: "30", label: "30 days" },
] as const;

type ExpiryValue = (typeof EXPIRY_OPTIONS)[number]["value"];

export interface ShareDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  documentId: string;
  /** The acknowledged revision the clean editor currently holds. */
  revision: number;
  canPublish?: boolean;
  onAnnounce?: (message: string) => void;
  /** Focus-return target (the workbench Share button), NI-064 pattern. */
  returnFocusRef?: React.RefObject<HTMLButtonElement | null>;
}

function describeError(error: unknown): string {
  if (error instanceof ShareApiError) {
    if (error.status === 401) {
      return "Your session has expired. Sign in again and retry.";
    }
    if (error.status === 404) {
      return "The document does not exist for your account.";
    }
    if (error.code === "REVISION_NOT_ACKNOWLEDGED"
      || error.code === "PREVIEW_MISMATCH") {
      return "The document changed since the preview was shown. Review the fresh preview and consent again.";
    }
    return error.message;
  }
  return "The share could not be created. Try again.";
}

function expiryDate(value: ExpiryValue): string | null {
  if (value === "never") return null;
  const days = Number(value);
  return new Date(Date.now() + days * 86_400_000).toISOString();
}

function shareLink(path: string | null): string | null {
  if (!path || typeof window === "undefined") return null;
  return `${window.location.origin}${path}`;
}

export function ShareDialog({
  open,
  onOpenChange,
  documentId,
  revision,
  canPublish = true,
  onAnnounce,
  returnFocusRef,
}: ShareDialogProps) {
  const [phase, setPhase] = useState<Phase>("loading");
  const [errorText, setErrorText] = useState<string | null>(null);
  const [preview, setPreview] = useState<(Omit<SharePreviewResponse, "projection"> & { projection: ShareProjectionPayload }) | null>(null);
  const [consented, setConsented] = useState(false);
  const [expiry, setExpiry] = useState<ExpiryValue>("7");
  const [created, setCreated] = useState<ShareCreatedResponse | null>(null);
  const [copied, setCopied] = useState(false);
  const [shares, setShares] = useState<ShareSummaryResponse[] | null>(null);
  const [revokeTarget, setRevokeTarget] = useState<string | null>(null);
  const [refreshWarning, setRefreshWarning] = useState<string | null>(null);
  const runRef = useRef(0);
  const request = useRef<AbortController | null>(null);
  const attempt = useRef<{ key: string; consent: ShareConsent } | null>(null);
  const mutationInFlight = useRef(false);

  const startRequest = useCallback(() => {
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    return { signal: controller.signal, run: ++runRef.current };
  }, []);

  const resetPreview = useCallback(() => {
    setPhase("loading");
    setErrorText(null);
    setRefreshWarning(null);
    setConsented(false);
    setCreated(null);
    setCopied(false);
    setPreview(null);
    setShares(null);
  }, []);

  const load = useCallback(() => {
    const { signal, run } = startRequest();
    return Promise.allSettled([
      previewShare(documentId, signal),
      listShares(documentId, signal),
    ]).then(([fetchedPreview, fetchedShares]) => {
      if (runRef.current !== run) return;
      if (fetchedShares.status === "fulfilled") setShares(fetchedShares.value);
      else setRefreshWarning("The existing links could not be loaded. Retry to manage them.");
      if (fetchedPreview.status === "rejected") throw fetchedPreview.reason;
      const projection = shareProjectionSchema.safeParse(fetchedPreview.value.projection);
      if (!projection.success || fetchedPreview.value.document_id !== documentId
        || projection.data.document.revision !== fetchedPreview.value.revision) {
        throw new ShareApiError(502, "INVALID_PREVIEW", "The publication preview could not be verified.");
      }
      setPreview({ ...fetchedPreview.value, projection: projection.data });
      setPhase("ready");
    }).catch((error: unknown) => {
      if (runRef.current !== run) return;
      setErrorText(describeError(error));
      setPhase("error");
    });
  }, [documentId, startRequest]);

  useEffect(() => {
    if (!open) return;
    void load();
    return () => {
      request.current?.abort();
      runRef.current += 1;
      mutationInFlight.current = false;
    };
  }, [open, load]);

  const previewStale = preview !== null && (preview.document_id !== documentId
    || preview.revision !== revision || !canPublish);

  const handleCreate = useCallback(async () => {
    if (!preview || previewStale || !consented || mutationInFlight.current) return;
    mutationInFlight.current = true;
    const { signal, run } = startRequest();
    const pending = attempt.current ?? {
      key: crypto.randomUUID(),
      consent: {
        acknowledged_revision: preview.revision,
        preview_sha256: preview.projection_sha256,
        visible_scope: preview.scope,
        expires_at: expiryDate(expiry),
      },
    };
    attempt.current = pending;
    setPhase("creating");
    setErrorText(null);
    setRefreshWarning(null);
    try {
      const response = await createShare(documentId, pending.consent, pending.key, signal);
      if (runRef.current !== run) return;
      attempt.current = null;
      setCreated(response);
      setCopied(false);
      setPhase("created");
      onAnnounce?.(response.share_path
        ? "The share link was created. It is shown once — copy it now."
        : "This request already created a share. Its link cannot be shown again.");
    } catch (error) {
      if (runRef.current !== run) return;
      const definitive = error instanceof ShareApiError && error.status < 500;
      if (definitive) attempt.current = null;
      setErrorText(describeError(error));
      setPhase("error");
      return;
    } finally {
      if (runRef.current === run) mutationInFlight.current = false;
    }
    try {
      const current = await listShares(documentId, signal);
      if (runRef.current === run) setShares(current);
    } catch {
      if (runRef.current === run) setRefreshWarning("The link was recorded. The existing links list could not be refreshed.");
    }
  }, [consented, documentId, expiry, onAnnounce, preview, previewStale, startRequest]);

  const handleCopy = useCallback(async () => {
    const link = shareLink(created?.share_path ?? null);
    if (!link) return;
    try {
      await navigator.clipboard.writeText(link);
      setCopied(true);
      onAnnounce?.("The share link was copied to the clipboard.");
    } catch {
      // Clipboard permission denied: the link stays visible for a manual
      // copy (this dialog state is its only display).
      onAnnounce?.("Automatic copy failed — select the link text and copy it manually.");
    }
  }, [created, onAnnounce]);

  const handleRevoke = useCallback(async (shareId: string) => {
    const { signal, run } = startRequest();
    setRefreshWarning(null);
    try {
      await revokeShare(documentId, shareId, signal);
      if (runRef.current !== run) return;
      setShares((items) => items?.map((item) => item.id === shareId ? { ...item, status: "revoked" } : item) ?? null);
      setCreated((item) => item?.id === shareId ? { ...item, status: "revoked", share_path: null, share_token: null } : item);
      setRevokeTarget(null);
      onAnnounce?.("The share was revoked. Everyone with the link is denied from now on.");
    } catch (error) {
      if (runRef.current !== run) return;
      setRevokeTarget(null);
      setRefreshWarning(describeError(error));
    }
  }, [documentId, onAnnounce, startRequest]);

  const handleClose = useCallback((next: boolean) => {
    if (!next) {
      if (phase === "creating") return;
      request.current?.abort();
      runRef.current += 1;
      attempt.current = null;
      resetPreview();
      onAnnounce?.("Share dialog closed. Existing links stay active until revoked or expired.");
    }
    onOpenChange(next);
  }, [onAnnounce, onOpenChange, phase, resetPreview]);

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent
        data-testid="share-dialog"
        aria-describedby="share-dialog-description"
        className="max-h-[85vh] overflow-y-auto"
        onCloseAutoFocus={(event) => {
          if (returnFocusRef?.current) {
            event.preventDefault();
            returnFocusRef.current.focus();
          }
        }}
      >
        <DialogTitle>Share this revision (read-only)</DialogTitle>
        <DialogDescription id="share-dialog-description">
          Publishing creates a secret read-only link to the frozen revision on
          the server. The link never refreshes and you can revoke it at any
          time.
        </DialogDescription>

        {refreshWarning ? <p role="alert" className="mt-4 text-ui text-warning">{refreshWarning}</p> : null}
        {phase === "loading" ? (
          <p role="status" data-testid="share-loading" className="text-ui leading-ui text-text mt-4">
            Preparing the publication preview…
          </p>
        ) : null}

        {phase === "error" && errorText ? (
          <div className="mt-4">
            <p role="alert" data-testid="share-error" className="text-ui leading-ui text-danger font-medium">
              {errorText}
            </p>
            <div className="mt-3">
              <Button variant="secondary" onClick={() => {
                if (attempt.current && !previewStale) void handleCreate();
                else { attempt.current = null; resetPreview(); void load(); }
              }}
                data-testid="share-error-retry">
                Try again
              </Button>
            </div>
          </div>
        ) : null}

        {preview !== null && (phase === "ready" || phase === "creating") ? (
          <section className="mt-4" aria-label="Publication preview">
            <h3 className="font-ui text-ui font-medium text-text">
              This is exactly what the link shows
            </h3>
            {previewStale ? (
              <p role="alert" data-testid="share-preview-stale" className="text-ui leading-ui text-warning mt-2">
                Save your edits and refresh the preview before publishing.
                This preview is revision {preview.revision} and the editor is at revision {revision}.
              </p>
            ) : null}
            <ul className="mt-2 text-ui leading-ui text-text" data-testid="share-preview-visible">
              <li>Title “{preview.projection.document.title}”, revision {preview.projection.document.revision} ({formatUpdated(preview.projection.document.created_at)})</li>
              <li>{preview.scope.chart_blocks} chart{preview.scope.chart_blocks === 1 ? "" : "s"} with their frozen data, exact-value tables and source references</li>
              <li>{preview.scope.data_table_blocks} data table{preview.scope.data_table_blocks === 1 ? "" : "s"}{preview.scope.insight_blocks > 0 ? `, ${preview.scope.insight_blocks} insight card${preview.scope.insight_blocks === 1 ? "" : "s"}` : ""}</li>
              <li>{preview.scope.source_references} registered data source{preview.scope.source_references === 1 ? "" : "s"} (name only)</li>
            </ul>
            <h3 className="font-ui text-ui font-medium text-text mt-3">Never included</h3>
            <ul className="mt-2 text-ui leading-ui text-text-secondary" data-testid="share-preview-hidden">
              <li>Your identity and account details</li>
              <li>Private document and editor metadata (internal ids, authorship timestamps, evidence notes)</li>
              <li>Any later edits — the link is frozen at this revision</li>
            </ul>
            <p className="mt-2 text-metadata leading-metadata text-text-secondary">
              {preview.projection.document.limitations}
            </p>
            <details className="mt-4 rounded-control border border-border p-3">
              <summary className="cursor-pointer text-ui font-medium">Read the exact shared content</summary>
              <ShareViewer projection={preview.projection} embedded />
            </details>
          </section>
        ) : null}

        {preview !== null && (phase === "ready" || phase === "creating") ? (
          <section className="mt-4" aria-label="Consent">
            <div className="flex flex-wrap items-end gap-3">
              <div className="min-w-40">
                <Label htmlFor="share-expiry">Link expires</Label>
                <select id="share-expiry" data-testid="share-expiry"
                  className="mt-1 block w-full rounded-surface border-2 border-panel-border bg-surface p-2 text-ui text-text"
                  value={expiry}
                  onChange={(event) => {
                    setExpiry(event.target.value as ExpiryValue);
                    setConsented(false);
                  }}>
                  {EXPIRY_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </select>
              </div>
            </div>
            <label className="mt-3 flex items-start gap-2 text-ui leading-ui text-text">
              <input type="checkbox" data-testid="share-consent" className="mt-1"
                checked={consented}
                onChange={(event) => setConsented(event.target.checked)} />
              <span>
                I consent to publishing revision {preview.revision} with the
                visible scope listed above as a secret read-only link that
                anyone holding it can open.
              </span>
            </label>
            <div className="mt-3">
              <Button data-testid="share-create" pending={phase === "creating"}
                disabled={!consented || previewStale || phase === "creating"}
                onClick={() => void handleCreate()}>
                Create share link
              </Button>
            </div>
          </section>
        ) : null}

        {phase === "created" && created?.share_path ? (
          <section className="mt-4" aria-label="Share link" data-testid="share-created">
            <p role="status" className="text-ui leading-ui font-medium text-text">
              The share link was created. It is shown <strong>only this once</strong> —
              copy it now; the server stores its hash, so it cannot be displayed
              again.
            </p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <Input readOnly data-testid="share-link"
                value={shareLink(created.share_path ?? null) ?? ""}
                aria-label="Share link"
                onFocus={(event) => event.currentTarget.select()} />
              <Button variant="secondary" data-testid="share-copy" onClick={() => void handleCopy()}>
                {copied ? "Copied" : "Copy"}
              </Button>
            </div>
            <p className="mt-2 text-metadata leading-metadata text-text-secondary">
              {created.expires_at
                ? `Expires ${formatUpdated(created.expires_at)} (UTC). `
                : "No expiry. "}
              Revoke below to deny everyone at any time.
            </p>
          </section>
        ) : null}
        {phase === "created" && created && !created.share_path ? (
          <p role="status" className="mt-4 text-ui">
            This share is {created.status}. Its link is available only on first creation.
          </p>
        ) : null}

        {shares !== null ? (
          <section className="mt-5" aria-label="Existing share links" data-testid="share-list">
            <h3 className="font-ui text-ui font-medium text-text">
              Existing share links ({shares.length})
            </h3>
            {shares.length === 0 ? (
              <p className="mt-2 text-ui leading-ui text-text-secondary" data-testid="share-list-empty">
                No share links yet.
              </p>
            ) : (
              <ul className="mt-2 flex flex-col gap-2">
                {shares.map((share) => (
                  <li key={share.id} className="rounded-surface border-2 border-panel-border bg-surface p-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-ui leading-ui text-text">
                        <span className={
                          share.status === "active" ? "font-medium text-accent"
                            : share.status === "expired" ? "font-medium text-warning"
                              : "font-medium text-text-secondary"
                        } data-testid="share-status">
                          {share.status === "active" ? "Active"
                            : share.status === "expired" ? "Expired" : "Revoked"}
                        </span>
                        {" · "}Revision {share.revision}
                        {" · "}Created {formatUpdated(share.created_at)}
                        {share.expires_at ? ` · Expires ${formatUpdated(share.expires_at)}` : " · No expiry"}
                      </p>
                      {share.status !== "revoked" ? (
                        revokeTarget === share.id ? (
                          <span className="flex items-center gap-2">
                            <Button variant="destructive" data-testid="share-revoke-confirm"
                              disabled={phase === "creating"} onClick={() => void handleRevoke(share.id)}>
                              Confirm revoke
                            </Button>
                            <Button variant="quiet" onClick={() => setRevokeTarget(null)}>
                              Cancel
                            </Button>
                          </span>
                        ) : (
                          <Button variant="secondary" data-testid="share-revoke" disabled={phase === "creating"}
                            onClick={() => setRevokeTarget(share.id)}>
                            Revoke
                          </Button>
                        )
                      ) : null}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        ) : null}

        <div className="mt-5 flex justify-end">
          <Button variant="quiet" disabled={phase === "creating"} onClick={() => handleClose(false)} data-testid="share-close">
            Done
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
