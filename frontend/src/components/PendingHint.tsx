"use client";

/**
 * A calm, gentle "we're working" affordance for model-backed (Gemini/Vertex)
 * calls that take ~10–30s. Deliberately soft: a slow opacity pulse and a short
 * ETA hint — no fast spinner, no alarm color, no jarring motion (the audience
 * includes ADHD/autistic users). Respects prefers-reduced-motion via the
 * global rule in globals.css, which disables the pulse animation.
 */
export function PendingHint({ hint }: { hint: string }) {
  return (
    <p
      className="mt-3 flex items-center gap-2 text-[12px] leading-relaxed text-ink-500"
      role="status"
      aria-live="polite"
    >
      <span className="inline-flex gap-0.5" aria-hidden>
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-brand-indigo/60" />
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-brand-indigo/60 [animation-delay:200ms]" />
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-brand-indigo/60 [animation-delay:400ms]" />
      </span>
      {hint}
    </p>
  );
}
