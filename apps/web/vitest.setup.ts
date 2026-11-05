import "@testing-library/jest-dom/vitest";
import { toHaveNoViolations } from "jest-axe";
import { expect } from "vitest";

expect.extend(toHaveNoViolations);

// jsdom lacks the browser APIs Radix primitives rely on; provide minimal
// stand-ins so keyboard behavior is what the tests exercise.
class PointerEventPolyfill extends MouseEvent {
  pointerId = 1;
  isPrimary = true;
  pointerType = "mouse";
}

if (!("PointerEvent" in globalThis)) {
  Object.defineProperty(globalThis, "PointerEvent", {
    value: PointerEventPolyfill,
    writable: true,
  });
}

if (!Element.prototype.hasPointerCapture) {
  Element.prototype.hasPointerCapture = () => false;
  Element.prototype.setPointerCapture = () => {};
  Element.prototype.releasePointerCapture = () => {};
}

Element.prototype.scrollIntoView ??= () => {};

globalThis.ResizeObserver ??= class ResizeObserverStub {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {};
};

globalThis.matchMedia ??= ((query: string) =>
  ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }) as MediaQueryList) as typeof matchMedia;
