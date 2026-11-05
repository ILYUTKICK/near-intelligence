import type { Metadata } from "next";
import type { ReactNode } from "react";
import localFont from "next/font/local";
import "@/styles/globals.css";

// Self-hosted variable fonts (SIL OFL 1.1) — see src/styles/fonts/LICENSE-NOTES.md.
// next/font/local serves them same-origin with automatic fallback-metric
// adjustment; no external font service is contacted at runtime.
const newsreader = localFont({
  src: [
    { path: "../styles/fonts/Newsreader-Variable.woff2", style: "normal" },
    { path: "../styles/fonts/Newsreader-Italic-Variable.woff2", style: "italic" },
  ],
  weight: "200 800",
  display: "swap",
  variable: "--font-newsreader",
  fallback: ["Georgia", "Times New Roman", "serif"],
});

const inter = localFont({
  src: [{ path: "../styles/fonts/Inter-Variable.woff2", style: "normal" }],
  weight: "100 900",
  display: "swap",
  variable: "--font-inter",
  fallback: ["system-ui", "Segoe UI", "sans-serif"],
});

export const metadata: Metadata = {
  title: "NEAR Intelligence",
  description: "Evidence-first NEAR investment research.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={`${newsreader.variable} ${inter.variable}`}>
      <body>{children}</body>
    </html>
  );
}
