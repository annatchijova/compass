import Link from "next/link";
import {
  ArrowRight,
  Lock,
  Cpu,
  GitBranch,
  ShieldCheck,
  ScrollText,
  Scale,
} from "lucide-react";

const CYCLE = [
  "DISCOVER",
  "MAP",
  "HYPOTHESIZE",
  "EXPERIMENT",
  "OBSERVE",
  "REFLECT",
  "UPDATE",
  "NAVIGATE",
];

const FEATURES = [
  {
    icon: Lock,
    title: "Sealed evidence ledger",
    desc: "No claim about the person exists without recorded, sealed evidence. Every assertion is appended to an append-only, hash-chained audit ledger you can verify.",
  },
  {
    icon: Cpu,
    title: "No number from an LLM",
    desc: "A deterministic engine computes and seals every confidence index before any model speaks. The narrator only puts fixed figures into words — it can never move them.",
  },
  {
    icon: GitBranch,
    title: "Rival hypotheses, discriminating experiments",
    desc: "Competing explanations are held alive until a preregistered experiment separates them. Contradicting evidence weighs more than confirming — a compass, not a mirror.",
  },
];

export default function LandingPage() {
  return (
    <section className="mx-auto max-w-7xl px-4 pb-8 pt-8">
      {/* Hero */}
      <div className="grid items-center gap-10 lg:grid-cols-[1.05fr_0.95fr]">
        <div>
          <div className="animate-fade-up inline-flex items-center gap-2 rounded-full border border-ink-900/8 bg-white px-2 py-1 pl-3 shadow-soft">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-brand-indigo/10 px-2.5 py-1 text-[11.5px] font-bold text-brand-deep">
              <span className="h-1.5 w-1.5 rounded-full bg-brand-indigo shadow-[0_0_0_4px_rgba(99,102,241,0.16)]" />
              Adaptive personal navigation
            </span>
          </div>

          <h1 className="animate-fade-up mt-5 font-display text-[clamp(38px,5.2vw,62px)] font-extrabold leading-[0.96] tracking-[-0.035em] text-ink-900">
            Evidence, not flattery.
            <br />
            <span className="brand-text font-bold italic">A compass, not a mirror.</span>
          </h1>

          <p className="animate-fade-up mt-5 max-w-[560px] text-[17.5px] leading-[1.62] text-ink-700">
            COMPASS is a navigation partner bound by two invariants: no claim about you
            exists without sealed evidence, and no number describing you ever comes out
            of a language model. A deterministic engine computes and seals every index
            before any model is allowed to speak.
          </p>

          <div className="animate-fade-up mt-6 flex flex-wrap gap-3">
            <Link
              href="/compass"
              className="btn-primary shadow-soft inline-flex items-center gap-2 rounded-full px-6 py-3 text-sm font-bold"
            >
              Open the dashboard
              <ArrowRight className="h-4 w-4" />
            </Link>
            <a
              href="#how"
              className="btn-ghost inline-flex items-center gap-2 rounded-full px-5 py-3 text-sm font-semibold"
            >
              How it works
            </a>
          </div>

          <div className="animate-fade-up mt-6 grid max-w-[560px] grid-cols-1 gap-2.5 sm:grid-cols-3">
            <MiniStat
              icon={Cpu}
              title="Deterministic core"
              desc="The index is sealed before the LLM narrates."
            />
            <MiniStat
              icon={Scale}
              title="Anti-flattery"
              desc="Contradicting evidence weighs more than confirming."
            />
            <MiniStat
              icon={ScrollText}
              title="Audit ledger"
              desc="Append-only, hash-chained, independently verifiable."
            />
          </div>
        </div>

        {/* Hero visual — an index dial that is explicitly not a percentage */}
        <div className="animate-fade-up">
          <HeroDial />
        </div>
      </div>

      {/* Features */}
      <div className="mt-12 grid gap-4 md:grid-cols-3">
        {FEATURES.map((f) => {
          const Icon = f.icon;
          return (
            <div key={f.title} className="card-solid card-hover rounded-3xl p-6">
              <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-brand-indigo/10 text-brand-deep">
                <Icon className="h-5 w-5" />
              </span>
              <h3 className="mt-4 font-display text-lg font-extrabold tracking-tight text-ink-900">
                {f.title}
              </h3>
              <p className="mt-1.5 text-[13.5px] leading-relaxed text-ink-500">{f.desc}</p>
            </div>
          );
        })}
      </div>

      {/* How it works — the abductive cycle */}
      <div
        id="how"
        className="glass-subtle mt-8 rounded-2xl px-5 py-4"
      >
        <div className="mb-3 flex items-center gap-2">
          <span className="text-[11px] font-extrabold uppercase tracking-[0.08em] text-ink-500">
            The abductive cycle
          </span>
          <span className="inline-flex items-center gap-1.5 text-[11px] text-ink-400">
            <span className="ml-1">rival hypotheses held alive until an experiment separates them</span>
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-3">
          {CYCLE.map((step, i) => (
            <span key={step} className="flex items-center gap-2.5">
              <span
                className={`flex h-6 w-6 items-center justify-center rounded-full text-[11px] font-extrabold ${
                  i === CYCLE.length - 1 ? "brand-gradient text-white" : "bg-ink-900 text-white"
                }`}
              >
                {i + 1}
              </span>
              <span className="text-[12.5px] font-semibold text-ink-700">{step}</span>
              {i < CYCLE.length - 1 && <span className="ml-1 text-ink-400">→</span>}
            </span>
          ))}
          <span className="ml-auto inline-flex items-center gap-1.5 text-[12px] text-ink-500">
            <Lock className="h-3.5 w-3.5 text-brand-deep" />
            index sealed before narration
          </span>
        </div>
      </div>
    </section>
  );
}

function MiniStat({
  icon: Icon,
  title,
  desc,
}: {
  icon: typeof Cpu;
  title: string;
  desc: string;
}) {
  return (
    <div className="card-solid flex items-start gap-2.5 rounded-2xl p-3">
      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-brand-indigo/10 text-brand-deep">
        <Icon className="h-4 w-4" />
      </span>
      <div>
        <p className="text-[12.5px] font-bold leading-tight text-ink-900">{title}</p>
        <p className="mt-0.5 text-[11.5px] leading-[1.35] text-ink-500">{desc}</p>
      </div>
    </div>
  );
}

// A decorative dial reinforcing that the confidence index is 0–1000, never a %.
function HeroDial() {
  const R = 80;
  const CIRC = 2 * Math.PI * R;
  const value = 742; // illustrative only
  const pct = value / 1000;
  return (
    <div className="glass shadow-lift mx-auto flex max-w-[420px] flex-col items-center rounded-3xl p-8">
      <div className="relative h-[220px] w-[220px]">
        <svg viewBox="0 0 200 200" className="h-full w-full -rotate-90">
          <circle cx="100" cy="100" r={R} fill="none" stroke="rgba(11,18,32,0.07)" strokeWidth="14" />
          <circle
            cx="100"
            cy="100"
            r={R}
            fill="none"
            stroke="url(#hero-dial-g)"
            strokeWidth="14"
            strokeLinecap="round"
            strokeDasharray={CIRC}
            strokeDashoffset={CIRC * (1 - pct)}
          />
          <defs>
            <linearGradient id="hero-dial-g" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#22D3EE" />
              <stop offset="100%" stopColor="#6366F1" />
            </linearGradient>
          </defs>
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="brand-text font-display text-[42px] font-extrabold leading-none tracking-tight">
            {value}
            <span className="text-[16px] font-bold text-ink-400"> / 1000</span>
          </span>
          <span className="mt-1.5 text-[10px] font-bold uppercase tracking-[0.08em] text-ink-400">
            confidence index
          </span>
        </div>
      </div>
      <p className="mt-4 flex items-center gap-1.5 text-center text-[12px] leading-relaxed text-ink-500">
        <ShieldCheck className="h-3.5 w-3.5 shrink-0 text-brand-indigo" />
        an integer accumulation of evidence under versioned rules — never a probability
      </p>
    </div>
  );
}
