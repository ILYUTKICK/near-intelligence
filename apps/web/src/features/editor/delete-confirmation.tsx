"use client";

import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

import { blockLabel, type DependentBlock } from "./commands";

/**
 * Delete/reference confirmation (NI-039; UI_SCREEN_SPECIFICATIONS reusable
 * dialogs: "delete/reference confirmation ... Every overlay has title, clear
 * primary/cancel action, initial focus, Escape behavior and return-focus").
 *
 * Deleting a hypothesis/insight/chart target with dependent links is ONLY
 * possible through this explicit preview-and-confirm flow — the affected
 * evidence/insight/risk links are named before anything is removed, and the
 * removal deletes target + dependents together so the canonical document
 * never contains a dangling reference.
 */
export function DeleteConfirmationDialog({
  open,
  targetLabel,
  targetIndex,
  dependents,
  onConfirm,
  onOpenChange,
}: {
  open: boolean;
  targetLabel: string;
  targetIndex: number;
  dependents: readonly DependentBlock[];
  onConfirm: () => void;
  onOpenChange: (open: boolean) => void;
}) {
  const total = dependents.length + 1;
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogTitle>Delete {targetLabel}?</DialogTitle>
        <DialogDescription>
          {dependents.length > 0
            ? `This block is referenced by ${dependents.length} other block${dependents.length === 1 ? "" : "s"}. Deleting it removes those blocks too — the document cannot keep a link whose target is gone.`
            : "The block will be removed from the document. You can undo this."}
        </DialogDescription>
        {dependents.length > 0 ? (
          <ul
            data-testid="dependent-links-list"
            aria-label="Blocks that will be removed together with this block"
            className="mt-4 flex flex-col gap-2"
          >
            {dependents.map((dependent, index) => (
              <li
                key={`${dependent.blockId}-${index}`}
                className="rounded-control border border-border bg-surface-muted px-3 py-2"
              >
                <p className="text-ui leading-ui text-text">
                  {blockLabel(dependent.blockType)}
                </p>
                <p className="text-metadata leading-metadata text-text-secondary">
                  {dependent.reason}
                </p>
              </li>
            ))}
          </ul>
        ) : null}
        <div className="mt-6 flex flex-wrap gap-3">
          <Button variant="destructive" data-testid="confirm-delete" onClick={onConfirm}>
            Delete {total} block{total === 1 ? "" : "s"}
          </Button>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
        </div>
        <p className="sr-only">Target block position: {targetIndex}</p>
      </DialogContent>
    </Dialog>
  );
}
