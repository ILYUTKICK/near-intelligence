export function filterEnumOptions(properties: unknown, key: string): string[] {
  if (properties === null || typeof properties !== "object" || Array.isArray(properties)) {
    return [];
  }
  const bound = (properties as Record<string, unknown>)[key];
  if (bound === null || typeof bound !== "object" || Array.isArray(bound)) {
    return [];
  }
  const options = (bound as Record<string, unknown>)["enum"];
  return Array.isArray(options) ? options.filter((option): option is string => typeof option === "string") : [];
}

export function filterLabel(key: string): string {
  return key
    .split("_")
    .map((word) => (word === "" ? "" : word.charAt(0).toUpperCase() + word.slice(1)))
    .join(" ");
}
