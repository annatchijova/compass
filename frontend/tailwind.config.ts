import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // COMPASS palette — reused verbatim from VELO's design language
        // (glass, ink scale, cyan->indigo brand gradient, soft shadows).
        canvas: "#F6F8FB",
        surface: "#FFFFFF",
        ink: {
          900: "#0B1220",
          700: "#1E2A44",
          500: "#5B6B84",
          400: "#8494A8",
        },
        brand: {
          cyan: "#22D3EE",
          indigo: "#6366F1",
          deep: "#4F46E5",
        },
        // Hypothesis-status tiers (color per status, adapted from VELO's
        // verdict tiers). These are UI chrome only — never a computed value.
        status: {
          corroborada: "#4F46E5",
          corroboradaBg: "#EEF0FF",
          activa: "#0891B2",
          activaBg: "#ECFEFF",
          latente: "#5B6B84",
          latenteBg: "#F1F5F9",
          debilitada: "#B45309",
          debilitadaBg: "#FFFBEB",
          descartada: "#64748B",
          descartadaBg: "#F1F5F9",
        },
      },
      fontFamily: {
        sans: ["var(--font-inter)", "ui-sans-serif", "system-ui", "sans-serif"],
        display: ["var(--font-newsreader)", "Georgia", "serif"],
      },
      borderRadius: {
        "2xl": "1rem",
        "3xl": "1.5rem",
      },
      boxShadow: {
        soft: "0 1px 2px rgba(11,18,32,0.04), 0 8px 24px rgba(11,18,32,0.06)",
        lift: "0 2px 6px rgba(11,18,32,0.05), 0 18px 40px rgba(11,18,32,0.10)",
        glow: "0 0 0 1px rgba(99,102,241,0.16), 0 12px 28px rgba(99,102,241,0.16)",
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
        drift: {
          "0%": { transform: "translateY(0) translateX(0)" },
          "50%": { transform: "translateY(-14px) translateX(10px)" },
          "100%": { transform: "translateY(0) translateX(0)" },
        },
      },
      animation: {
        "fade-up": "fade-up 0.5s ease-out both",
        drift: "drift 14s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
export default config;
