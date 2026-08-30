// COMPASS API contract types. Mirrors the backend response shapes.

export type HypothesisStatus =
  | "latente"
  | "activa"
  | "corroborada"
  | "debilitada"
  | "descartada";

export type NextStepKind =
  | "completar_experimento"
  | "ejecutar_experimento"
  | "validar_evidencia"
  | "diseñar_experimento"
  | "abstain";

export type EvidenceType =
  | "self_report"
  | "narrative_extracted"
  | "behavioral"
  | "experiment_result"
  | "outcome_external";

export interface Health {
  status: string;
  llm_backend?: string;
  model?: string;
  gemini_transport?: string;
  db_durability?: string;
  seeded?: boolean;
  chain_linkage_ok?: boolean;
  chain_integrity_ok?: boolean;
  chain_content_ok?: boolean;
}

export interface StateHypothesis {
  id: number | string;
  statement: string;
  status: HypothesisStatus;
  index: number | null;
  engine_version?: string;
}

export interface NextStep {
  kind: NextStepKind;
  detail: string;
  [key: string]: unknown;
}

export interface CompassState {
  person?: string;
  hypotheses: StateHypothesis[];
  hypothesis_counts?: Record<string, number>;
  experiment_counts?: Record<string, number>;
  evidence_validated?: number;
  evidence_pending?: number;
  next_step: NextStep;
}

export interface Coverage {
  validated_unlinked: number;
}

export interface StateResponse {
  state: CompassState;
  seal: string;
  coverage?: Coverage;
}

export interface Evidence {
  id: number | string;
  evidence_type: EvidenceType;
  source: string;
  content: string; // JSON string
  validated: 0 | 1;
  deleted: 0 | 1;
  created_at?: string;
  validated_at?: string | null;
}

export interface EvidenceResponse {
  evidence: Evidence[];
}

export interface Hypothesis {
  id: number | string;
  statement: string;
  status: HypothesisStatus;
  origin?: string;
  index_value: number | null;
  engine_version?: string;
}

export interface HypothesesResponse {
  hypotheses: Hypothesis[];
}

export interface Experiment {
  id: number | string;
  hypothesis_id: number | string;
  design: string;
  success_criterion: string;
  failure_criterion: string;
  rival_hypothesis_id?: number | string | null;
  status: string;
  preregistered_at?: string;
  completed_at?: string | null;
}

export interface ExperimentsResponse {
  experiments: Experiment[];
}

export interface ChainEntry {
  seq: number;
  op: string;
  ts: string;
  audit_hash: string;
  prev_hash: string;
}

export interface ChainResponse {
  entries: ChainEntry[];
  linkage_ok: boolean;
  integrity_ok: boolean;
  content_ok?: boolean;
  issues: unknown[];
}

export interface RecomputeResult {
  hypothesis_id: number | string;
  support: number;
  contra: number;
  net: number;
  index: number;
  status: HypothesisStatus;
}

export interface RecomputeResponse {
  engine_version: string;
  config_hash: string;
  results: RecomputeResult[];
  seal: string;
}

export interface ExtractCandidate {
  evidence_id: number | string;
  "señal": string;
  cita: string;
}

export interface ExtractResponse {
  candidates: ExtractCandidate[];
  note?: string;
}

export interface NarrateResponse {
  seal: string;
  summary?: string;
  prose: string;
}

export interface AbduceProposal {
  statement: string;
}

export interface AbduceResponse {
  proposals: AbduceProposal[];
  state_seal: string;
}

/* ── Trajectories (vocational fit) ───────────────────────────────────────
   "What to dedicate yourself to" as a FIT between demonstrated capabilities
   and what a path requires — counts per state, never a destiny percentage.
   The fit only READS sealed hypotheses; it moves no index. */

export type FitState = "met" | "supported" | "open" | "against" | "discarded";

export interface Trajectory {
  id: number | string;
  name: string;
  description: string;
}

export interface TrajectoriesResponse {
  trajectories: Trajectory[];
}

export interface TrajectoryRequirement {
  requirement_id: number | string;
  hypothesis_id: number | string;
  label: string;
  hypothesis_statement: string;
  hypothesis_status: HypothesisStatus;
  index: number | null;
  fit: FitState;
}

/** Counts per fit state plus `total` — deliberately no ratio, no percentage. */
export type FitSummary = Record<FitState, number> & { total: number };

export interface TrajectoryFitResponse {
  trajectory: Trajectory;
  requirements: TrajectoryRequirement[];
  summary: FitSummary;
}

export interface DistinguishingRequirement {
  hypothesis_id: number | string;
  label: string;
  only_in: "a" | "b";
  fit: FitState;
  index: number;
}

export interface DiscriminateResponse {
  trajectory_a: Trajectory;
  trajectory_b: Trajectory;
  shared_requirements: (number | string)[];
  distinguishing: DistinguishingRequirement[];
  suggested_experiment_target: DistinguishingRequirement | null;
  note: string;
}

/* ── Concrete suggestions from the LLM ───────────────────────────────────
   Both are PROPOSALS: they live outside the seal, write nothing to the
   ledger, and move no index. The person edits and decides. */

export interface ExperimentDraft {
  design: string;
  success_criterion: string;
  failure_criterion: string;
}

export interface DesignExperimentResponse {
  hypothesis_id: number | string;
  hypothesis_statement: string;
  draft: ExperimentDraft;
  note?: string;
}

export type ResourceKind =
  | "course"
  | "community"
  | "project"
  | "reading"
  | "tool"
  | "person";

export interface Resource {
  title: string;
  kind: ResourceKind;
  why: string;
  /** Empty when the model found no source. Never render a link for "". */
  url: string;
}

export interface GroundingSource {
  title: string;
  uri: string;
}

export interface ResourcesResponse {
  hypothesis_id: number | string;
  capability: string;
  resources: Resource[];
  /** False = these came from the model's memory, NOT from a real search. */
  grounded: boolean;
  sources: GroundingSource[];
  note?: string;
}
