"use client";

import { useEffect, useRef, useState } from "react";
import { Fingerprint, Copy, Check, RotateCcw, X, AlertCircle } from "lucide-react";
import { useI18n } from "@/lib/i18n";
import {
  getUserId,
  setUserId,
  rotateUserId,
  isValidUserId,
} from "@/lib/session";

/**
 * Per-browser Compass ID control. Shows the current session id, lets the user
 * pin a custom id (to return to their own compass) or generate a fresh one
 * (a clean isolated compass). On any change it persists to localStorage and
 * calls onChange so the dashboard refetches against the new id.
 */
export function CompassIdControl({ onChange }: { onChange: () => void }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [id, setId] = useState("");
  const [draft, setDraft] = useState("");
  const [invalid, setInvalid] = useState(false);
  const [copied, setCopied] = useState(false);
  const wrapRef = useRef<HTMLDivElement | null>(null);

  // Resolve the id in the browser (SSR-safe: empty string on the server).
  useEffect(() => {
    setId(getUserId());
  }, []);

  // Close on outside click / Escape.
  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const openPopover = () => {
    setDraft(id);
    setInvalid(false);
    setCopied(false);
    setOpen(true);
  };

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(id);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable — no-op */
    }
  };

  const apply = () => {
    const next = draft.trim();
    if (!isValidUserId(next)) {
      setInvalid(true);
      return;
    }
    setUserId(next);
    setId(next);
    setOpen(false);
    onChange();
  };

  const newCompass = () => {
    const next = rotateUserId();
    setId(next);
    setDraft(next);
    setInvalid(false);
    setOpen(false);
    onChange();
  };

  return (
    <div className="relative" ref={wrapRef}>
      <button
        onClick={() => (open ? setOpen(false) : openPopover())}
        aria-expanded={open}
        aria-haspopup="dialog"
        className="inline-flex items-center gap-1.5 rounded-full bg-ink-900/5 px-2.5 py-1 text-[11px] font-semibold text-ink-700 transition hover:bg-ink-900/10"
        title={t("user.button")}
      >
        <Fingerprint className="h-3.5 w-3.5 text-brand-indigo" />
        <span className="font-mono">{id || "…"}</span>
      </button>

      {open && (
        <div
          role="dialog"
          aria-label={t("user.title")}
          className="glass shadow-lift animate-fade-up absolute left-0 top-[calc(100%+8px)] z-50 w-[320px] rounded-2xl p-4"
        >
          <div className="mb-2 flex items-center justify-between gap-2">
            <p className="font-display text-[15px] font-extrabold tracking-tight text-ink-900">
              {t("user.title")}
            </p>
            <button
              onClick={() => setOpen(false)}
              aria-label={t("user.close")}
              className="flex h-6 w-6 items-center justify-center rounded-full text-ink-400 transition hover:bg-ink-900/5 hover:text-ink-700"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>

          <p className="mb-3 text-[11.5px] leading-relaxed text-ink-500">
            {t("user.explainer")}
          </p>

          {/* Current id (copyable) */}
          <label className="mb-1 block text-[10.5px] font-bold uppercase tracking-wide text-ink-400">
            {t("user.currentLabel")}
          </label>
          <div className="mb-3 flex items-center gap-2">
            <code className="min-w-0 flex-1 truncate rounded-xl bg-ink-900/5 px-2.5 py-1.5 font-mono text-[12px] text-ink-700">
              {id}
            </code>
            <button
              onClick={() => void copy()}
              className="btn-ghost inline-flex shrink-0 items-center gap-1 rounded-full px-2.5 py-1.5 text-[11px] font-bold"
            >
              {copied ? (
                <>
                  <Check className="h-3.5 w-3.5" />
                  {t("user.copied")}
                </>
              ) : (
                <>
                  <Copy className="h-3.5 w-3.5" />
                  {t("user.copy")}
                </>
              )}
            </button>
          </div>

          {/* Set a custom id */}
          <label className="mb-1 block text-[10.5px] font-bold uppercase tracking-wide text-ink-400">
            {t("user.setLabel")}
          </label>
          <input
            value={draft}
            onChange={(e) => {
              setDraft(e.target.value);
              if (invalid) setInvalid(false);
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") apply();
            }}
            placeholder={t("user.setPlaceholder")}
            spellCheck={false}
            autoComplete="off"
            className="field-input font-mono text-[12px]"
          />
          {invalid && (
            <p className="mt-1.5 flex items-center gap-1.5 text-[11px] text-status-debilitada">
              <AlertCircle className="h-3.5 w-3.5 shrink-0" />
              {t("user.invalid")}
            </p>
          )}

          <div className="mt-3 flex items-center gap-2">
            <button
              onClick={apply}
              disabled={!draft.trim() || draft.trim() === id}
              className="btn-primary shadow-soft inline-flex flex-1 items-center justify-center gap-1.5 rounded-full px-3 py-2 text-[12px] font-bold"
            >
              {t("user.apply")}
            </button>
            <button
              onClick={newCompass}
              className="btn-ghost inline-flex shrink-0 items-center gap-1.5 rounded-full px-3 py-2 text-[12px] font-bold"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              {t("user.new")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
