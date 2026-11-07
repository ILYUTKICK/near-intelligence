import type { Attribute } from "@tiptap/core";

/**
 * Shared Tiptap attribute definitions for the canonical P0 block nodes.
 *
 * Canonical storage is JSON (NI-036), so attribute fidelity is required on
 * the JSON path; the data-attribute forms below keep ADR-018's HTML-level
 * fidelity (renderHTML tuple form, attrs serialized as data-attributes).
 * Scalar attrs use `data-kebab-name`; structured attrs (selection, columns,
 * body, context) carry their JSON serialization in a data attribute.
 */

const kebab = (name: string) => name.replace(/_/g, "-");

export function blockIdAttr(): Attribute {
  return {
    default: null,
    parseHTML: (element: HTMLElement) => element.getAttribute(`data-${kebab("block_id")}`),
    renderHTML: (attributes: Record<string, unknown>) => {
      return attributes.block_id == null
        ? {}
        : { "data-block-id": attributes.block_id };
    },
  };
}

export function stringAttr(name: string, { defaultValue = null }: { defaultValue?: unknown } = {}): Attribute {
  return {
    default: defaultValue,
    parseHTML: (element: HTMLElement) => element.getAttribute(`data-${kebab(name)}`),
    renderHTML: (attributes: Record<string, unknown>) => {
      const value = attributes[name];
      return value == null ? {} : { [`data-${kebab(name)}`]: String(value) };
    },
  };
}

export function jsonAttr(name: string): Attribute {
  return {
    default: null,
    parseHTML: (element: HTMLElement) => {
      const raw = element.getAttribute(`data-${kebab(name)}`);
      if (raw == null) {
        return null;
      }
      try {
        return JSON.parse(raw);
      } catch {
        return null;
      }
    },
    renderHTML: (attributes: Record<string, unknown>) => {
      const value = attributes[name];
      if (value === undefined) {
        return {};
      }
      return { [`data-${kebab(name)}`]: JSON.stringify(value ?? null) };
    },
  };
}
