"use client";

import { Component, type ReactNode } from "react";
import { AlertCircle, RefreshCw } from "lucide-react";
import { useI18n } from "@/lib/i18n";

/**
 * React error boundary for the dashboard content. If any panel throws during
 * render, the user sees a small, calm "Something went wrong here — reload"
 * card instead of a blank white-screen client-side exception. No alarm color,
 * consistent with the app's sensory rules.
 *
 * Error boundaries must be class components (there is no hook equivalent for
 * getDerivedStateFromError / componentDidCatch).
 */
class ErrorBoundaryInner extends Component<
  {
    children: ReactNode;
    fallback: (reset: () => void) => ReactNode;
  },
  { hasError: boolean }
> {
  constructor(props: {
    children: ReactNode;
    fallback: (reset: () => void) => ReactNode;
  }) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error: unknown) {
    // Surface it for debugging without crashing the tree.
    // eslint-disable-next-line no-console
    console.error("Dashboard panel error:", error);
  }

  reset = () => this.setState({ hasError: false });

  render() {
    if (this.state.hasError) {
      return this.props.fallback(this.reset);
    }
    return this.props.children;
  }
}

function BoundaryCard({ onReset }: { onReset: () => void }) {
  const { t } = useI18n();
  return (
    <div className="mx-auto my-8 max-w-md rounded-3xl border border-ink-900/8 bg-white p-6 text-center shadow-soft">
      <span className="mx-auto flex h-11 w-11 items-center justify-center rounded-2xl bg-ink-900/5 text-ink-500">
        <AlertCircle className="h-5 w-5" />
      </span>
      <p className="mt-4 font-display text-[16px] font-extrabold tracking-tight text-ink-900">
        {t("boundary.title")}
      </p>
      <p className="mt-1.5 text-[13px] leading-relaxed text-ink-500">{t("boundary.body")}</p>
      <button
        onClick={() => {
          onReset();
          // A hard reload is the surest recovery when a panel's state is bad.
          if (typeof window !== "undefined") window.location.reload();
        }}
        className="btn-ghost mt-4 inline-flex items-center gap-1.5 rounded-full px-4 py-2 text-[13px] font-bold"
      >
        <RefreshCw className="h-3.5 w-3.5" />
        {t("boundary.reload")}
      </button>
    </div>
  );
}

export function DashboardErrorBoundary({ children }: { children: ReactNode }) {
  return (
    <ErrorBoundaryInner fallback={(reset) => <BoundaryCard onReset={reset} />}>
      {children}
    </ErrorBoundaryInner>
  );
}
