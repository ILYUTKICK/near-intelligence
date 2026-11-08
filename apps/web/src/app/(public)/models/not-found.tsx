import Link from "next/link";

/**
 * Honest 404 boundary for the model routes (NI-054 handoff): an unknown,
 * unpublished or malformed run identity lands here with a real 404 status.
 * The wording is generic by design — the API deliberately makes an
 * unpublished run indistinguishable from an absent one, and this page never
 * leaks which case occurred.
 */
export default function ModelNotFound() {
  return (
    <div className="mx-auto w-full max-w-(--width-content-max) px-4 py-12">
      <div className="rounded-surface border border-border bg-surface-muted p-6 max-w-prose">
        <h1>Model run not found</h1>
        <p className="text-body leading-body text-text-secondary mt-2">
          No published model run corresponds to this address. The link may be mistyped, or no
          such run has been published; no distinction is made between those cases. Nothing is
          shown in place of an unpublished result.
        </p>
        <div className="mt-4 flex flex-wrap gap-3">
          <Link
            href="/models"
            className="inline-flex h-11 items-center rounded-control border border-control-border bg-surface px-4 font-ui text-ui leading-ui text-text hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
          >
            Open the model catalog
          </Link>
          <Link
            href="/methodology#reproduce"
            className="inline-flex h-11 items-center rounded-control border border-transparent px-4 font-ui text-ui leading-ui text-text underline underline-offset-2 hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
          >
            How models are verified and reproduced
          </Link>
        </div>
      </div>
    </div>
  );
}
