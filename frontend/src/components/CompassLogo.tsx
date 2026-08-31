export function CompassLogo({ className = "h-8 w-8" }: { className?: string }) {
  return (
    <svg viewBox="0 0 48 48" className={className} role="img" aria-label="COMPASS">
      <defs>
        <linearGradient id="compass-g" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#1C8296" />
          <stop offset="100%" stopColor="#0F5563" />
        </linearGradient>
      </defs>
      {/* outer ring — the bezel */}
      <circle
        cx="24"
        cy="24"
        r="20"
        fill="none"
        stroke="url(#compass-g)"
        strokeWidth="2.4"
        opacity="0.9"
      />
      {/* compass needle — points to evidence, not to flattery */}
      <path d="M24 7 L29 24 L24 41 L19 24 Z" fill="url(#compass-g)" opacity="0.95" />
      {/* the sealed pivot */}
      <circle cx="24" cy="24" r="3" fill="#fff" stroke="url(#compass-g)" strokeWidth="2" />
    </svg>
  );
}

export function CompassWordmark({ subtitle = "Adaptive navigation" }: { subtitle?: string }) {
  return (
    <span className="flex flex-col leading-none">
      <span className="brand-text text-[19px] font-extrabold tracking-tight">COMPASS</span>
      <span className="mt-0.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-ink-500">
        {subtitle}
      </span>
    </span>
  );
}
