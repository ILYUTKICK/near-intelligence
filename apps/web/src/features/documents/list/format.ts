/**
 * Deterministic display formatting for document metadata (NI-023). Dates are
 * shown in UTC (storage stays UTC; the display-timezone preference is a
 * NI-025 profile concern), so server and browser render the same label.
 */
const UTC_DATE_FORMAT = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "short",
  year: "numeric",
  timeZone: "UTC",
});

export function formatUpdated(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso;
  }
  try {
    return UTC_DATE_FORMAT.format(date);
  } catch {
    return iso;
  }
}
