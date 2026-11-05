/**
 * Ambient types for the untyped jest-axe package (v11 ships none). Kept in
 * script context — a module-context augmentation cannot declare an untyped
 * package. Minimal structural types; the validator stays jest-axe's runtime.
 */
declare module "jest-axe" {
  export interface AxeResults {
    passes: unknown[];
    violations: {
      id: string;
      impact: string | null;
      nodes: unknown[];
    }[];
    incomplete: unknown[];
    inapplicable: unknown[];
  }

  export function axe(
    html: Element | string,
    options?: Record<string, unknown>,
  ): Promise<AxeResults>;

  export const toHaveNoViolations: {
    toHaveNoViolations: () => (results: AxeResults) => {
      pass: boolean;
      message: () => string;
    };
  };
}
