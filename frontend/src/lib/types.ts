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

/* ─────────────────────────── Intake (Big Five + RIASEC) ─────────────────────────── */

// The intake SEEDS candidate hypotheses to test — it is never a verdict.
export type Instrument = "big_five" | "riasec";

export interface IntakeItem {
  code: string;
  dimension: string;
  text: string;
}

export interface IntakeItemsResponse {
  instrument: Instrument;
  lang: string;
  items: IntakeItem[];
}

export interface IntakeProposal {
  dimension: string;
  raw: number;
  max: number;
  statement: string;
}

export interface IntakeProposalsResponse {
  assessment_id: number | string;
  instrument: Instrument;
  proposals: IntakeProposal[];
  note: string;
}

/* ─────────────────────────── O*NET occupations ───────────────────────────
   Adopting an occupation seeds candidate required capabilities to test
   against the person's evidence — never a verdict about whether they fit.
   The `attribution` string is a CC BY 4.0 requirement and must be shown. */

export interface OnetOccupationSummary {
  code: string;
  title: string;
  riasec: string;
  requirement_count: number;
}

export interface OnetOccupationsResponse {
  occupations: OnetOccupationSummary[];
  attribution: string;
}

export interface OnetOccupationDetail {
  code: string;
  title: string;
  riasec: string;
  requirements: string[];
  attribution: string;
}

export interface OnetAdoptRequirement {
  requirement_id: number | string;
  hypothesis_id: number | string;
  label: string;
}

export interface OnetAdoptResponse {
  trajectory_id: number | string;
  title: string;
  onet_code: string;
  requirements: OnetAdoptRequirement[];
}

/* ─────────────────────────── Narrative prompts (on-ramp) ───────────────────────────
   Gentle narrative questions used by Calm mode when there is nothing to
   compute yet. One question at a time — never a list of 18. */

export type PromptTier = "easy" | "medium" | "hard" | string;

export interface Prompt {
  code: string;
  tier: PromptTier;
  text: string;
}

export interface PromptsResponse {
  prompts: Prompt[];
}

export interface ProposedRequirement {
  hypothesis_id: number;
  label: string;
}

export interface ProposedTrajectory {
  name: string;
  description: string;
  requirements: ProposedRequirement[];
}

export interface ProposeTrajectoriesResponse {
  proposals: ProposedTrajectory[];
  note?: string;
}

/* ── Self-perception vs. data confrontation (design doc §5) ──────────────
   The API returns COUNTS and the policy, never prose: the sentence is built
   from a fixed template here, so no model can turn a discrepancy into a
   verdict about who the person is. Read-only — it moves no index. */

export type ConfrontationKind = "record_exceeds_self" | "self_exceeds_record";

export interface Confrontation {
  hypothesis_id: number | string;
  hypothesis_statement: string;
  status: HypothesisStatus;
  index: number | null;
  kind: ConfrontationKind;
  self_supports: number;
  self_contradicts: number;
  record_supports: number;
  record_contradicts: number;
  distinct_types: number;
}

export interface ConfrontationPolicy {
  policy_version: string;
  index_threshold: number;
  min_distinct_types: number;
  max_surfaced: number;
}

export interface ConfrontationsResponse {
  confrontations: Confrontation[];
  held_back: number;
  policy: ConfrontationPolicy;
  note?: string;
}
