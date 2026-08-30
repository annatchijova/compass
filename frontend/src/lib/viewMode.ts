// Dashboard view mode. Calm (single-focus, progressive disclosure) is the
// DEFAULT — it is the accessible view for the primary audience. Full shows
// every panel. Persisted in localStorage.

export type ViewMode = "calm" | "full";

export const VIEW_MODE_KEY = "compass-view-mode";

/** SSR-safe read; defaults to "calm" when unset or in a non-browser context. */
export function getViewMode(): ViewMode {
  if (typeof window === "undefined" || !window.localStorage) return "calm";
  const v = window.localStorage.getItem(VIEW_MODE_KEY);
  return v === "full" ? "full" : "calm";
}

export function setViewMode(mode: ViewMode): void {
  if (typeof window === "undefined" || !window.localStorage) return;
  window.localStorage.setItem(VIEW_MODE_KEY, mode);
}
