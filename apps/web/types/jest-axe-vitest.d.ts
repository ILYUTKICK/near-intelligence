/**
 * Local types for jest-axe under vitest: jest-axe ships no declarations and
 * the community @types/jest-axe augments jest's Assertion, not vitest's.
 * Minimal structural types — the real validator stays jest-axe's runtime.
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

declare module "vitest" {
  interface Assertion {
    toHaveNoViolations(): void;
  }
  interface AsymmetricMatchersContaining {
    toHaveNoViolations(): void;
  }
}
