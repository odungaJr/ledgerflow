/**
 * The single source of truth for "today" as a YYYY-MM-DD string.
 *
 * Deliberately not `new Date().toISOString().slice(0, 10)` — toISOString()
 * converts to UTC, which silently returns the *previous* calendar day for
 * anyone east of UTC (e.g. Tanzania, UTC+3) during the first few hours after
 * local midnight. This uses the browser's local calendar date instead.
 */
export function todayIso(): string {
  return dateToIso(new Date());
}

/** Format a Date as YYYY-MM-DD using its local calendar date (see todayIso). */
export function dateToIso(d: Date): string {
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}
