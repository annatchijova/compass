"use client";

import { Fingerprint, Link2, CheckCircle2, AlertTriangle } from "lucide-react";
import type { ChainEntry } from "@/lib/types";
import { shortHash, formatDate } from "@/lib/utils";
import { useI18n } from "@/lib/i18n";

// Append-only, hash-chained audit ledger view. Adapted from VELO's
// CustodyChain (same numbered-node timeline + linkage/integrity verdicts).
export function AuditChain({
  entries,
  linkageOk,
  integrityOk,
  contentOk,
}: {
  entries: ChainEntry[];
  linkageOk: boolean;
  integrityOk: boolean;
  contentOk?: boolean;
}) {
  const { t } = useI18n();

  if (entries.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-ink-900/15 bg-ink-900/[0.02] p-5 text-center">
        <p className="text-[13px] font-bold text-ink-900">{t("chain.emptyTitle")}</p>
        <p className="mt-1 text-[12px] leading-relaxed text-ink-500">
          {t("chain.emptyDesc")}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <Verdict ok={linkageOk} label={t("chain.linkage")} />
        <Verdict ok={integrityOk} label={t("chain.integrity")} />
        {contentOk !== undefined && (
          <Verdict ok={contentOk} label={t("chain.content")} />
        )}
        <span className="ml-auto text-[11px] text-ink-400">
          {entries.length} {t("chain.entries")}
        </span>
      </div>

      <div className="space-y-2">
        {entries.map((e, i) => (
          <div key={`${e.seq}-${i}`} className="relative flex items-start gap-3">
            {i < entries.length - 1 && (
              <span className="absolute left-[11px] top-7 h-[calc(100%-12px)] w-px bg-ink-900/10" />
            )}
            <span className="relative z-10 mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border-2 border-brand-indigo/30 bg-white text-[10px] font-extrabold text-brand-indigo">
              {e.seq}
            </span>
            <div className="min-w-0 flex-1 pb-1">
              <div className="flex flex-wrap items-center gap-2">
                {/* op is a stable event-code identifier from the backend —
                    shown verbatim as a compact monospace code, never
                    translated (a fake translation would hide the real op). */}
                <span className="rounded-full bg-brand-indigo/10 px-2.5 py-0.5 font-mono text-[11px] font-bold tracking-tight text-brand-deep">
                  {e.op}
                </span>
                <span className="text-[11.5px] text-ink-400">{formatDate(e.ts)}</span>
              </div>
              <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 font-mono text-[11px] text-ink-500">
                <span className="inline-flex items-center gap-1">
                  <Fingerprint className="h-3 w-3 shrink-0 text-ink-400" />
                  {shortHash(e.audit_hash, 10, 6)}
                </span>
                <span className="inline-flex items-center gap-1 text-ink-400">
                  <Link2 className="h-3 w-3 shrink-0" />
                  {t("chain.prev")} {shortHash(e.prev_hash, 8, 6)}
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function Verdict({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-bold uppercase tracking-wide ${
        ok
          ? "bg-status-corroboradaBg text-status-corroborada"
          : "bg-status-debilitadaBg text-status-debilitada"
      }`}
    >
      {ok ? (
        <CheckCircle2 className="h-3.5 w-3.5" />
      ) : (
        <AlertTriangle className="h-3.5 w-3.5" />
      )}
      {label} {ok ? "✓" : "✗"}
    </span>
  );
}
