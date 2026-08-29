import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Short, monospace-friendly hash/seal display: head…tail. */
export function shortHash(hash: string | undefined | null, head = 8, tail = 6): string {
  if (!hash) return "—";
  const h = String(hash);
  if (h.length <= head + tail + 1) return h;
  return `${h.slice(0, head)}…${h.slice(-tail)}`;
}

/** Best-effort human timestamp; falls back to the raw string. */
export function formatDate(ts: string | undefined | null): string {
  if (!ts) return "—";
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return String(ts);
  return d.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/**
 * Render a short, readable snippet of an evidence content JSON string.
 * The content arrives as a JSON string; we pretty-flatten the top-level
 * fields for a one-line preview and truncate.
 */
export function contentSnippet(content: string, max = 140): string {
  if (!content) return "—";
  let text = content;
  try {
    const obj = JSON.parse(content);
    if (obj && typeof obj === "object") {
      text = Object.entries(obj)
        .map(([k, v]) => `${k}: ${typeof v === "object" ? JSON.stringify(v) : String(v)}`)
        .join(" · ");
    }
  } catch {
    // not JSON — show raw
  }
  return text.length > max ? `${text.slice(0, max)}…` : text;
}

/** Clamp the COMPASS confidence index into the documented 0–1000 range. */
export function clampIndex(index: number | null | undefined): number {
  if (index == null || Number.isNaN(index)) return 0;
  return Math.min(1000, Math.max(0, Math.round(index)));
}
