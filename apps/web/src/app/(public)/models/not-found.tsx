import Link from "next/link";

import { PageIntro } from "@/components/layout/PageIntro";
import { Button } from "@/components/ui/button";
import { ModelAvailability } from "@/features/models/ModelAvailability";

/**
 * Honest 404 boundary for the model routes (NI-054 handoff): an unknown,
 * unpublished or malformed run identity lands here with a real 404 status.
 * The wording is generic by design — the API deliberately makes an
 * unpublished run indistinguishable from an absent one, and this page never
 * leaks which case occurred.
 */
export default function ModelNotFound() {
  return (
    <div className="page-container">
      <PageIntro eyebrow="Econometric evidence" title="Model run not found" />
      <ModelAvailability
        title="No published run to inspect"
        description="No published model run corresponds to this address. You can check the catalog for verified runs."
        action={<Button asChild variant="secondary"><Link href="/models">Open the model catalog</Link></Button>}
      />
    </div>
  );
}
