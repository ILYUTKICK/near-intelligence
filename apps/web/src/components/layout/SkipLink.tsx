/**
 * Skip navigation link — the first tabbable element on every shell; becomes
 * visible on focus and jumps to the shell's main landmark (#main-content).
 */
export function SkipLink() {
  return (
    <a
      href="#main-content"
      className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-[100] focus:rounded-control focus:bg-surface focus:px-4 focus:py-2 focus:text-ui focus:leading-ui focus:text-text focus:border focus:border-control-border focus:shadow-[var(--shadow-overlay)] focus:outline-2 focus:outline-focus"
    >
      Skip to main content
    </a>
  );
}
