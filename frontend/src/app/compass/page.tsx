"use client";

import { useCallback, useEffect, useState } from "react";
import {
  RefreshCw,
  AlertCircle,
  ShieldCheck,
  FlaskConical,
  ClipboardCheck,
  PlayCircle,
  PencilRuler,
  Pause,
  Sparkles,
  ScrollText,
  ClipboardList,
  CheckCircle2,
  Clock,
  Wand2,
  GitBranch,
} from "lucide-react";
import * as api from "@/lib/api";
import { ApiError } from "@/lib/api";
import type {
  StateResponse,
  Evidence,
  ChainResponse,
  NextStepKind,
  ExtractCandidate,
  NarrateResponse,
} from "@/lib/types";
import { shortHash, contentSnippet, formatDate } from "@/lib/utils";
import { StatusChip, statusIsStruck } from "@/components/StatusChip";
import { IndexGauge } from "@/components/IndexGauge";
import { AuditChain } from "@/components/AuditChain";

const NEXT_STEP_ICON: Record<NextStepKind, typeof FlaskConical> = {
  completar_experimento: ClipboardCheck,
  ejecutar_experimento: PlayCircle,
  validar_evidencia: ClipboardCheck,
  "diseñar_experimento": PencilRuler,
  abstain: Pause,
};

const EVIDENCE_TYPE_LABEL: Record<string, string> = {
  self_report: "self report",
  narrative_extracted: "narrative",
  behavioral: "behavioral",
  experiment_result: "experiment",
  outcome_external: "outcome",
};

export default function CompassDashboard() {
  const [state, setState] = useState<StateResponse | null>(null);
  const [evidence, setEvidence] = useState<Evidence[] | null>(null);
  const [chain, setChain] = useState<ChainResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [s, e, c] = await Promise.all([
        api.getState(),
        api.getEvidence(),
        api.getChain(),
      ]);
      setState(s);
      setEvidence(e.evidence);
      setChain(c);
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? err.message
          : "Something went wrong loading the dashboard.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const refetch = useCallback(async () => {
    try {
      const [s, e, c] = await Promise.all([
        api.getState(),
        api.getEvidence(),
        api.getChain(),
      ]);
      setState(s);
      setEvidence(e.evidence);
      setChain(c);
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Refetch failed.";
      setError(msg);
    }
  }, []);

  const onValidate = useCallback(
    async (id: number | string) => {
      setBusy(`validate-${id}`);
      try {
        await api.validateEvidence(id);
        await refetch();
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Validation failed.");
      } finally {
        setBusy(null);
      }
    },
    [refetch],
  );

  const onRecompute = useCallback(async () => {
    setBusy("recompute");
    try {
      await api.recompute();
      await refetch();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Recompute failed.");
    } finally {
      setBusy(null);
    }
  }, [refetch]);

  if (loading) return <DashboardSkeleton />;

  if (error && !state) {
    return <BackendUnreachable message={error} onRetry={() => void load()} />;
  }

  const s = state?.state;
  const visibleEvidence = (evidence ?? []).filter((e) => e.deleted !== 1);

  return (
    <section className="mx-auto max-w-7xl px-4 pb-10 pt-6">
      {/* Header row */}
      <div className="animate-fade-up flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <p className="text-[11px] font-extrabold uppercase tracking-[0.1em] text-ink-400">
            Navigation dashboard
          </p>
          <h1 className="font-display text-[clamp(26px,4vw,38px)] font-extrabold tracking-tight text-ink-900">
            {s?.person ?? "Person"}
          </h1>
          <div className="mt-1.5 flex flex-wrap items-center gap-2 text-[12px] text-ink-500">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-ink-900/5 px-2.5 py-1 font-mono text-[11px] text-ink-700">
              <ShieldCheck className="h-3.5 w-3.5 text-brand-indigo" />
              seal {shortHash(state?.seal, 10, 6)}
            </span>
            {chain && (
              <span
                className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-bold ${
                  chain.linkage_ok && chain.integrity_ok
                    ? "bg-status-corroboradaBg text-status-corroborada"
                    : "bg-status-debilitadaBg text-status-debilitada"
                }`}
              >
                <ScrollText className="h-3.5 w-3.5" />
                chain: linkage {chain.linkage_ok ? "✓" : "✗"} integrity{" "}
                {chain.integrity_ok ? "✓" : "✗"}
              </span>
            )}
          </div>
        </div>

        <button
          onClick={() => void onRecompute()}
          disabled={busy === "recompute"}
          className="btn-primary shadow-soft inline-flex shrink-0 items-center gap-2 rounded-full px-5 py-2.5 text-[13px] font-bold"
        >
          <RefreshCw
            className={`h-4 w-4 ${busy === "recompute" ? "animate-spin" : ""}`}
          />
          Recompute &amp; reseal
        </button>
      </div>

      {error && state && (
        <div className="animate-fade-up mt-4 flex items-center gap-2 rounded-2xl border border-status-debilitada/25 bg-status-debilitadaBg px-4 py-3 text-[13px] text-status-debilitada">
          <AlertCircle className="h-4 w-4 shrink-0" />
          {error}
        </div>
      )}

      {/* Counts strip */}
      {s && (
        <div className="animate-fade-up mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <CountCard
            icon={ClipboardCheck}
            label="Evidence validated"
            value={s.evidence_validated ?? 0}
          />
          <CountCard
            icon={Clock}
            label="Evidence pending"
            value={s.evidence_pending ?? 0}
          />
          <CountCard
            icon={GitCount}
            label="Hypotheses"
            value={s.hypotheses.length}
          />
          <CountCard
            icon={FlaskConical}
            label="Experiments"
            value={countValues(s.experiment_counts)}
          />
        </div>
      )}

      {/* The single next step */}
      {s?.next_step && <NextStepCard kind={s.next_step.kind} detail={s.next_step.detail} />}

      <div className="mt-6 grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        {/* Left column */}
        <div className="space-y-6">
          {/* Rival hypotheses */}
          <Panel
            title="Rival hypotheses"
            subtitle="Held alive until a discriminating experiment separates them"
            icon={GitCount}
          >
            {s && s.hypotheses.length > 0 ? (
              <div className="grid gap-4 sm:grid-cols-2">
                {s.hypotheses.map((h) => (
                  <div
                    key={h.id}
                    className="card-solid rounded-2xl p-4"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <StatusChip status={h.status} />
                      {h.engine_version && (
                        <span className="font-mono text-[10px] text-ink-400">
                          {h.engine_version}
                        </span>
                      )}
                    </div>
                    <p
                      className={`mt-3 text-[13.5px] leading-relaxed text-ink-700 ${
                        statusIsStruck(h.status) ? "line-through opacity-60" : ""
                      }`}
                    >
                      {h.statement}
                    </p>
                    <div className="mt-3 border-t border-ink-900/5 pt-3">
                      <IndexGauge index={h.index} status={h.status} />
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <Empty>No hypotheses yet.</Empty>
            )}
          </Panel>

          {/* Evidence ledger */}
          <Panel
            title="Evidence ledger"
            subtitle="Nothing counts until it is validated"
            icon={ClipboardList}
          >
            {visibleEvidence.length > 0 ? (
              <div className="space-y-2">
                {visibleEvidence.map((e) => (
                  <EvidenceRow
                    key={e.id}
                    ev={e}
                    onValidate={() => void onValidate(e.id)}
                    validating={busy === `validate-${e.id}`}
                  />
                ))}
              </div>
            ) : (
              <Empty>No evidence recorded yet.</Empty>
            )}
          </Panel>

          {/* Narrative -> signals */}
          <ExtractPanel onValidated={() => void refetch()} />
        </div>

        {/* Right column */}
        <div className="space-y-6">
          {/* Narrator */}
          <NarratePanel />

          {/* Audit chain */}
          <Panel
            title="Audit chain"
            subtitle="Append-only, hash-chained ledger"
            icon={ScrollText}
          >
            {chain ? (
              <AuditChain
                entries={chain.entries}
                linkageOk={chain.linkage_ok}
                integrityOk={chain.integrity_ok}
              />
            ) : (
              <Empty>Chain unavailable.</Empty>
            )}
          </Panel>
        </div>
      </div>
    </section>
  );
}

/* ─────────────────────────── sub-components ─────────────────────────── */

function NextStepCard({ kind, detail }: { kind: NextStepKind; detail: string }) {
  const Icon = NEXT_STEP_ICON[kind] ?? FlaskConical;
  return (
    <div className="animate-fade-up shadow-glow glass mt-6 flex items-start gap-4 rounded-3xl p-6">
      <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl brand-gradient text-white">
        <Icon className="h-6 w-6" />
      </span>
      <div className="min-w-0">
        <p className="text-[11px] font-extrabold uppercase tracking-[0.1em] text-brand-deep">
          The single next step · {kind.replace(/_/g, " ")}
        </p>
        <p className="mt-1 text-[16px] font-semibold leading-relaxed text-ink-900">
          {detail}
        </p>
        <p className="mt-2 text-[11.5px] text-ink-400">
          Deterministic recommendation — computed by the engine, not the narrator.
        </p>
      </div>
    </div>
  );
}

function EvidenceRow({
  ev,
  onValidate,
  validating,
}: {
  ev: Evidence;
  onValidate: () => void;
  validating: boolean;
}) {
  const pending = ev.validated !== 1;
  return (
    <div className="card-solid flex flex-col gap-2 rounded-2xl p-3.5 sm:flex-row sm:items-center sm:gap-3">
      <div className="flex shrink-0 items-center gap-2">
        <span className="rounded-full bg-brand-indigo/10 px-2.5 py-0.5 text-[10.5px] font-bold uppercase tracking-wide text-brand-deep">
          {EVIDENCE_TYPE_LABEL[ev.evidence_type] ?? ev.evidence_type}
        </span>
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-[12.5px] leading-snug text-ink-700">
          {contentSnippet(ev.content)}
        </p>
        <p className="mt-0.5 text-[11px] text-ink-400">
          {ev.source} · {formatDate(ev.created_at)}
        </p>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        {pending ? (
          <>
            <span className="inline-flex items-center gap-1 rounded-full bg-status-debilitadaBg px-2.5 py-1 text-[10.5px] font-bold uppercase tracking-wide text-status-debilitada">
              <Clock className="h-3 w-3" />
              pending
            </span>
            <button
              onClick={onValidate}
              disabled={validating}
              className="btn-ghost inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[11.5px] font-bold"
            >
              {validating ? (
                <RefreshCw className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <CheckCircle2 className="h-3.5 w-3.5" />
              )}
              Validate
            </button>
          </>
        ) : (
          <span className="inline-flex items-center gap-1 rounded-full bg-status-corroboradaBg px-2.5 py-1 text-[10.5px] font-bold uppercase tracking-wide text-status-corroborada">
            <CheckCircle2 className="h-3 w-3" />
            validated
          </span>
        )}
      </div>
    </div>
  );
}

function ExtractPanel({ onValidated }: { onValidated: () => void }) {
  const [narrative, setNarrative] = useState("");
  const [candidates, setCandidates] = useState<ExtractCandidate[] | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [validatingId, setValidatingId] = useState<string | number | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const run = async () => {
    if (!narrative.trim()) return;
    setBusy(true);
    setErr(null);
    try {
      const res = await api.extract(narrative);
      setCandidates(res.candidates);
      setNote(res.note ?? null);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Extraction failed.");
    } finally {
      setBusy(false);
    }
  };

  const validate = async (id: string | number) => {
    setValidatingId(id);
    try {
      await api.validateEvidence(id);
      setCandidates((prev) => prev?.filter((c) => c.evidence_id !== id) ?? null);
      onValidated();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Validation failed.");
    } finally {
      setValidatingId(null);
    }
  };

  return (
    <Panel
      title="Narrative → signals"
      subtitle="Extracted candidates persist as PENDING evidence — nothing counts until validated"
      icon={Wand2}
    >
      <textarea
        value={narrative}
        onChange={(e) => setNarrative(e.target.value)}
        rows={4}
        placeholder="Paste a narrative in the person's own words…"
        className="field-input resize-y"
      />
      <div className="mt-3 flex items-center justify-between gap-3">
        <button
          onClick={() => void run()}
          disabled={busy || !narrative.trim()}
          className="btn-primary shadow-soft inline-flex items-center gap-2 rounded-full px-4 py-2 text-[13px] font-bold"
        >
          {busy ? (
            <RefreshCw className="h-4 w-4 animate-spin" />
          ) : (
            <Sparkles className="h-4 w-4" />
          )}
          Extract signals
        </button>
        {note && <span className="text-[11px] italic text-ink-400">{note}</span>}
      </div>

      {err && (
        <p className="mt-3 flex items-center gap-1.5 text-[12px] text-status-debilitada">
          <AlertCircle className="h-3.5 w-3.5" /> {err}
        </p>
      )}

      {candidates && (
        <div className="mt-4 space-y-2">
          {candidates.length === 0 ? (
            <Empty>No signals extracted.</Empty>
          ) : (
            candidates.map((c) => (
              <div
                key={c.evidence_id}
                className="rounded-2xl border border-dashed border-brand-indigo/25 bg-brand-indigo/[0.03] p-3.5"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-[13px] font-semibold text-ink-900">{c["señal"]}</p>
                    <p className="mt-1 border-l-2 border-brand-indigo/30 pl-2.5 text-[12px] italic leading-relaxed text-ink-500">
                      “{c.cita}”
                    </p>
                  </div>
                  <button
                    onClick={() => void validate(c.evidence_id)}
                    disabled={validatingId === c.evidence_id}
                    className="btn-ghost inline-flex shrink-0 items-center gap-1.5 rounded-full px-3 py-1.5 text-[11.5px] font-bold"
                  >
                    {validatingId === c.evidence_id ? (
                      <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <CheckCircle2 className="h-3.5 w-3.5" />
                    )}
                    Validate
                  </button>
                </div>
                <p className="mt-2 text-[10.5px] font-bold uppercase tracking-wide text-brand-deep">
                  pending — does not count until validated
                </p>
              </div>
            ))
          )}
        </div>
      )}
    </Panel>
  );
}

function NarratePanel() {
  const [result, setResult] = useState<NarrateResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const run = async () => {
    setBusy(true);
    setErr(null);
    try {
      setResult(await api.narrate());
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Narration failed.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel
      title="Narrator"
      subtitle="The seal exists before the narrator speaks"
      icon={Sparkles}
    >
      <button
        onClick={() => void run()}
        disabled={busy}
        className="btn-primary shadow-soft inline-flex items-center gap-2 rounded-full px-4 py-2 text-[13px] font-bold"
      >
        {busy ? (
          <RefreshCw className="h-4 w-4 animate-spin" />
        ) : (
          <Sparkles className="h-4 w-4" />
        )}
        Narrate my state
      </button>

      {err && (
        <p className="mt-3 flex items-center gap-1.5 text-[12px] text-status-debilitada">
          <AlertCircle className="h-3.5 w-3.5" /> {err}
        </p>
      )}

      {result && (
        <div className="animate-fade-up mt-4">
          <div className="mb-2 inline-flex items-center gap-1.5 rounded-full bg-ink-900/5 px-2.5 py-1 font-mono text-[10.5px] text-ink-700">
            <ShieldCheck className="h-3 w-3 text-brand-indigo" />
            seal {shortHash(result.seal, 10, 6)}
          </div>
          {result.summary && (
            <p className="mb-2 text-[12px] font-semibold text-ink-500">{result.summary}</p>
          )}
          <div className="glass-subtle rounded-2xl p-4 text-[13.5px] leading-relaxed text-ink-700">
            {result.prose}
          </div>
          <p className="mt-2 text-[11px] italic leading-relaxed text-ink-400">
            The seal exists before the narrator speaks; swapping the model changes only
            these words — never the seal or any index.
          </p>
        </div>
      )}
    </Panel>
  );
}

/* ─────────────────────────── primitives ─────────────────────────── */

function Panel({
  title,
  subtitle,
  icon: Icon,
  children,
}: {
  title: string;
  subtitle?: string;
  icon: typeof FlaskConical;
  children: React.ReactNode;
}) {
  return (
    <div className="animate-fade-up card-solid shadow-soft rounded-3xl p-5">
      <div className="mb-4 flex items-start gap-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-brand-indigo/10 text-brand-deep">
          <Icon className="h-4.5 w-4.5" />
        </span>
        <div>
          <h2 className="font-display text-[17px] font-extrabold tracking-tight text-ink-900">
            {title}
          </h2>
          {subtitle && <p className="text-[12px] leading-snug text-ink-500">{subtitle}</p>}
        </div>
      </div>
      {children}
    </div>
  );
}

function CountCard({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof FlaskConical;
  label: string;
  value: number;
}) {
  return (
    <div className="card-solid rounded-2xl p-3.5">
      <div className="flex items-center gap-2 text-ink-400">
        <Icon className="h-3.5 w-3.5" />
        <span className="text-[10.5px] font-bold uppercase tracking-wide">{label}</span>
      </div>
      <p className="mt-1 font-display text-[26px] font-extrabold leading-none tracking-tight text-ink-900">
        {value}
      </p>
    </div>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-dashed border-ink-900/15 bg-ink-900/[0.02] p-5 text-center text-[12.5px] text-ink-500">
      {children}
    </div>
  );
}

// Alias used where GitBranch reads as "hypotheses".
const GitCount = GitBranch;

function countValues(counts?: Record<string, number>): number {
  if (!counts) return 0;
  return Object.values(counts).reduce((a, b) => a + (Number(b) || 0), 0);
}

/* ─────────────────────────── states ─────────────────────────── */

function DashboardSkeleton() {
  return (
    <section className="mx-auto max-w-7xl px-4 pb-10 pt-6">
      <div className="skeleton h-9 w-64 rounded-lg" />
      <div className="mt-3 skeleton h-5 w-96 rounded-lg" />
      <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="skeleton h-20 rounded-2xl" />
        ))}
      </div>
      <div className="skeleton mt-6 h-28 rounded-3xl" />
      <div className="mt-6 grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <div className="space-y-6">
          <div className="skeleton h-72 rounded-3xl" />
          <div className="skeleton h-56 rounded-3xl" />
        </div>
        <div className="space-y-6">
          <div className="skeleton h-56 rounded-3xl" />
          <div className="skeleton h-72 rounded-3xl" />
        </div>
      </div>
    </section>
  );
}

function BackendUnreachable({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <section className="mx-auto flex max-w-2xl flex-col items-center px-4 pb-10 pt-20 text-center">
      <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-status-debilitadaBg text-status-debilitada">
        <AlertCircle className="h-7 w-7" />
      </span>
      <h1 className="mt-5 font-display text-2xl font-extrabold tracking-tight text-ink-900">
        Can&apos;t reach the COMPASS backend
      </h1>
      <p className="mt-2 max-w-md text-[14px] leading-relaxed text-ink-500">{message}</p>
      <div className="mt-4 rounded-2xl bg-ink-900/5 px-4 py-3 text-left font-mono text-[12px] text-ink-700">
        <p className="mb-1 text-ink-400"># start the backend, then retry</p>
        <p>NEXT_PUBLIC_API_URL={api.API_BASE}</p>
      </div>
      <button
        onClick={onRetry}
        className="btn-primary shadow-soft mt-5 inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-[13px] font-bold"
      >
        <RefreshCw className="h-4 w-4" />
        Retry
      </button>
    </section>
  );
}
