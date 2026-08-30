"use client";

import { useEffect, useRef } from "react";

/**
 * Auto-sizing textarea. Returns a ref to attach to a <textarea>; the element
 * grows to fit its content (no inner scrollbar) and re-measures whenever the
 * passed value changes. Give the textarea a min-height via className/rows so a
 * short draft still reads as a comfortable multi-line field.
 *
 * The whole draft is meant to be read at a glance, so we deliberately remove
 * the inner scrollbox and let the card (and the page) flow.
 */
export function useAutoResize<T extends HTMLTextAreaElement>(value: string) {
  const ref = useRef<T | null>(null);

  const resize = () => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  };

  // Re-measure on mount and whenever the content changes.
  useEffect(() => {
    resize();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  return ref;
}
