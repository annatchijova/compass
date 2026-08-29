"use client";

import { useEffect, useState } from "react";
import { Compass, X, ChevronRight } from "lucide-react";
import { useI18n } from "@/lib/i18n";

const DISMISS_KEY = "compass-tour-dismissed";

/**
 * Judge onboarding: a dismissible, collapsible "quick tour" card near the top
 * of the dashboard. A judge who doesn't know the domain should be able to do
 * something meaningful in ~60s. Dismissal is remembered in localStorage.
 */
export function QuickTour() {
  const { t } = useI18n();
  // Start hidden to avoid an SSR/first-paint flash; reveal after we can read
  // the dismissed flag in the browser.
  const [ready, setReady] = useState(false);
  const [dismissed, setDismissed] = useState(true);

  useEffect(() => {
    const flag =
      typeof window !== "undefined" && window.localStorage
        ? window.localStorage.getItem(DISMISS_KEY) === "1"
        : false;
    setDismissed(flag);
    setReady(true);
  }, []);

  const dismiss = () => {
    setDismissed(true);
    if (typeof window !== "undefined" && window.localStorage) {
      window.localStorage.setItem(DISMISS_KEY, "1");
    }
  };

  const reopen = () => {
    setDismissed(false);
    if (typeof window !== "undefined" && window.localStorage) {
      window.localStorage.removeItem(DISMISS_KEY);
    }
  };

  if (!ready) return null;

  const steps = [
    t("tour.step1"),
    t("tour.step2"),
    t("tour.step3"),
    t("tour.step4"),
    t("tour.step5"),
    t("tour.step6"),
  ];

  // Collapsed affordance: a small pill to re-open the tour once dismissed.
  if (dismissed) {
    return (
      <div className="animate-fade-up mt-5">
        <button
          onClick={reopen}
          className="btn-ghost inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[12px] font-semibold"
        >
          <Compass className="h-3.5 w-3.5 text-brand-indigo" />
          {t("tour.show")}
          <ChevronRight className="h-3.5 w-3.5" />
        </button>
      </div>
    );
  }

  return (
    <div className="animate-fade-up glass shadow-soft mt-5 rounded-3xl p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl brand-gradient text-white">
            <Compass className="h-4.5 w-4.5" />
          </span>
          <div>
            <p className="text-[10.5px] font-extrabold uppercase tracking-[0.1em] text-brand-deep">
              {t("tour.badge")}
            </p>
            <h2 className="font-display text-[17px] font-extrabold tracking-tight text-ink-900">
              {t("tour.title")}
            </h2>
          </div>
        </div>
        <button
          onClick={dismiss}
          aria-label={t("tour.dismiss")}
          title={t("tour.dismiss")}
          className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-ink-400 transition hover:bg-ink-900/5 hover:text-ink-700"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <ol className="mt-4 grid gap-2.5 sm:grid-cols-2">
        {steps.map((step, i) => (
          <li key={i} className="flex items-start gap-2.5">
            <span
              className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[11px] font-extrabold text-white ${
                i === steps.length - 1 ? "brand-gradient" : "bg-ink-900"
              }`}
            >
              {i + 1}
            </span>
            <span className="text-[12.5px] leading-relaxed text-ink-700">{step}</span>
          </li>
        ))}
      </ol>

      <div className="mt-4 flex justify-end">
        <button
          onClick={dismiss}
          className="btn-ghost inline-flex items-center gap-1.5 rounded-full px-4 py-1.5 text-[12px] font-bold"
        >
          {t("tour.dismiss")}
        </button>
      </div>
    </div>
  );
}
