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
        // COMPASS palette — azul petróleo (petrol) + mostaza (mustard) + gris.
        // Petrol is the dominant brand color, mustard the single warm accent,
        // gray the neutral system. Token NAMES are kept from the prior
        // cyan/indigo/ink scheme so components recolor automatically.
        canvas: "#F4F5F6",
        surface: "#FFFFFF",
        ink: {
          900: "#15191D",
          700: "#2C333A",
          500: "#5C666E",
          400: "#8B949C",
        },
        brand: {
          // Petrol family (was cyan->indigo->deep).
          cyan: "#1C8296", // bright petrol — light end of gradients
          indigo: "#0F5563", // primary petrol
          deep: "#0C3B45", // deep petrol
          // Mustard accent.
          mustard: "#C6971C",
          mustardBright: "#DDB03A",
          mustardBg: "#FBF3DA",
        },
        // Hypothesis-status tiers. UI chrome only — never a computed value.
        status: {
          corroborada: "#0F5563", // petrol
          corroboradaBg: "#E6F0F2",
          activa: "#C6971C", // mustard
          activaBg: "#FBF3DA",
          latente: "#5C666E", // gray
          latenteBg: "#F1F2F3",
          debilitada: "#A65A2A", // muted terracotta ("weakened")
          debilitadaBg: "#F7EEE8",
          descartada: "#727C84", // gray
          descartadaBg: "#F1F2F3",
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
        soft: "0 1px 2px rgba(21,25,29,0.04), 0 8px 24px rgba(21,25,29,0.06)",
        lift: "0 2px 6px rgba(21,25,29,0.05), 0 18px 40px rgba(21,25,29,0.10)",
        glow: "0 0 0 1px rgba(15,85,99,0.16), 0 12px 28px rgba(15,85,99,0.16)",
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
