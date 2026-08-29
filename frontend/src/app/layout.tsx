import type { Metadata } from "next";
import { Inter, Newsreader } from "next/font/google";
import "./globals.css";
import { Navbar } from "@/components/Navbar";
import { Footer } from "@/components/Footer";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const newsreader = Newsreader({
  subsets: ["latin"],
  variable: "--font-newsreader",
  display: "swap",
});

export const metadata: Metadata = {
  title: "COMPASS — Evidence, not flattery.",
  description:
    "An adaptive personal-navigation partner. No claim about you without sealed evidence, and no number describing you ever comes out of an LLM — a deterministic engine computes and seals every index before any model speaks.",
  keywords: [
    "abductive reasoning",
    "deterministic engine",
    "sealed evidence",
    "hash-chained ledger",
    "personal navigation",
    "Google ADK",
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${newsreader.variable}`}>
      <body className="font-sans">
        <div className="app-bg">
          <Navbar />
          <a href="#main" className="skip-link">
            Skip to content
          </a>
          <main id="main">{children}</main>
          <Footer />
        </div>
      </body>
    </html>
  );
}
