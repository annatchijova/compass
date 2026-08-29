"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertCircle, Compass, Plus, RefreshCw, Split, Target } from "lucide-react";
import * as api from "@/lib/api";
import { ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { Panel, Empty, ExampleChips } from "@/components/Panel";
import { TrajectoryFit, FitChip } from "@/components/TrajectoryFit";
import type {
  StateResponse,
  Trajectory,
  TrajectoryFitResponse,
  DiscriminateResponse,
} from "@/lib/types";

/**
 * Trajectories — "what to dedicate yourself to" as a FIT between demonstrated
 * capabilities and what a path requires (design doc §5/§7).
 *
 * Everything here is read-only over the sealed state: a fit projects
 * already-sealed hypotheses, and `discriminate` names the cheapest open
 * capability that would separate two paths. Neither recomputes an index nor
 * appends to the audit chain, so this panel never needs a reseal.
 *
 * A requirement must be backed by a hypothesis — that is the structural reason
 * a trajectory cannot become a wish list.
 */
export function TrajectoriesPanel({
  hypotheses,
}: {
  hypotheses: StateResponse["state"]["hypotheses"];
}) {
  const { t } = useI18n();
  const [trajectories, setTrajectories] = useState<Trajectory[] | null>(null);
  const [selected, setSelected] = useState<string>("");
  const [fit, setFit] = useState<TrajectoryFitResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const loadTrajectories = useCallback(async () => {
    const res = await api.getTrajectories();
    setTrajectories(res.trajectories);
    return res.trajectories;
  }, []);

  const loadFit = useCallback(
    async (id: string) => {
      if (!id) {
        setFit(null);
        return;
      }
      try {
        setFit(await api.getTrajectoryFit(id));
      } catch (e) {
        setErr(e instanceof ApiError ? e.message : t("err.trajectoryFit"));
      }
    },
    [t],
  );

  // First load: fetch the list and open the first trajectory, so the panel
  // lands on something readable instead of an empty selector.
  useEffect(() => {
    void (async () => {
      try {
        const list = await loadTrajectories();
        if (list.length > 0) {
          const first = String(list[0].id);
          setSelected(first);
          await loadFit(first);
        }
      } catch (e) {
        setErr(e instanceof ApiError ? e.message : t("err.trajectoryFit"));
      }
    })();
  }, [loadTrajectories, loadFit, t]);

  const onSelect = useCallback(
    (id: string) => {
      setSelected(id);
      setErr(null);
      void loadFit(id);
    },
    [loadFit],
  );

  // A hypothesis added or an index resealed elsewhere changes the fit, since
  // the fit reads hypothesis status. Re-read whenever the parent's sealed
  // hypotheses change identity or status.
  const fingerprint = hypotheses.map((h) => `${h.id}:${h.status}`).join(",");
  useEffect(() => {
    if (selected) void loadFit(selected);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fingerprint]);

  const addTrajectory = useCallback(
    async (name: string) => {
      setBusy("add");
      setErr(null);
      try {
        const { trajectory_id } = await api.postTrajectory({ name });
        await loadTrajectories();
        onSelect(String(trajectory_id));
      } catch (e) {
        setErr(e instanceof ApiError ? e.message : t("err.trajectory"));
      } finally {
        setBusy(null);
      }
    },
    [loadTrajectories, onSelect, t],
  );

  const addRequirement = useCallback(
    async (label: string, hypothesisId: string) => {
      if (!selected) return;
      setBusy("req");
      setErr(null);
      try {
        await api.postRequirement(selected, {
          hypothesis_id: hypothesisId,
          label,
        });
        await loadFit(selected);
      } catch (e) {
        setErr(e instanceof ApiError ? e.message : t("err.requirement"));
      } finally {
        setBusy(null);
      }
    },
    [selected, loadFit, t],
  );

  return (
    <Panel
      title={t("panel.traj.title")}
      subtitle={t("panel.traj.subtitle")}
      icon={Compass}
    >
      <p className="mb-3 text-[12px] leading-relaxed text-ink-500">
        {t("traj.readonly")}
      </p>

      {trajectories && trajectories.length > 0 ? (
        <>
          <label className="block">
            <span className="mb-1 block text-[10.5px] font-bold uppercase tracking-wide text-ink-400">
              {t("traj.select")}
            </span>
            <select
              value={selected}
              onChange={(e) => onSelect(e.target.value)}
              className="field-input w-full"
            >
              {trajectories.map((tr) => (
                <option key={tr.id} value={String(tr.id)}>
                  {tr.name}
                </option>
              ))}
            </select>
          </label>

          <div className="mt-4">
            {fit ? <TrajectoryFit fit={fit} /> : <Empty>{t("panel.traj.empty")}</Empty>}
          </div>

          <RequirementForm
            hypotheses={hypotheses}
            usedHypothesisIds={(fit?.requirements ?? []).map((r) =>
              String(r.hypothesis_id),
            )}
            busy={busy === "req"}
            onAdd={addRequirement}
          />

          <DiscriminatePanel trajectories={trajectories} />
        </>
      ) : (
        <Empty>{t("panel.traj.empty")}</Empty>
      )}

      <AddTrajectoryForm busy={busy === "add"} onAdd={addTrajectory} />

      {err && (
        <p className="mt-2 flex items-center gap-1.5 text-[12px] text-status-debilitada">
          <AlertCircle className="h-3.5 w-3.5" /> {err}
        </p>
      )}
    </Panel>
  );
}

function AddTrajectoryForm({
  busy,
  onAdd,
}: {
  busy: boolean;
  onAdd: (name: string) => void;
}) {
  const { t } = useI18n();
  const [name, setName] = useState("");

  const submit = () => {
    if (!name.trim()) return;
    onAdd(name.trim());
    setName("");
  };

  return (
    <div className="mt-4 border-t border-ink-900/5 pt-4">
      <ExampleChips
        hint={t("examples.trajectoryHint")}
        examples={[t("example.trajectory1"), t("example.trajectory2")]}
        onPick={setName}
      />
      <div className="mt-3 flex flex-col gap-2 sm:flex-row">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") submit();
          }}
          placeholder={t("traj.addPlaceholder")}
          className="field-input flex-1"
        />
        <button
          onClick={submit}
          disabled={busy || !name.trim()}
          className="btn-primary shadow-soft inline-flex shrink-0 items-center justify-center gap-2 rounded-full px-4 py-2 text-[13px] font-bold"
        >
          {busy ? (
            <RefreshCw className="h-4 w-4 animate-spin" />
          ) : (
            <Plus className="h-4 w-4" />
          )}
          {t("traj.add")}
        </button>
      </div>
    </div>
  );
}

/** A requirement is always anchored to a hypothesis — never free text alone. */
function RequirementForm({
  hypotheses,
  usedHypothesisIds,
  busy,
  onAdd,
}: {
  hypotheses: StateResponse["state"]["hypotheses"];
  usedHypothesisIds: string[];
  busy: boolean;
  onAdd: (label: string, hypothesisId: string) => void;
}) {
  const { t } = useI18n();
  const [label, setLabel] = useState("");
  const [hypothesisId, setHypothesisId] = useState("");

  // The backend rejects a second requirement backed by the same hypothesis
  // within one trajectory (400). Offering one anyway would default the form
  // to a choice that is guaranteed to fail, so already-used hypotheses are
  // filtered out rather than left selectable.
  const available = hypotheses.filter(
    (h) => !usedHypothesisIds.includes(String(h.id)),
  );
  const first = available.length > 0 ? String(available[0].id) : "";
  // A stale selection (the chosen hypothesis just became used) falls back to
  // the first still-available one.
  const chosen =
    hypothesisId && available.some((h) => String(h.id) === hypothesisId)
      ? hypothesisId
      : first;

  if (available.length === 0) {
    return (
      <p className="mt-4 flex items-start gap-1.5 border-t border-ink-900/5 pt-4 text-[12px] text-ink-500">
        <Target className="mt-0.5 h-3.5 w-3.5 shrink-0 text-ink-400" />
        {hypotheses.length === 0
          ? t("traj.req.needHypothesis")
          : t("traj.req.allUsed")}
      </p>
    );
  }

  const submit = () => {
    if (!label.trim() || !chosen) return;
    onAdd(label.trim(), chosen);
    setLabel("");
  };

  return (
    <div className="mt-4 border-t border-ink-900/5 pt-4">
      <div className="flex flex-col gap-2">
        <input
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") submit();
          }}
          placeholder={t("traj.req.labelPlaceholder")}
          className="field-input w-full"
        />
        <label className="block">
          <span className="mb-1 block text-[10.5px] font-bold uppercase tracking-wide text-ink-400">
            {t("traj.req.hypothesis")}
          </span>
          <select
            value={chosen}
            onChange={(e) => setHypothesisId(e.target.value)}
            className="field-input w-full"
          >
            {available.map((h) => (
              <option key={h.id} value={String(h.id)}>
                #{h.id} — {h.statement}
              </option>
            ))}
          </select>
        </label>
        <button
          onClick={submit}
          disabled={busy || !label.trim()}
          className="btn-ghost inline-flex items-center justify-center gap-2 self-start rounded-full px-4 py-2 text-[13px] font-bold"
        >
          {busy ? (
            <RefreshCw className="h-4 w-4 animate-spin" />
          ) : (
            <Plus className="h-4 w-4" />
          )}
          {t("traj.req.add")}
        </button>
      </div>
    </div>
  );
}

/**
 * Research economy: of the capabilities required by exactly ONE of two paths
 * and still unresolved, the backend suggests the cheapest to test — the one
 * with the least evidence behind it. The suggestion is deterministic; this
 * view only displays it.
 */
function DiscriminatePanel({ trajectories }: { trajectories: Trajectory[] }) {
  const { t } = useI18n();
  const [a, setA] = useState(String(trajectories[0]?.id ?? ""));
  const [b, setB] = useState(String(trajectories[1]?.id ?? ""));
  const [result, setResult] = useState<DiscriminateResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const nameOf = (side: "a" | "b") =>
    side === "a" ? result?.trajectory_a.name ?? "" : result?.trajectory_b.name ?? "";

  const run = async () => {
    setBusy(true);
    setErr(null);
    try {
      setResult(await api.discriminate(a, b));
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : t("err.discriminate"));
    } finally {
      setBusy(false);
    }
  };

  if (trajectories.length < 2) {
    return (
      <p className="mt-4 flex items-start gap-1.5 border-t border-ink-900/5 pt-4 text-[12px] text-ink-500">
        <Split className="mt-0.5 h-3.5 w-3.5 shrink-0 text-ink-400" />
        {t("traj.disc.pickTwo")}
      </p>
    );
  }

  return (
    <div className="mt-4 border-t border-ink-900/5 pt-4">
      <p className="mb-2 flex items-center gap-1.5 text-[10.5px] font-bold uppercase tracking-wide text-ink-400">
        <Split className="h-3.5 w-3.5" />
        {t("traj.disc.title")}
      </p>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
        <select
          value={a}
          onChange={(e) => setA(e.target.value)}
          className="field-input flex-1"
        >
          {trajectories.map((tr) => (
            <option key={tr.id} value={String(tr.id)}>
              {tr.name}
            </option>
          ))}
        </select>
        <select
          value={b}
          onChange={(e) => setB(e.target.value)}
          className="field-input flex-1"
        >
          {trajectories.map((tr) => (
            <option key={tr.id} value={String(tr.id)}>
              {tr.name}
            </option>
          ))}
        </select>
        <button
          onClick={() => void run()}
          disabled={busy || a === b}
          className="btn-ghost inline-flex shrink-0 items-center justify-center gap-2 rounded-full px-4 py-2 text-[13px] font-bold"
        >
          {busy ? (
            <RefreshCw className="h-4 w-4 animate-spin" />
          ) : (
            <Split className="h-4 w-4" />
          )}
          {t("traj.disc.run")}
        </button>
      </div>

      {a === b && (
        <p className="mt-2 text-[12px] text-ink-500">{t("traj.disc.pickTwo")}</p>
      )}

      {err && (
        <p className="mt-2 flex items-center gap-1.5 text-[12px] text-status-debilitada">
          <AlertCircle className="h-3.5 w-3.5" /> {err}
        </p>
      )}

      {result && (
        <div className="mt-3 space-y-3">
          {result.suggested_experiment_target ? (
            <div className="rounded-2xl bg-brand-indigo/[0.06] p-3.5">
              <p className="text-[10.5px] font-bold uppercase tracking-wide text-brand-deep">
                {t("traj.disc.suggested")}
              </p>
              <p className="mt-1 text-[13.5px] font-bold text-ink-900">
                {result.suggested_experiment_target.label}
              </p>
              <p className="mt-1 text-[12px] text-ink-600">
                {t("traj.disc.onlyIn", {
                  name: nameOf(result.suggested_experiment_target.only_in),
                })}
              </p>
              {/* Backend-authored note (deterministic, not narrated) */}
              <p className="mt-2 text-[12px] leading-relaxed text-ink-600">
                {result.note}
              </p>
            </div>
          ) : (
            <Empty>{t("traj.disc.none")}</Empty>
          )}

          {result.distinguishing.length > 0 && (
            <div>
              <p className="mb-1.5 text-[10.5px] font-bold uppercase tracking-wide text-ink-400">
                {t("traj.disc.distinguishing")}
              </p>
              <div className="space-y-1.5">
                {result.distinguishing.map((d) => (
                  <div
                    key={`${d.only_in}-${d.hypothesis_id}`}
                    className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-ink-900/[0.02] px-3 py-2"
                  >
                    <span className="min-w-0 flex-1 text-[12.5px] text-ink-700">
                      {d.label}
                    </span>
                    <span className="text-[11px] text-ink-400">
                      {t("traj.disc.onlyIn", { name: nameOf(d.only_in) })}
                    </span>
                    <FitChip fit={d.fit} />
                  </div>
                ))}
              </div>
            </div>
          )}

          <p className="text-[11.5px] text-ink-500">
            {t("traj.disc.shared", { n: result.shared_requirements.length })}
          </p>
        </div>
      )}
    </div>
  );
}
