"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Route,
  Plus,
  RefreshCw,
  AlertCircle,
  ChevronRight,
  GitCompare,
  Target,
} from "lucide-react";
import * as api from "@/lib/api";
import { ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type {
  Trajectory,
  FitResponse,
  FitSummary,
  DiscriminateResponse,
  Hypothesis,
  FitStatus,
} from "@/lib/types";
import { FitChip, fitIsStruck } from "@/components/FitChip";

export default function TrajectoriesPage() {
  const { t } = useI18n();
  const [trajectories, setTrajectories] = useState<Trajectory[] | null>(null);
  const [hypotheses, setHypotheses] = useState<Hypothesis[]>([]);
  const [selectedId, setSelectedId] = useState<number | string | null>(null);
  const [fit, setFit] = useState<FitResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadTrajectories = useCallback(async () => {
    const [tr, hy] = await Promise.all([
      api.getTrajectories(),
      api.getHypotheses(),
    ]);
    setTrajectories(tr.trajectories);
    setHypotheses(hy.hypotheses);
    return tr.trajectories;
  }, []);

  const load = useCallback(async () => {
    setError(null);
    try {
      await loadTrajectories();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("err.trajectories"));
    } finally {
      setLoading(false);
    }
  }, [loadTrajectories, t]);

  useEffect(() => {
    void load();
  }, [load]);

  const loadFit = useCallback(
    async (id: number | string) => {
      setSelectedId(id);
      setFit(null);
      try {
        setFit(await api.getFit(id));
      } catch (err) {
        setError(err instanceof ApiError ? err.message : t("err.fit"));
      }
    },
    [t],
  );

  const refetchFit = useCallback(async () => {
    if (selectedId == null) return;
    try {
      setFit(await api.getFit(selectedId));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("err.fit"));
    }
  }, [selectedId, t]);

  const onCreated = useCallback(
    async (id: number | string) => {
      await loadTrajectories();
      await loadFit(id);
    },
    [loadTrajectories, loadFit],
  );

  if (loading) return <TrajectoriesSkeleton />;

  if (error && !trajectories) {
    return <BackendUnreachable message={error} onRetry={() => void load()} />;
  }

  const list = trajectories ?? [];

  return (
    <section className="mx-auto max-w-7xl px-4 pb-10 pt-6">
      {/* Header */}
      <div className="animate-fade-up">
        <p className="text-[11px] font-extrabold uppercase tracking-[0.1em] text-brand-deep">
          {t("traj.eyebrow")}
        </p>
        <h1 className="font-display text-[clamp(26px,4vw,38px)] font-extrabold tracking-tight text-ink-900">
          {t("traj.title")}
        </h1>
        <p className="mt-1.5 max-w-[640px] text-[13.5px] leading-relaxed text-ink-500">
          {t("traj.subtitle")}
        </p>
      </div>

      {error && trajectories && (
        <div className="animate-fade-up mt-4 flex items-center gap-2 rounded-2xl border border-status-debilitada/25 bg-status-debilitadaBg px-4 py-3 text-[13px] text-status-debilitada">
          <AlertCircle className="h-4 w-4 shrink-0" />
          {error}
        </div>
      )}

      <div className="mt-6 grid gap-6 lg:grid-cols-[0.8fr_1.2fr]">
        {/* Left: list + create */}
        <div className="space-y-6">
          <Panel title={t("traj.list.title")} subtitle={t("traj.list.subtitle")} icon={Route}>
            {list.length > 0 ? (
              <div className="space-y-2">
                {list.map((tr) => (
                  <button
                    key={tr.id}
                    onClick={() => void loadFit(tr.id)}
                    className={`card-solid card-hover flex w-full items-center gap-3 rounded-2xl p-3.5 text-left ${
                      selectedId === tr.id ? "shadow-glow border-brand-indigo/30" : ""
                    }`}
                  >
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[13.5px] font-bold text-ink-900">{tr.name}</p>
                      {tr.description && (
                        <p className="mt-0.5 truncate text-[12px] text-ink-500">
                          {tr.description}
                        </p>
                      )}
                    </div>
                    <ChevronRight className="h-4 w-4 shrink-0 text-ink-400" />
                  </button>
                ))}
              </div>
            ) : (
              <Empty>{t("traj.list.empty")}</Empty>
            )}

            <div className="mt-4 border-t border-ink-900/5 pt-4">
              <CreateTrajectory onCreated={onCreated} />
            </div>
          </Panel>

          {/* Discriminate */}
          <DiscriminatePanel trajectories={list} />
        </div>

        {/* Right: fit view */}
        <div className="space-y-6">
          {selectedId == null ? (
            <Panel title={t("traj.fit.title")} subtitle={t("traj.fit.caption")} icon={Target}>
              <Empty>{t("traj.select.hint")}</Empty>
            </Panel>
          ) : fit == null ? (
            <div className="card-solid shadow-soft rounded-3xl p-5">
              <div className="skeleton h-6 w-40 rounded-lg" />
              <div className="mt-4 skeleton h-16 rounded-2xl" />
              <div className="mt-3 skeleton h-40 rounded-2xl" />
            </div>
          ) : (
            <FitView fit={fit} hypotheses={hypotheses} onRequirementAdded={() => void refetchFit()} />
          )}
        </div>
      </div>
    </section>
  );
}

/* ─────────────────────────── fit view ─────────────────────────── */

function FitView({
  fit,
  hypotheses,
  onRequirementAdded,
}: {
  fit: FitResponse;
  hypotheses: Hypothesis[];
  onRequirementAdded: () => void;
}) {
  const { t } = useI18n();
  return (
    <>
      <Panel title={fit.trajectory.name} subtitle={fit.trajectory.description ?? undefined} icon={Target}>
        {/* Summary counts — integers, never a percentage */}
        <div className="grid grid-cols-3 gap-2 sm:grid-cols-6">
          <SummaryCount label={t("traj.summary.met")} value={fit.summary.met} tone="met" />
          <SummaryCount
            label={t("traj.summary.supported")}
            value={fit.summary.supported}
            tone="supported"
          />
          <SummaryCount label={t("traj.summary.open")} value={fit.summary.open} tone="open" />
          <SummaryCount
            label={t("traj.summary.against")}
            value={fit.summary.against}
            tone="against"
          />
          <SummaryCount
            label={t("traj.summary.discarded")}
            value={fit.summary.discarded}
            tone="discarded"
          />
          <SummaryCount label={t("traj.summary.total")} value={fit.summary.total} tone="total" />
        </div>
        <p className="mt-3 text-[11.5px] italic leading-relaxed text-ink-400">
          {t("traj.fit.caption")}
        </p>

        {/* Requirements list */}
        <div className="mt-5">
          <p className="mb-2 text-[11px] font-extrabold uppercase tracking-wide text-ink-500">
            {t("traj.fit.requirements")}
          </p>
          {fit.requirements.length > 0 ? (
            <div className="space-y-2">
              {fit.requirements.map((r) => (
                <div key={r.requirement_id} className="card-solid rounded-2xl p-3.5">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-[13px] font-bold text-ink-900">{r.label}</p>
                      {/* hypothesis_statement is API-authored (Spanish) — as-is */}
                      <p
                        className={`mt-1 text-[12.5px] leading-relaxed text-ink-500 ${
                          fitIsStruck(r.fit) ? "line-through opacity-60" : ""
                        }`}
                      >
                        {r.hypothesis_statement}
                      </p>
                    </div>
                    <div className="flex shrink-0 flex-col items-end gap-1.5">
                      <FitChip fit={r.fit} />
                      <span className="font-mono text-[11px] font-semibold text-ink-500">
                        {r.index == null ? "—" : `${r.index} / 1000`}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <Empty>{t("traj.fit.empty")}</Empty>
          )}
        </div>
      </Panel>

      {/* Add requirement */}
      <Panel title={t("traj.addReq.title")} icon={Plus}>
        <AddRequirement
          trajectoryId={fit.trajectory.id}
          hypotheses={hypotheses}
          onAdded={onRequirementAdded}
        />
      </Panel>
    </>
  );
}

function SummaryCount({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: FitStatus | "total";
}) {
  const color: Record<FitStatus | "total", string> = {
    met: "text-status-corroborada",
    supported: "text-status-activa",
    open: "text-ink-500",
    against: "text-status-debilitada",
    discarded: "text-status-descartada",
    total: "text-ink-900",
  };
  return (
    <div className="card-solid rounded-xl p-2.5 text-center">
      <p className={`font-display text-[22px] font-extrabold leading-none ${color[tone]}`}>
        {value}
      </p>
      <p className="mt-1 text-[9.5px] font-bold uppercase tracking-wide text-ink-400">{label}</p>
    </div>
  );
}

/* ─────────────────────────── create trajectory ─────────────────────────── */

function CreateTrajectory({
  onCreated,
}: {
  onCreated: (id: number | string) => void;
}) {
  const { t } = useI18n();
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const create = async () => {
    if (!name.trim()) return;
    setBusy(true);
    setErr(null);
    try {
      const res = await api.postTrajectory({
        name: name.trim(),
        description: desc.trim() || undefined,
      });
      setName("");
      setDesc("");
      onCreated(res.trajectory_id);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : t("err.trajCreate"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-2">
      <input
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder={t("traj.create.namePlaceholder")}
        aria-label={t("traj.create.name")}
        className="field-input"
      />
      <input
        value={desc}
        onChange={(e) => setDesc(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") void create();
        }}
        placeholder={t("traj.create.descPlaceholder")}
        aria-label={t("traj.create.desc")}
        className="field-input"
      />
      <button
        onClick={() => void create()}
        disabled={busy || !name.trim()}
        className="btn-primary shadow-soft inline-flex w-full items-center justify-center gap-2 rounded-full px-4 py-2 text-[13px] font-bold"
      >
        {busy ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
        {t("traj.create.action")}
      </button>
      {err && (
        <p className="flex items-center gap-1.5 text-[12px] text-status-debilitada">
          <AlertCircle className="h-3.5 w-3.5" /> {err}
        </p>
      )}
    </div>
  );
}

/* ─────────────────────────── add requirement ─────────────────────────── */

function AddRequirement({
  trajectoryId,
  hypotheses,
  onAdded,
}: {
  trajectoryId: number | string;
  hypotheses: Hypothesis[];
  onAdded: () => void;
}) {
  const { t } = useI18n();
  const [hypId, setHypId] = useState<string>("");
  const [label, setLabel] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  if (hypotheses.length === 0) {
    return <Empty>{t("traj.addReq.noHypotheses")}</Empty>;
  }

  const add = async () => {
    if (!hypId || !label.trim()) return;
    setBusy(true);
    setErr(null);
    try {
      await api.postRequirement(trajectoryId, {
        hypothesis_id: hypId,
        label: label.trim(),
      });
      setLabel("");
      setHypId("");
      onAdded();
    } catch (e) {
      // 400 typically means duplicate/missing — show a friendly message.
      if (e instanceof ApiError && e.status === 400) {
        setErr(t("traj.addReq.duplicate"));
      } else {
        setErr(e instanceof ApiError ? e.message : t("err.requirement"));
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-2.5">
      <div>
        <label className="mb-1 block text-[10.5px] font-bold uppercase tracking-wide text-ink-400">
          {t("traj.addReq.pickHypothesis")}
        </label>
        <select
          value={hypId}
          onChange={(e) => setHypId(e.target.value)}
          className="field-input"
        >
          <option value="">{t("traj.addReq.pickPlaceholder")}</option>
          {hypotheses.map((h) => (
            <option key={h.id} value={String(h.id)}>
              {h.statement}
            </option>
          ))}
        </select>
      </div>
      <div>
        <label className="mb-1 block text-[10.5px] font-bold uppercase tracking-wide text-ink-400">
          {t("traj.addReq.label")}
        </label>
        <input
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") void add();
          }}
          placeholder={t("traj.addReq.labelPlaceholder")}
          className="field-input"
        />
      </div>
      <button
        onClick={() => void add()}
        disabled={busy || !hypId || !label.trim()}
        className="btn-primary shadow-soft inline-flex items-center justify-center gap-2 rounded-full px-4 py-2 text-[13px] font-bold"
      >
        {busy ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
        {t("traj.addReq.action")}
      </button>
      {err && (
        <p className="flex items-center gap-1.5 text-[12px] text-status-debilitada">
          <AlertCircle className="h-3.5 w-3.5" /> {err}
        </p>
      )}
    </div>
  );
}

/* ─────────────────────────── discriminate ─────────────────────────── */

function DiscriminatePanel({ trajectories }: { trajectories: Trajectory[] }) {
  const { t } = useI18n();
  const [a, setA] = useState<string>("");
  const [b, setB] = useState<string>("");
  const [result, setResult] = useState<DiscriminateResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const sameOrEmpty = !a || !b || a === b;

  const run = async () => {
    if (sameOrEmpty) return;
    setBusy(true);
    setErr(null);
    try {
      setResult(await api.getDiscriminate(a, b));
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : t("err.discriminate"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel title={t("traj.disc.title")} subtitle={t("traj.disc.subtitle")} icon={GitCompare}>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        <div>
          <label className="mb-1 block text-[10.5px] font-bold uppercase tracking-wide text-ink-400">
            {t("traj.disc.pickA")}
          </label>
          <select value={a} onChange={(e) => setA(e.target.value)} className="field-input">
            <option value="">—</option>
            {trajectories.map((tr) => (
              <option key={tr.id} value={String(tr.id)}>
                {tr.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-1 block text-[10.5px] font-bold uppercase tracking-wide text-ink-400">
            {t("traj.disc.pickB")}
          </label>
          <select value={b} onChange={(e) => setB(e.target.value)} className="field-input">
            <option value="">—</option>
            {trajectories.map((tr) => (
              <option key={tr.id} value={String(tr.id)}>
                {tr.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      <button
        onClick={() => void run()}
        disabled={busy || sameOrEmpty}
        className="btn-primary shadow-soft mt-3 inline-flex items-center gap-2 rounded-full px-4 py-2 text-[13px] font-bold"
      >
        {busy ? <RefreshCw className="h-4 w-4 animate-spin" /> : <GitCompare className="h-4 w-4" />}
        {t("traj.disc.action")}
      </button>
      {a && b && a === b && (
        <p className="mt-2 text-[11.5px] text-ink-400">{t("traj.disc.same")}</p>
      )}

      {err && (
        <p className="mt-3 flex items-center gap-1.5 text-[12px] text-status-debilitada">
          <AlertCircle className="h-3.5 w-3.5" /> {err}
        </p>
      )}

      {result && (
        <div className="animate-fade-up mt-4 space-y-3">
          <p className="text-[11px] font-extrabold uppercase tracking-wide text-ink-500">
            {t("traj.disc.distinguishing")}
          </p>
          {result.distinguishing.length === 0 ? (
            <Empty>{t("traj.disc.none")}</Empty>
          ) : (
            <div className="space-y-2">
              {result.distinguishing.map((d) => {
                const suggested =
                  result.suggested_experiment_target?.hypothesis_id === d.hypothesis_id;
                return (
                  <div
                    key={`${d.hypothesis_id}-${d.only_in}`}
                    className={`rounded-2xl p-3.5 ${
                      suggested
                        ? "shadow-glow glass border border-brand-indigo/30"
                        : "card-solid"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-[13px] font-bold text-ink-900">{d.label}</p>
                        <span className="mt-1 inline-flex items-center gap-1 rounded-full bg-ink-900/5 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-ink-500">
                          {d.only_in === "a" ? t("traj.disc.onlyInA") : t("traj.disc.onlyInB")}
                        </span>
                      </div>
                      <div className="flex shrink-0 flex-col items-end gap-1.5">
                        <FitChip fit={d.fit} />
                        <span className="font-mono text-[11px] font-semibold text-ink-500">
                          {d.index == null ? "—" : `${d.index} / 1000`}
                        </span>
                      </div>
                    </div>
                    {suggested && (
                      <p className="mt-2 flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wide text-brand-deep">
                        <Target className="h-3.5 w-3.5" />
                        {t("traj.disc.suggested")}
                      </p>
                    )}
                  </div>
                );
              })}
            </div>
          )}
          {/* note is API-authored — rendered as-is */}
          {result.note && (
            <p className="text-[12px] italic leading-relaxed text-ink-500">{result.note}</p>
          )}
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
  icon: typeof Route;
  children: React.ReactNode;
}) {
  return (
    <div className="animate-fade-up card-solid shadow-soft rounded-3xl p-5">
      <div className="mb-4 flex items-start gap-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-brand-indigo/10 text-brand-deep">
          <Icon className="h-4.5 w-4.5" />
        </span>
        <div className="min-w-0">
          <h2 className="truncate font-display text-[17px] font-extrabold tracking-tight text-ink-900">
            {title}
          </h2>
          {subtitle && <p className="text-[12px] leading-snug text-ink-500">{subtitle}</p>}
        </div>
      </div>
      {children}
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

function TrajectoriesSkeleton() {
  return (
    <section className="mx-auto max-w-7xl px-4 pb-10 pt-6">
      <div className="skeleton h-9 w-56 rounded-lg" />
      <div className="mt-3 skeleton h-5 w-96 rounded-lg" />
      <div className="mt-6 grid gap-6 lg:grid-cols-[0.8fr_1.2fr]">
        <div className="space-y-6">
          <div className="skeleton h-64 rounded-3xl" />
          <div className="skeleton h-56 rounded-3xl" />
        </div>
        <div className="skeleton h-96 rounded-3xl" />
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
  const { t } = useI18n();
  return (
    <section className="mx-auto flex max-w-2xl flex-col items-center px-4 pb-10 pt-20 text-center">
      <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-status-debilitadaBg text-status-debilitada">
        <AlertCircle className="h-7 w-7" />
      </span>
      <h1 className="mt-5 font-display text-2xl font-extrabold tracking-tight text-ink-900">
        {t("err.backendTitle")}
      </h1>
      <p className="mt-2 max-w-md text-[14px] leading-relaxed text-ink-500">{message}</p>
      <button
        onClick={onRetry}
        className="btn-primary shadow-soft mt-5 inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-[13px] font-bold"
      >
        <RefreshCw className="h-4 w-4" />
        {t("err.retry")}
      </button>
    </section>
  );
}
