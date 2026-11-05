/**
 * Expose jest-axe's matcher on vitest's Assertion (jest-axe and its
 * community types target jest only). Module file so this merges with, not
 * replaces, vitest's own declarations.
 */
declare module "vitest" {
  interface Assertion {
    toHaveNoViolations(): void;
  }
  interface AsymmetricMatchersContaining {
    toHaveNoViolations(): void;
  }
}

export {};
